import subprocess
import sys
from collections.abc import Iterator
from pathlib import Path
from uuid import uuid4

import pytest


class DockerComposeRunner:
    """Run Docker Compose for one isolated generated project."""

    def __init__(
        self,
        project_path: Path,
    ) -> None:
        self.project_path = project_path
        self.project_name = (
            f"boilr-e2e-{uuid4().hex[:12]}"
        )

    def run(
        self,
        *arguments: str,
        timeout: int = 900,
        require_success: bool = True,
    ) -> subprocess.CompletedProcess[str]:
        """Run one Docker Compose command and require success."""
        command = [
            "docker",
            "compose",
            "--project-name",
            self.project_name,
            *arguments,
        ]

        try:
            result = subprocess.run(
                command,
                cwd=self.project_path,
                capture_output=True,
                encoding="utf-8",
                errors="replace",
                check=False,
                timeout=timeout,
            )
        except FileNotFoundError:
            pytest.fail(
                "Docker CLI is not installed or is not "
                "available in PATH.",
                pytrace=False,
            )
        except subprocess.TimeoutExpired:
            pytest.fail(
                "Docker Compose command timed out after "
                f"{timeout} seconds: {' '.join(command)}",
                pytrace=False,
            )

        if require_success:
            assert result.returncode == 0, (
                "Docker Compose command failed.\n"
                f"Command: {' '.join(command)}\n"
                f"Exit code: {result.returncode}\n"
                f"stdout:\n{result.stdout}\n"
                f"stderr:\n{result.stderr}"
            )

        return result

    def diagnostics(self) -> str:
        """Return service state and logs for a failed stack."""
        status = self.run(
            "ps",
            "--all",
            timeout=30,
            require_success=False,
        )
        logs = self.run(
            "logs",
            "--no-color",
            timeout=60,
            require_success=False,
        )

        return (
            "Docker Compose status:\n"
            f"{status.stdout}\n"
            f"{status.stderr}\n"
            "Docker Compose logs:\n"
            f"{logs.stdout}\n"
            f"{logs.stderr}"
        )

    def cleanup(self) -> None:
        """Remove resources created for this Compose project."""
        self.run(
            "down",
            "--volumes",
            "--remove-orphans",
            "--rmi",
            "local",
            timeout=120,
        )


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
        encoding="utf-8",
        errors="replace",
        check=False,
    )

    assert result.returncode == 0, (
        "E2E project generation failed.\n"
        f"stdout:\n{result.stdout}\n"
        f"stderr:\n{result.stderr}"
    )

    return output_path


@pytest.fixture
def docker_compose_project(
    generated_e2e_project: Path,
) -> Iterator[DockerComposeRunner]:
    """Provide an isolated Compose project and clean it afterward."""
    runner = DockerComposeRunner(
        generated_e2e_project
    )

    runner.run(
        "version",
        timeout=30,
    )

    try:
        yield runner
    finally:
        runner.cleanup()