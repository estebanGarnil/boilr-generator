import json
import stat
from pathlib import Path

from rich.text import Text
from typer.testing import CliRunner

from boilr_generator import cli
from boilr_generator.generation import (
    ProjectGenerator,
    observe_project,
)
from boilr_generator.state import (
    ProjectStateStorage,
)

runner = CliRunner()


def snapshot_output(
    output_path: Path,
) -> dict[str, tuple[str, object, int]]:
    """Capture paths, contents, links, and permissions."""
    if not output_path.exists():
        return {}

    paths = [
        output_path,
        *sorted(output_path.rglob("*")),
    ]
    snapshot = {}

    for path in paths:
        relative_path = (
            "."
            if path == output_path
            else path.relative_to(
                output_path
            ).as_posix()
        )
        path_stat = path.lstat()
        mode = stat.S_IMODE(
            path_stat.st_mode
        )

        if path.is_symlink():
            snapshot[relative_path] = (
                "symlink",
                str(path.readlink()),
                mode,
            )
        elif path.is_dir():
            snapshot[relative_path] = (
                "directory",
                None,
                mode,
            )
        else:
            snapshot[relative_path] = (
                "file",
                path.read_bytes(),
                mode,
            )

    return snapshot


def generate_project(
    registry,
    manifest,
    output_path,
):
    generator = ProjectGenerator(registry)
    plan = generator.plan(
        manifest=manifest,
        output_path=output_path,
    )

    assert plan.desired_state is not None

    generator.execute(plan)

    return plan


def test_status_command_options_are_available():
    result = runner.invoke(
        cli.app,
        [
            "status",
            "--help",
        ],
    )

    plain_output = Text.from_ansi(
        result.output
    ).plain

    assert result.exit_code == 0
    assert "--json" in plain_output
    assert "--debug" in plain_output
    assert "OUTPUT_PATH" in plain_output


def test_status_json_is_exhaustive_and_read_only(
    registry,
    manifest,
    tmp_path,
):
    output_path = tmp_path / "output"

    plan = generate_project(
        registry,
        manifest,
        output_path,
    )

    assert plan.desired_state is not None
    assert plan.desired_state.resources

    managed_resource = (
        plan.desired_state.resources[0]
    )
    managed_path = (
        output_path
        / managed_resource.materialized_path
    )

    managed_path.write_bytes(
        b"locally modified"
    )
    (
        output_path / "user-created.txt"
    ).write_bytes(b"user content")

    before = snapshot_output(
        output_path
    )

    result = runner.invoke(
        cli.app,
        [
            "status",
            str(output_path),
            "--json",
        ],
    )

    after = snapshot_output(
        output_path
    )

    assert result.exit_code == 0

    data = json.loads(result.output)

    assert data["observation"]["has_drift"] is True

    expected_observation = observe_project(
        output_path
    )

    assert expected_observation is not None

    assert data == {
        "output_path": str(output_path),
        "pending_transaction": False,
        "observation": (
            expected_observation.to_dict()
        ),
    }
    assert after == before
    assert ".boilr/state.json" not in json.dumps(
        data["observation"]
    )


def test_status_human_output_reports_drift(
    registry,
    manifest,
    tmp_path,
):
    output_path = tmp_path / "output"

    plan = generate_project(
        registry,
        manifest,
        output_path,
    )

    assert plan.desired_state is not None

    managed_resource = (
        plan.desired_state.resources[0]
    )
    managed_path = (
        output_path
        / managed_resource.materialized_path
    )
    managed_path.write_bytes(
        b"locally modified"
    )

    before = snapshot_output(
        output_path
    )

    result = runner.invoke(
        cli.app,
        [
            "status",
            str(output_path),
        ],
    )

    plain_output = Text.from_ansi(
        result.output
    ).plain

    assert result.exit_code == 0
    assert "Boilr project status" in plain_output
    assert "Drift" in plain_output
    assert "Yes" in plain_output
    assert "Pending transaction" in plain_output
    assert "Resource summary" in plain_output
    assert "Resource drift" in plain_output
    assert snapshot_output(
        output_path
    ) == before


def test_status_missing_state_is_read_only(
    tmp_path,
):
    output_path = tmp_path / "output"
    output_path.mkdir()

    user_file = output_path / "user.txt"
    user_file.write_bytes(
        b"user content"
    )

    before = snapshot_output(
        output_path
    )

    result = runner.invoke(
        cli.app,
        [
            "status",
            str(output_path),
            "--json",
        ],
    )

    assert result.exit_code == 1
    assert json.loads(result.output) == {
        "code": "project_state_not_found",
        "message": (
            "No committed Boilr project state "
            "was found."
        ),
        "output_path": str(output_path),
        "pending_transaction": False,
        "suggestion": (
            "Run 'boilr generate' before "
            "inspecting project status."
        ),
    }
    assert snapshot_output(
        output_path
    ) == before
    assert not (
        output_path / ".boilr"
    ).exists()


def test_status_reports_pending_without_consuming_it(
    registry,
    manifest,
    tmp_path,
):
    output_path = tmp_path / "output"

    plan = generate_project(
        registry,
        manifest,
        output_path,
    )

    assert plan.desired_state is not None

    storage = ProjectStateStorage(
        output_path
    )
    storage.begin(
        plan.desired_state
    )

    pending_bytes = (
        storage.pending_state_path.read_bytes()
    )
    before = snapshot_output(
        output_path
    )

    result = runner.invoke(
        cli.app,
        [
            "status",
            str(output_path),
            "--json",
        ],
    )

    assert result.exit_code == 0

    data = json.loads(result.output)

    assert data[
        "pending_transaction"
    ] is True
    assert (
        storage.pending_state_path.read_bytes()
        == pending_bytes
    )
    assert storage.read_pending() == (
        plan.desired_state
    )
    assert snapshot_output(
        output_path
    ) == before