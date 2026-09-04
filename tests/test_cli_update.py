import json
import stat
from pathlib import Path

from rich.text import Text
from typer.testing import CliRunner

import boilr_generator.cli as cli
from boilr_generator.generation import (
    ProjectGenerator,
)
from boilr_generator.state import ProjectStateStorage

runner = CliRunner()


def _snapshot_output(
    output_path: Path,
) -> dict[str, tuple]:
    """Capture project contents, modes, and internal state."""
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
        mode = stat.S_IMODE(
            path.lstat().st_mode
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
                mode,
            )
        else:
            snapshot[relative_path] = (
                "file",
                path.read_bytes(),
                mode,
            )

    return snapshot


def _generated_project(
    registry,
    manifest,
    output_path: Path,
):
    generator = ProjectGenerator(registry)
    plan = generator.plan(
        manifest=manifest,
        output_path=output_path,
    )
    generator.execute(plan)

    storage = ProjectStateStorage(output_path)
    state = storage.read()

    assert state is not None

    return generator, storage, state


def _configure_cli(
    monkeypatch,
    generator,
    manifest,
) -> None:
    monkeypatch.setattr(
        cli,
        "load_project_manifest_from_yaml",
        lambda _: manifest,
    )
    monkeypatch.setattr(
        cli,
        "build_generator",
        lambda: generator,
    )


def _configure_environment_update(
    monkeypatch,
    generator,
    content: bytes = b"UPDATED=value\n",
) -> None:
    original_plan = generator.plan

    def plan_with_updated_environment(
        *args,
        **kwargs,
    ):
        candidate_plan = original_plan(
            *args,
            **kwargs,
        )
        environment_file = next(
            planned_file
            for planned_file
            in candidate_plan.files
            if planned_file.relative_destination_path
            == ".env"
        )
        environment_file.content = content
        return candidate_plan

    monkeypatch.setattr(
        generator,
        "plan",
        plan_with_updated_environment,
    )


def test_update_help_exposes_safe_update_options():
    result = runner.invoke(
        cli.app,
        [
            "update",
            "--help",
        ],
    )

    assert result.exit_code == 0
    assert "--dry-run" in result.output
    assert "--info" in result.output
    assert "--json" in result.output
    assert "--debug" in result.output
    assert "--clean" not in result.output


