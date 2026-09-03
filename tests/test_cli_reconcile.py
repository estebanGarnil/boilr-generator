import json
from pathlib import Path

import pytest
from rich.text import Text
from typer.testing import CliRunner

import boilr_generator.cli as cli
from boilr_generator.generation import (
    ProjectGenerator,
    observe_project,
)
from boilr_generator.generation.filesystem import (
    capture_output_state,
)
from boilr_generator.state import ProjectStateStorage

runner = CliRunner()


def _snapshot_output(
    output_path: Path,
) -> dict[str, tuple]:
    """Capture all project and internal-state paths."""
    if not output_path.exists():
        return {}

    snapshot: dict[str, tuple] = {}

    for path in sorted(
        output_path.rglob("*"),
        key=lambda item: item.as_posix(),
    ):
        relative_path = path.relative_to(
            output_path
        ).as_posix()

        if path.is_symlink():
            snapshot[relative_path] = (
                "symlink",
                str(path.readlink()),
            )
        elif path.is_dir():
            snapshot[relative_path] = (
                "directory",
            )
        else:
            snapshot[relative_path] = (
                "file",
                path.read_bytes(),
            )

    return snapshot


def _generated_project(
    registry,
    manifest,
    output_path: Path,
) -> ProjectStateStorage:
    generator = ProjectGenerator(registry)
    plan = generator.plan(
        manifest=manifest,
        output_path=output_path,
    )
    generator.execute(plan)

    return ProjectStateStorage(output_path)


def _project_with_moved_environment(
    registry,
    manifest,
    output_path: Path,
):
    storage = _generated_project(
        registry,
        manifest,
        output_path,
    )
    state = storage.read()

    assert state is not None

    resource = next(
        resource
        for resource in state.resources
        if resource.materialized_path == ".env"
    )
    source_path = output_path / ".env"
    destination_path = output_path / ".env.local"
    content = source_path.read_bytes()

    source_path.rename(destination_path)

    observation = observe_project(output_path)

    assert observation is not None

    resource_observation = next(
        item
        for item in observation.resources
        if item.resource_id == resource.id
    )

    assert resource_observation.status == (
        "move_candidate"
    )
    assert resource_observation.candidate_paths == (
        ".env.local",
    )

    return storage, state, resource, content


def test_reconcile_help_exposes_explicit_move_options():
    result = runner.invoke(
        cli.app,
        [
            "reconcile",
            "--help",
        ],
    )

    assert result.exit_code == 0
    assert "--accept-move" in result.output
    assert "--dry-run" in result.output
    assert "--json" in result.output


def test_reconcile_dry_run_json_is_read_only(
    registry,
    manifest,
    tmp_path,
):
    output_path = tmp_path / "output"
    storage, state, resource, _ = (
        _project_with_moved_environment(
            registry,
            manifest,
            output_path,
        )
    )
    before = _snapshot_output(output_path)

    result = runner.invoke(
        cli.app,
        [
            "reconcile",
            str(output_path),
            "--accept-move",
            f"{resource.id}=.env.local",
            "--dry-run",
            "--json",
        ],
    )

    assert result.exit_code == 0, result.output

    data = json.loads(result.output)

    assert data["output_path"] == str(output_path)
    assert data["state_path"] == str(
        storage.state_path
    )
    assert data["dry_run"] is True
    assert data["applied"] is False
    assert data["plan"]["has_changes"] is True
    assert data["plan"]["summary"] == {
        "moves_count": 1,
    }
    assert data["plan"]["moves"] == [
        {
            "resource_id": resource.id,
            "from_path": ".env",
            "to_path": ".env.local",
            "detected_as": "move_candidate",
        }
    ]
    assert storage.read() == state
    assert not storage.pending_state_path.exists()
    assert _snapshot_output(output_path) == before


def test_reconcile_json_applies_state_without_moving_files(
    registry,
    manifest,
    tmp_path,
):
    output_path = tmp_path / "output"
    storage, state, resource, content = (
        _project_with_moved_environment(
            registry,
            manifest,
            output_path,
        )
    )
    state_bytes_before = (
        storage.state_path.read_bytes()
    )
    filesystem_before = capture_output_state(
        output_path
    )

    result = runner.invoke(
        cli.app,
        [
            "reconcile",
            str(output_path),
            "--accept-move",
            f"{resource.id}=.env.local",
            "--json",
        ],
    )

    assert result.exit_code == 0, result.output

    data = json.loads(result.output)

    assert data["dry_run"] is False
    assert data["applied"] is True
    assert data["plan"]["has_changes"] is True
    assert data["plan"]["summary"] == {
        "moves_count": 1,
    }

    updated_state = storage.read()

    assert updated_state is not None
    assert updated_state != state
    assert storage.state_path.read_bytes() != (
        state_bytes_before
    )
    assert not storage.pending_state_path.exists()

    updated_resource = next(
        item
        for item in updated_state.resources
        if item.id == resource.id
    )

    assert updated_resource.materialized_path == (
        ".env.local"
    )
    assert capture_output_state(output_path) == (
        filesystem_before
    )
    assert not (output_path / ".env").exists()
    assert (
        output_path / ".env.local"
    ).read_bytes() == content


