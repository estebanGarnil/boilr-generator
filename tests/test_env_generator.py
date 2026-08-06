import pytest
from boilr_generator.exceptions import (
    EnvironmentConflictError,
    TemplateRenderError,
)
from boilr_generator.generation.env import EnvGenerator


def test_env_generator_returns_dict(resolved_project):
    env = EnvGenerator().generate(resolved_project)

    assert isinstance(env, dict)


def test_env_generator_contains_database_values(resolved_project):
    env = EnvGenerator().generate(resolved_project)

    assert env["DB_ENGINE"] == "postgresql"
    assert env["DB_HOST"] == "db"
    assert env["DB_NAME"] == "my_app"
    assert env["DB_USER"] == "my_app"
    assert env["DB_PASSWORD"] == "password"
    assert env["DB_PORT"] == "5432"


def test_env_generator_values_are_strings(resolved_project):
    env = EnvGenerator().generate(resolved_project)

    for value in env.values():
        assert isinstance(value, str)


def test_env_generator_accepts_identical_exports(resolved_project):
    env = EnvGenerator().generate(resolved_project)

    assert env["DB_HOST"] == "db"
    assert env["DB_NAME"] == "my_app"


def test_env_generator_rejects_conflicting_exports(
    resolved_project,
):
    project = resolved_project.model_copy(deep=True)
    django = project.get_module("django")

    assert django is not None
    assert django.manifest.exports is not None
    assert django.manifest.exports.env is not None

    django.manifest.exports.env.root["DB_HOST"] = "another-database"

    with pytest.raises(EnvironmentConflictError) as error_info:
        EnvGenerator().generate(project)

    error = error_info.value

    assert error.code == "environment_conflict"
    assert error.module_key == "django"
    assert error.field_path == "modules.django.exports.env.DB_HOST"
    assert error.context["variable"] == "DB_HOST"
    assert error.context["first_module"] == "postgres"
    assert error.context["conflicting_module"] == "django"


def test_env_generator_reports_template_render_errors(
    resolved_project,
):
    project = resolved_project.model_copy(deep=True)
    postgres = project.get_module("postgres")

    assert postgres is not None
    assert postgres.manifest.exports is not None
    assert postgres.manifest.exports.env is not None

    postgres.manifest.exports.env.root["BROKEN"] = (
        "{{ missing_environment_value }}"
    )

    with pytest.raises(TemplateRenderError) as error_info:
        EnvGenerator().generate(project)

    error = error_info.value

    assert error.code == "template_render_error"
    assert error.module_key == "postgres"
    assert error.field_path == "modules.postgres.exports.env.BROKEN"
    assert error.context["target"] == "environment"
    assert error.context["error_type"] == "UndefinedError"