def test_update_dry_run_json_is_strictly_read_only(
    registry,
    manifest,
    tmp_path,
    monkeypatch,
):
    output_path = tmp_path / "output"
    generator, storage, current_state = (
        _generated_project(
            registry,
            manifest,
            output_path,
        )
    )
    _configure_cli(
        monkeypatch,
        generator,
        manifest,
    )
    _configure_environment_update(
        monkeypatch,
        generator,
    )
    before = _snapshot_output(output_path)

    result = runner.invoke(
        cli.app,
        [
            "update",
            str(tmp_path / "project.yml"),
            str(output_path),
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
    assert data["ready"] is True
    assert data["applied"] is False
    assert data["pending_transaction"] is False
    assert data["plan"]["can_execute"] is True
    assert data["plan"]["has_changes"] is True
    assert data["plan"][
        "has_filesystem_changes"
    ] is True
    assert data["plan"]["summary"][
        "replace_count"
    ] == 1
    assert data["plan"]["execution_plan"][
        "clean_output"
    ] is False
    assert storage.read() == current_state
    assert not storage.pending_state_path.exists()
    assert _snapshot_output(output_path) == before


def test_update_dry_run_never_calls_execution(
    registry,
    manifest,
    tmp_path,
    monkeypatch,
):
    output_path = tmp_path / "output"
    generator, _, _ = _generated_project(
        registry,
        manifest,
        output_path,
    )
    _configure_cli(
        monkeypatch,
        generator,
        manifest,
    )
    _configure_environment_update(
        monkeypatch,
        generator,
    )

    def fail_execution(_update_plan):
        raise AssertionError(
            "An update dry-run must never be executed."
        )

    monkeypatch.setattr(
        generator,
        "execute_update",
        fail_execution,
    )
    before = _snapshot_output(output_path)

    result = runner.invoke(
        cli.app,
        [
            "update",
            str(tmp_path / "project.yml"),
            str(output_path),
            "--dry-run",
            "--json",
        ],
    )

    assert result.exit_code == 0, result.output
    assert _snapshot_output(output_path) == before


def test_update_json_applies_safe_replacement(
    registry,
    manifest,
    tmp_path,
    monkeypatch,
):
    output_path = tmp_path / "output"
    generator, storage, current_state = (
        _generated_project(
            registry,
            manifest,
            output_path,
        )
    )
    _configure_cli(
        monkeypatch,
        generator,
        manifest,
    )
    _configure_environment_update(
        monkeypatch,
        generator,
    )

    result = runner.invoke(
        cli.app,
        [
            "update",
            str(tmp_path / "project.yml"),
            str(output_path),
            "--json",
        ],
    )

    assert result.exit_code == 0, result.output

    data = json.loads(result.output)
    updated_state = storage.read()

    assert updated_state is not None
    assert updated_state != current_state
    assert data["dry_run"] is False
    assert data["ready"] is True
    assert data["applied"] is True
    assert data["pending_transaction"] is False
    assert (output_path / ".env").read_bytes() == (
        b"UPDATED=value\n"
    )
    assert updated_state.model_dump(
        mode="json"
    ) == data["plan"]["desired_state"]
    assert not storage.pending_state_path.exists()


def test_update_noop_does_not_rewrite_project(
    registry,
    manifest,
    tmp_path,
    monkeypatch,
):
    output_path = tmp_path / "output"
    generator, storage, current_state = (
        _generated_project(
            registry,
            manifest,
            output_path,
        )
    )
    _configure_cli(
        monkeypatch,
        generator,
        manifest,
    )
    before = _snapshot_output(output_path)

    result = runner.invoke(
        cli.app,
        [
            "update",
            str(tmp_path / "project.yml"),
            str(output_path),
            "--json",
        ],
    )

    assert result.exit_code == 0, result.output

    data = json.loads(result.output)

    assert data["dry_run"] is False
    assert data["ready"] is True
    assert data["applied"] is False
    assert data["plan"]["has_changes"] is False
    assert data["plan"]["execution_plan"][
        "files"
    ] == []
    assert data["plan"]["execution_plan"][
        "removals"
    ] == []
    assert storage.read() == current_state
    assert _snapshot_output(output_path) == before


def test_update_human_output_describes_exact_plan(
    registry,
    manifest,
    tmp_path,
    monkeypatch,
):
    output_path = tmp_path / "output"
    generator, _, _ = _generated_project(
        registry,
        manifest,
        output_path,
    )
    _configure_cli(
        monkeypatch,
        generator,
        manifest,
    )
    _configure_environment_update(
        monkeypatch,
        generator,
    )
    before = _snapshot_output(output_path)

    result = runner.invoke(
        cli.app,
        [
            "update",
            str(tmp_path / "project.yml"),
            str(output_path),
            "--dry-run",
            "--info",
        ],
    )
    plain_output = Text.from_ansi(
        result.output
    ).plain

    assert result.exit_code == 0, result.output
    assert "Boilr project update" in plain_output
    assert "Dry run" in plain_output
    assert "Ready" in plain_output
    assert "Update summary" in plain_output
    assert "Resource transitions" in plain_output
    assert "replace" in plain_output
    assert ".env" in plain_output
    assert "Filesystem operations" in plain_output
    assert "Planned files" in plain_output
    assert _snapshot_output(output_path) == before


def test_update_conflict_dry_run_reports_without_writes(
    registry,
    manifest,
    tmp_path,
    monkeypatch,
):
    output_path = tmp_path / "output"
    generator, storage, current_state = (
        _generated_project(
            registry,
            manifest,
            output_path,
        )
    )
    (output_path / ".env").write_bytes(
        b"LOCAL=value\n"
    )
    _configure_cli(
        monkeypatch,
        generator,
        manifest,
    )
    _configure_environment_update(
        monkeypatch,
        generator,
        b"DESIRED=value\n",
    )
    before = _snapshot_output(output_path)

    result = runner.invoke(
        cli.app,
        [
            "update",
            str(tmp_path / "project.yml"),
            str(output_path),
            "--dry-run",
            "--json",
        ],
    )

    assert result.exit_code == 0, result.output

    data = json.loads(result.output)

    assert data["ready"] is False
    assert data["applied"] is False
    assert data["plan"]["can_execute"] is False
    assert data["plan"]["execution_plan"] is None
    assert any(
        conflict["reason"] == "modified_resource"
        and conflict["path"] == ".env"
        for conflict in data["plan"]["conflicts"]
    )
    assert storage.read() == current_state
    assert not storage.pending_state_path.exists()
    assert _snapshot_output(output_path) == before


def test_update_conflict_application_is_rejected(
    registry,
    manifest,
    tmp_path,
    monkeypatch,
):
    output_path = tmp_path / "output"
    generator, storage, current_state = (
        _generated_project(
            registry,
            manifest,
            output_path,
        )
    )
    (output_path / ".env").write_bytes(
        b"LOCAL=value\n"
    )
    _configure_cli(
        monkeypatch,
        generator,
        manifest,
    )
    _configure_environment_update(
        monkeypatch,
        generator,
        b"DESIRED=value\n",
    )
    before = _snapshot_output(output_path)

    result = runner.invoke(
        cli.app,
        [
            "update",
            str(tmp_path / "project.yml"),
            str(output_path),
            "--json",
        ],
    )

    assert result.exit_code == 1

    data = json.loads(result.output)

    assert data["context"]["reason"] == (
        "update_conflicts"
    )
    assert storage.read() == current_state
    assert not storage.pending_state_path.exists()
    assert _snapshot_output(output_path) == before


def test_update_missing_state_is_reported_without_creation(
    manifest,
    tmp_path,
    monkeypatch,
):
    output_path = tmp_path / "missing-output"

    monkeypatch.setattr(
        cli,
        "load_project_manifest_from_yaml",
        lambda _: manifest,
    )

    result = runner.invoke(
        cli.app,
        [
            "update",
            str(tmp_path / "project.yml"),
            str(output_path),
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
            "Run 'boilr generate' before updating "
            "the project."
        ),
    }
    assert not output_path.exists()


def test_update_pending_dry_run_is_read_only_and_not_ready(
    registry,
    manifest,
    tmp_path,
    monkeypatch,
):
    output_path = tmp_path / "output"
    generator, storage, current_state = (
        _generated_project(
            registry,
            manifest,
            output_path,
        )
    )
    storage.begin(current_state)
    _configure_cli(
        monkeypatch,
        generator,
        manifest,
    )
    before = _snapshot_output(output_path)

    result = runner.invoke(
        cli.app,
        [
            "update",
            str(tmp_path / "project.yml"),
            str(output_path),
            "--dry-run",
            "--json",
        ],
    )

    assert result.exit_code == 0, result.output

    data = json.loads(result.output)

    assert data["pending_transaction"] is True
    assert data["ready"] is False
    assert data["applied"] is False
    assert data["plan"]["can_execute"] is True
    assert storage.read() == current_state
    assert storage.read_pending() == current_state
    assert _snapshot_output(output_path) == before


def test_update_pending_application_is_rejected(
    registry,
    manifest,
    tmp_path,
    monkeypatch,
):
    output_path = tmp_path / "output"
    generator, storage, current_state = (
        _generated_project(
            registry,
            manifest,
            output_path,
        )
    )
    storage.begin(current_state)
    _configure_cli(
        monkeypatch,
        generator,
        manifest,
    )
    before = _snapshot_output(output_path)

    result = runner.invoke(
        cli.app,
        [
            "update",
            str(tmp_path / "project.yml"),
            str(output_path),
            "--json",
        ],
    )

    assert result.exit_code == 1

    data = json.loads(result.output)

    assert data["code"] == "state_transaction_error"
    assert data["context"]["reason"] == (
        "pending_state_exists"
    )
    assert storage.read() == current_state
    assert storage.read_pending() == current_state
    assert _snapshot_output(output_path) == before