def test_reconcile_human_output_describes_accepted_move(
    registry,
    manifest,
    tmp_path,
):
    output_path = tmp_path / "output"
    _, _, resource, _ = (
        _project_with_moved_environment(
            registry,
            manifest,
            output_path,
        )
    )
    before = _snapshot_output(output_path)

    result = runner.invoke(
        cli.app,
        [
            "reconcile",
            str(output_path),
            "--accept-move",
            f"{resource.id}=.env.local",
            "--dry-run",
        ],
    )

    plain_output = Text.from_ansi(
        result.output
    ).plain

    assert result.exit_code == 0, result.output
    assert "Boilr project reconciliation" in plain_output
    assert "Dry run" in plain_output
    assert "Yes" in plain_output
    assert "Accepted moves" in plain_output
    assert "Accepted resource moves" in plain_output
    assert resource.id in plain_output
    assert ".env" in plain_output
    assert ".env.local" in plain_output
    assert _snapshot_output(output_path) == before


def test_reconcile_without_moves_is_a_read_only_noop(
    registry,
    manifest,
    tmp_path,
):
    output_path = tmp_path / "output"
    storage = _generated_project(
        registry,
        manifest,
        output_path,
    )
    before = _snapshot_output(output_path)

    result = runner.invoke(
        cli.app,
        [
            "reconcile",
            str(output_path),
            "--json",
        ],
    )

    assert result.exit_code == 0, result.output

    data = json.loads(result.output)

    assert data["dry_run"] is False
    assert data["applied"] is False
    assert data["plan"]["has_changes"] is False
    assert data["plan"]["moves"] == []
    assert not storage.pending_state_path.exists()
    assert _snapshot_output(output_path) == before


def test_reconcile_dry_run_never_calls_application(
    registry,
    manifest,
    tmp_path,
    monkeypatch,
):
    output_path = tmp_path / "output"
    _, _, resource, _ = (
        _project_with_moved_environment(
            registry,
            manifest,
            output_path,
        )
    )
    before = _snapshot_output(output_path)

    def fail_application(*_args, **_kwargs):
        raise AssertionError(
            "A reconciliation dry-run must not be applied."
        )

    monkeypatch.setattr(
        cli,
        "apply_reconciliation_plan",
        fail_application,
    )

    result = runner.invoke(
        cli.app,
        [
            "reconcile",
            str(output_path),
            "--accept-move",
            f"{resource.id}=.env.local",
            "--dry-run",
            "--json",
        ],
    )

    assert result.exit_code == 0, result.output
    assert _snapshot_output(output_path) == before


@pytest.mark.parametrize(
    "accepted_moves",
    [
        ["invalid"],
        ["=.env.local"],
        ["resource="],
        [
            "resource=.env.local",
            "resource=.env.backup",
        ],
    ],
)
def test_reconcile_rejects_invalid_move_syntax_without_writes(
    registry,
    manifest,
    tmp_path,
    accepted_moves,
):
    output_path = tmp_path / "output"
    _generated_project(
        registry,
        manifest,
        output_path,
    )
    before = _snapshot_output(output_path)
    arguments = [
        "reconcile",
        str(output_path),
        "--json",
    ]

    for accepted_move in accepted_moves:
        arguments.extend(
            [
                "--accept-move",
                accepted_move,
            ]
        )

    result = runner.invoke(
        cli.app,
        arguments,
    )

    assert result.exit_code == 1

    data = json.loads(result.output)

    assert data["code"] == (
        "invalid_reconciliation_request"
    )
    assert data["output_path"] == str(output_path)
    assert _snapshot_output(output_path) == before


def test_reconcile_rejects_unknown_resource_without_writes(
    registry,
    manifest,
    tmp_path,
):
    output_path = tmp_path / "output"
    _project_with_moved_environment(
        registry,
        manifest,
        output_path,
    )
    before = _snapshot_output(output_path)

    result = runner.invoke(
        cli.app,
        [
            "reconcile",
            str(output_path),
            "--accept-move",
            "unknown-resource=.env.local",
            "--json",
        ],
    )

    assert result.exit_code == 1

    data = json.loads(result.output)

    assert data["code"] == (
        "invalid_reconciliation_request"
    )
    assert _snapshot_output(output_path) == before


def test_reconcile_reports_missing_project_state_as_json(
    tmp_path,
):
    output_path = tmp_path / "missing-output"

    result = runner.invoke(
        cli.app,
        [
            "reconcile",
            str(output_path),
            "--accept-move",
            "resource=elsewhere.txt",
            "--json",
        ],
    )

    assert result.exit_code == 1

    data = json.loads(result.output)

    assert data == {
        "code": "project_state_not_found",
        "message": (
            "No committed Boilr project state was found."
        ),
        "output_path": str(output_path),
        "suggestion": (
            "Run 'boilr generate' before reconciling "
            "project resources."
        ),
    }
    assert not output_path.exists()


def test_reconcile_existing_pending_is_preserved(
    registry,
    manifest,
    tmp_path,
):
    output_path = tmp_path / "output"
    storage, state, resource, _ = (
        _project_with_moved_environment(
            registry,
            manifest,
            output_path,
        )
    )
    storage.begin(state)

    before = _snapshot_output(output_path)

    result = runner.invoke(
        cli.app,
        [
            "reconcile",
            str(output_path),
            "--accept-move",
            f"{resource.id}=.env.local",
            "--json",
        ],
    )

    assert result.exit_code == 1

    data = json.loads(result.output)

    assert data["code"] == "state_transaction_error"
    assert storage.read() == state
    assert storage.read_pending() == state
    assert _snapshot_output(output_path) == before