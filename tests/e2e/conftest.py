import subprocess
import sys
from pathlib import Path

import pytest


@pytest.fixture
def e2e_manifest_path() -> Path:
    """Return the fixed Docker E2E manifest."""
    return Path(__file__).with_name("project.yml")


@pytest.fixture
def generated_e2e_project(
    tmp_path: Path,
    e2e_manifest_path: Path,
) -> Path:
    """Generate the E2E project through the real CLI."""
    output_path = tmp_path / "generated-project"

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "boilr_generator.cli",
            "generate",
            str(e2e_manifest_path),
            str(output_path),
            "--clean",
        ],
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, (
        "E2E project generation failed.\n"
        f"stdout:\n{result.stdout}\n"
        f"stderr:\n{result.stderr}"
    )

    return output_path