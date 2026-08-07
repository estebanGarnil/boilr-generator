import pytest
from boilr_generator.exceptions import (
    DockerConflictError,
    TemplateRenderError,
)
from boilr_generator.generation.docker import DockerComposeGenerator
from boilr_generator.modules.schemas import DockerService


def test_docker_generator_returns_compose_dict(resolved_project):
    compose = DockerComposeGenerator().generate(resolved_project)

    assert isinstance(compose, dict)
    assert "services" in compose


def test_docker_generator_contains_postgres_service(resolved_project):
    compose = DockerComposeGenerator().generate(resolved_project)

    assert "db" in compose["services"]
    assert compose["services"]["db"]["image"] == "postgres:16"


def test_docker_generator_renders_postgres_port(resolved_project):
    compose = DockerComposeGenerator().generate(resolved_project)

    assert "5432:5432" in compose["services"]["db"]["ports"]


def test_docker_generator_contains_volumes(resolved_project):
    compose = DockerComposeGenerator().generate(resolved_project)

    assert "volumes" in compose
    assert "postgres_data" in compose["volumes"]


def test_docker_generator_accepts_identical_service_definitions(
    resolved_project,
):
    generator = DockerComposeGenerator()

    baseline_compose = generator.generate(
        resolved_project
    )

    project = resolved_project.model_copy(deep=True)
    django = project.get_module("django")

    assert django is not None
    assert django.manifest.docker is not None

    django.manifest.docker.services["db"] = (
        DockerService.model_validate(
            baseline_compose["services"]["db"]
        )
    )

    compose = generator.generate(project)

    assert compose["services"]["db"] == (
        baseline_compose["services"]["db"]
    )


def test_docker_generator_rejects_conflicting_services(
    resolved_project,
):
    project = resolved_project.model_copy(deep=True)
    django = project.get_module("django")

    assert django is not None
    assert django.manifest.docker is not None

    django.manifest.docker.services["db"] = DockerService.model_validate(
        {"image": "mysql:8"}
    )

    with pytest.raises(DockerConflictError) as error_info:
        DockerComposeGenerator().generate(project)

    error = error_info.value

    assert error.code == "docker_conflict"
    assert error.module_key == "django"
    assert error.field_path == "modules.django.docker.services.db"
    assert error.context["service"] == "db"
    assert error.context["first_module"] == "postgres"
    assert error.context["conflicting_module"] == "django"


def test_docker_generator_reports_template_render_errors(
    resolved_project,
):
    project = resolved_project.model_copy(deep=True)
    postgres = project.get_module("postgres")

    assert postgres is not None
    assert postgres.manifest.docker is not None

    postgres.manifest.docker.services["db"].root["image"] = (
        "{{ missing_image }}"
    )

    with pytest.raises(TemplateRenderError) as error_info:
        DockerComposeGenerator().generate(project)

    error = error_info.value

    assert error.code == "template_render_error"
    assert error.module_key == "postgres"
    assert error.field_path == "modules.postgres.docker.services.db.image"
    assert error.context["target"] == "docker"
    assert error.context["error_type"] == "UndefinedError"

def test_docker_generator_omits_obsolete_version(
    resolved_project,
):
    compose = DockerComposeGenerator().generate(
        resolved_project
    )

    assert "version" not in compose