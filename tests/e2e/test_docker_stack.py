import json
import os
import time
import urllib.request

import pytest

RUN_DOCKER_E2E = (
    os.getenv("BOILR_RUN_DOCKER_E2E") == "1"
)

pytestmark = [
    pytest.mark.docker_e2e,
    pytest.mark.skipif(
        not RUN_DOCKER_E2E,
        reason=(
            "Set BOILR_RUN_DOCKER_E2E=1 "
            "to run Docker E2E tests."
        ),
    ),
]


def wait_for_health(
    url: str,
    timeout: float,
) -> dict[str, str]:
    """Wait until the generated backend answers successfully."""
    deadline = time.monotonic() + timeout
    last_error: Exception | None = None

    while time.monotonic() < deadline:
        try:
            with urllib.request.urlopen(
                url,
                timeout=5,
            ) as response:
                if response.status == 200:
                    return json.loads(
                        response.read().decode(
                            "utf-8"
                        )
                    )

                last_error = RuntimeError(
                    "Unexpected HTTP status: "
                    f"{response.status}"
                )
        except (
            OSError,
            json.JSONDecodeError,
        ) as error:
            last_error = error

        time.sleep(1)

    raise AssertionError(
        "The generated backend did not become healthy "
        f"within {timeout} seconds. "
        f"Last error: {last_error!r}"
    )


def test_generated_compose_configuration_is_valid(
    docker_compose_project,
):
    docker_compose_project.run(
        "config",
        "--quiet",
        timeout=60,
    )


def test_generated_backend_image_builds(
    docker_compose_project,
):
    docker_compose_project.run(
        "build",
        timeout=900,
    )


def test_generated_stack_starts_and_serves_health(
    docker_compose_project,
):
    docker_compose_project.run(
        "up",
        "--detach",
        "--build",
        timeout=900,
    )

    try:
        health = wait_for_health(
            "http://127.0.0.1:8000/api/health/",
            timeout=120,
        )
    except AssertionError as error:
        pytest.fail(
            f"{error}\n\n"
            f"{docker_compose_project.diagnostics()}",
            pytrace=False,
        )

    assert health == {
        "status": "ok",
        "message": "Django backend is running",
    }

    running_services = {
        service.strip()
        for service in docker_compose_project.run(
            "ps",
            "--services",
            "--status",
            "running",
            timeout=30,
        ).stdout.splitlines()
        if service.strip()
    }

    assert running_services == {
        "backend",
        "db",
    }

    database_readiness = (
        docker_compose_project.run(
            "exec",
            "-T",
            "db",
            "pg_isready",
            "-U",
            "docker_e2e",
            "-d",
            "docker_e2e",
            timeout=30,
        )
    )

    assert (
        "accepting connections"
        in database_readiness.stdout
    )

    docker_compose_project.run(
        "exec",
        "-T",
        "backend",
        "python",
        "manage.py",
        "migrate",
        "--check",
        timeout=60,
    )