import os

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