import json
from pathlib import Path

import pytest
from boilr_generator import cli
from boilr_generator.exceptions import ManifestNotFoundError
from typer.testing import CliRunner

runner = CliRunner()

def snapshot_output(
    output_path: Path,
) -> dict[str, bytes | None]:
    """Capture output paths and exact file contents."""
    if not output_path.exists():
        return {}

    snapshot: dict[str, bytes | None] = {
        ".": None,
    }

    for path in sorted(
        output_path.rglob("*")
    ):
        relative_path = path.relative_to(
            output_path
        ).as_posix()

        snapshot[relative_path] = (
            None
            if path.is_dir()
            else path.read_bytes()
        )

    return snapshot

def test_dry_run_clean_option_is_available():
    result = runner.invoke(
        cli.app,
        [
            "dry-run",
            "--help",
        ],
    )

    assert result.exit_code == 0
    assert "--clean" in result.output

def test_dry_run_clean_json_is_exhaustive_and_immutable(
    registry,
    manifest,
    tmp_path,
    monkeypatch,
):
    output_path = tmp_path / "output"
    output_path.mkdir()

    existing_file = output_path / "existing.txt"
    existing_file.write_bytes(b"keep")

    generator = cli.ProjectGenerator(registry)

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

    def fail_execute(*args, **kwargs):
        raise AssertionError(
            "Dry-run must never execute its plan."
        )

    monkeypatch.setattr(
        generator,
        "execute",
        fail_execute,
    )

    before = snapshot_output(output_path)

    result = runner.invoke(
        cli.app,
        [
            "dry-run",
            str(tmp_path / "project.yml"),
            str(output_path),
            "--clean",
            "--json",
        ],
    )

    assert result.exit_code == 0

    data = json.loads(result.output)

    assert data["clean_output"] is True
    assert data["output_path"] == str(
        output_path
    )

    assert {
        removal["relative_path"]
        for removal in data["removals"]
    } == {
        ".",
        "existing.txt",
    }
    assert all(
        removal["reason"] == "clean"
        for removal in data["removals"]
    )
    assert {
        removal["kind"]
        for removal in data["removals"]
    } == {
        "directory",
        "file",
    }

    assert data["directories"]
    assert data["directories"][0][
        "relative_path"
    ] == "."

    assert data["initial_output_state"]
    assert data["summary"][
        "initial_paths_count"
    ] == len(data["initial_output_state"])
    assert data["summary"][
        "directories_to_create"
    ] == len(data["directories"])
    assert data["summary"][
        "removals_count"
    ] == len(data["removals"])
    assert data["summary"][
        "clean_removals_count"
    ] == len(data["removals"])
    assert data["summary"][
        "content_bytes_to_write"
    ] > 0

    serialized_files = {
        file["relative_destination_path"]: file
        for file in data["files"]
    }

    for relative_path in [
        ".env",
        "docker-compose.yml",
    ]:
        serialized_file = serialized_files[
            relative_path
        ]

        assert "content" not in serialized_file
        assert serialized_file[
            "destination_path"
        ]
        assert serialized_file[
            "operation"
        ] == "generate"
        assert serialized_file[
            "action"
        ] == "create"
        assert serialized_file[
            "content_size"
        ] > 0
        assert len(
            serialized_file[
                "content_sha256"
            ]
        ) == 64

    assert snapshot_output(output_path) == before

def test_dry_run_info_displays_filesystem_operations(
    registry,
    manifest,
    tmp_path,
    monkeypatch,
):
    output_path = tmp_path / "output"
    output_path.mkdir()

    existing_file = output_path / "existing.txt"
    existing_file.write_bytes(b"keep")

    generator = cli.ProjectGenerator(registry)

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

    before = snapshot_output(output_path)

    result = runner.invoke(
        cli.app,
        [
            "dry-run",
            str(tmp_path / "project.yml"),
            str(output_path),
            "--clean",
            "--info",
        ],
    )

    assert result.exit_code == 0
    assert "Clean output" in result.output
    assert "Yes" in result.output
    assert "Filesystem operations" in result.output
    assert "Remove file" in result.output
    assert "existing.txt" in result.output
    assert "Remove directory" in result.output
    assert "Create directory" in result.output
    assert "Directories" in result.output
    assert "Removals" in result.output
    assert snapshot_output(output_path) == before

def build_manifest_error() -> ManifestNotFoundError:
    return ManifestNotFoundError(
        "Project manifest not found.",
        field_path="manifest_path",
        context={
            "path": "missing.yml",
        },
        suggestion="Check the manifest path.",
    )


def test_dry_run_formats_expected_errors(
    monkeypatch,
    tmp_path,
):
    error = build_manifest_error()

    def raise_error(_: str):
        raise error

    monkeypatch.setattr(
        cli,
        "load_project_manifest_from_yaml",
        raise_error,
    )

    result = runner.invoke(
        cli.app,
        [
            "dry-run",
            str(tmp_path / "missing.yml"),
            str(tmp_path / "output"),
        ],
    )

    assert result.exit_code == 1
    assert "Boilr error" in result.output
    assert "manifest_not_found" in result.output
    assert "Project manifest not found." in result.output
    assert "manifest_path" in result.output
    assert "Check the manifest path." in result.output
    assert "Traceback" not in result.output


def test_generate_formats_expected_errors(
    monkeypatch,
    tmp_path,
):
    error = build_manifest_error()

    def raise_error(_: str):
        raise error

    monkeypatch.setattr(
        cli,
        "load_project_manifest_from_yaml",
        raise_error,
    )

    result = runner.invoke(
        cli.app,
        [
            "generate",
            str(tmp_path / "missing.yml"),
            str(tmp_path / "output"),
        ],
    )

    assert result.exit_code == 1
    assert "Boilr error" in result.output
    assert "manifest_not_found" in result.output
    assert "Project manifest not found." in result.output
    assert "Traceback" not in result.output


def test_debug_mode_reraises_expected_errors(
    monkeypatch,
    tmp_path,
):
    error = build_manifest_error()

    def raise_error(_: str):
        raise error

    monkeypatch.setattr(
        cli,
        "load_project_manifest_from_yaml",
        raise_error,
    )

    result = runner.invoke(
        cli.app,
        [
            "dry-run",
            str(tmp_path / "missing.yml"),
            str(tmp_path / "output"),
            "--debug",
        ],
    )

    assert result.exit_code == 1
    assert isinstance(
        result.exception,
        ManifestNotFoundError,
    )
    assert result.exception is error
    assert "Boilr error" not in result.output


@pytest.mark.parametrize(
    "command",
    [
        "dry-run",
        "generate",
    ],
)
def test_debug_option_is_available(
    command,
):
    result = runner.invoke(
        cli.app,
        [
            command,
            "--help",
        ],
    )

    assert result.exit_code == 0
    assert "--debug" in result.output