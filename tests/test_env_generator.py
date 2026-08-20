import pytest
from boilr_generator.exceptions import (
    EnvironmentConflictError,
    InvalidEnvironmentVariableError,
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
    assert error.context == {
        "variable": "DB_HOST",
        "first_module": "postgres",
        "conflicting_module": "django",
    }
    assert error.suggestion is not None


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

@pytest.mark.parametrize(
    "variable_name",
    [
        "",
        "1INVALID",
        "INVALID-NAME",
        "INVALID=NAME",
    ],
)
def test_env_generator_rejects_invalid_variable_name(
    resolved_project,
    variable_name,
):
    project = resolved_project.model_copy(deep=True)
    postgres = project.get_module("postgres")

    assert postgres is not None
    assert postgres.manifest.exports is not None
    assert postgres.manifest.exports.env is not None

    postgres.manifest.exports.env.root[
        variable_name
    ] = "value"

    with pytest.raises(
        InvalidEnvironmentVariableError
    ) as error_info:
        EnvGenerator().generate(project)

    error = error_info.value

    assert error.code == "invalid_environment_variable"
    assert error.module_key == "postgres"
    assert error.context["reason"] == "invalid_name"
    assert error.context["variable"] == variable_name
    assert "expected_pattern" in error.context
    assert error.suggestion is not None


@pytest.mark.parametrize(
    ("invalid_value", "expected_character"),
    [
        ("first\nsecond", "line_feed"),
        ("first\rsecond", "line_feed"),
        ("first\x00second", "null_byte"),
    ],
)
def test_env_generator_rejects_unsafe_value(
    resolved_project,
    invalid_value,
    expected_character,
):
    project = resolved_project.model_copy(deep=True)
    postgres = project.get_module("postgres")

    assert postgres is not None
    assert postgres.manifest.exports is not None
    assert postgres.manifest.exports.env is not None

    postgres.manifest.exports.env.root[
        "UNSAFE_VALUE"
    ] = invalid_value

    with pytest.raises(
        InvalidEnvironmentVariableError
    ) as error_info:
        EnvGenerator().generate(project)

    error = error_info.value

    assert error.context["reason"] == "invalid_value"
    assert error.context["variable"] == "UNSAFE_VALUE"
    assert expected_character in (
        error.context["invalid_characters"]
    )
    assert "value" not in error.context


@pytest.mark.parametrize(
    ("injected_value", "expected_character"),
    [
        (
            "password\nINJECTED_VARIABLE=true",
            "line_feed",
        ),
        (
            "password\rINJECTED_VARIABLE=true",
            "carriage_return",
        ),
    ],
)
def test_env_generator_rejects_rendered_line_injection(
    resolved_project,
    injected_value,
    expected_character,
):
    project = resolved_project.model_copy(deep=True)
    postgres = project.get_module("postgres")

    assert postgres is not None

    postgres.variables["db_password"] = injected_value

    with pytest.raises(
        InvalidEnvironmentVariableError
    ) as error_info:
        EnvGenerator().generate(project)

    error = error_info.value

    assert error.module_key == "postgres"
    assert error.context["variable"] == "DB_PASSWORD"
    assert expected_character in (
        error.context["invalid_characters"]
    )
    assert "password" not in str(error.context)

def test_env_generator_accepts_empty_value(
    resolved_project,
):
    project = resolved_project.model_copy(deep=True)
    postgres = project.get_module("postgres")

    assert postgres is not None
    assert postgres.manifest.exports is not None
    assert postgres.manifest.exports.env is not None

    postgres.manifest.exports.env.root[
        "EMPTY_VALUE"
    ] = ""

    env = EnvGenerator().generate(project)

    assert env["EMPTY_VALUE"] == ""