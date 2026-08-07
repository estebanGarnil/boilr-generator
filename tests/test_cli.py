import pytest
from boilr_generator import cli
from boilr_generator.exceptions import ManifestNotFoundError
from typer.testing import CliRunner

runner = CliRunner()


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