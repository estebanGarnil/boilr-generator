import pytest
from boilr_generator.exceptions import (
    InvalidOptionTypeError,
    InvalidVariableTypeError,
    MissingVariableError,
    UnknownOptionError,
    UnknownVariableError,
)
from boilr_generator.manifest import load_project_manifest_from_dict
from boilr_generator.resolver import Resolver


def test_resolver_resolves_valid_project(registry, manifest):
    resolved_project = Resolver(registry).resolve(manifest)

    assert resolved_project.project.name == "my_app"
    assert resolved_project.has_module("postgres") is True
    assert resolved_project.has_module("django") is True


def test_resolver_orders_modules_by_dependency_graph(
    resolved_project,
):
    ordered_keys = [
        module.key
        for module in resolved_project.ordered_modules()
    ]

    assert ordered_keys == [
        "postgres",
        "django",
        "django-postgres",
    ]

def test_resolver_raises_when_required_variable_is_missing(
    registry,
    valid_manifest_data,
):
    django_module = next(
        module
        for module in valid_manifest_data["modules"]
        if module["key"] == "django"
    )

    del django_module["variables"]["secret_key"]

    manifest = load_project_manifest_from_dict(valid_manifest_data)

    with pytest.raises(MissingVariableError) as error_info:
        Resolver(registry).resolve(manifest)

    error = error_info.value

    assert error.code == "missing_variable"
    assert error.module_key == "django"
    assert error.field_path == "modules.django.variables.secret_key"
    assert error.context["variable"] == "secret_key"
    assert error.suggestion is not None


def test_resolver_raises_when_variable_type_is_invalid(
    registry,
    valid_manifest_data,
):
    postgres_module = next(
        module
        for module in valid_manifest_data["modules"]
        if module["key"] == "postgres"
    )

    postgres_module["variables"]["db_port"] = "5432"

    manifest = load_project_manifest_from_dict(valid_manifest_data)

    with pytest.raises(InvalidVariableTypeError) as error_info:
        Resolver(registry).resolve(manifest)

    error = error_info.value

    assert error.code == "invalid_variable_type"
    assert error.module_key == "postgres"
    assert error.field_path == "modules.postgres.variables.db_port"
    assert error.context["expected_type"] == "int"
    assert error.context["actual_type"] == "str"


def test_resolver_rejects_boolean_for_integer_variable(
    registry,
    valid_manifest_data,
):
    postgres_module = next(
        module
        for module in valid_manifest_data["modules"]
        if module["key"] == "postgres"
    )

    postgres_module["variables"]["db_port"] = True

    manifest = load_project_manifest_from_dict(valid_manifest_data)

    with pytest.raises(InvalidVariableTypeError) as error_info:
        Resolver(registry).resolve(manifest)

    error = error_info.value

    assert error.module_key == "postgres"
    assert error.field_path == "modules.postgres.variables.db_port"
    assert error.context["expected_type"] == "int"
    assert error.context["actual_type"] == "bool"

def test_resolver_raises_when_variable_is_unknown(
    registry,
    valid_manifest_data,
):
    django_module = next(
        module
        for module in valid_manifest_data["modules"]
        if module["key"] == "django"
    )

    django_module["variables"]["unknown_variable"] = "value"

    manifest = load_project_manifest_from_dict(
        valid_manifest_data
    )

    with pytest.raises(UnknownVariableError) as error_info:
        Resolver(registry).resolve(manifest)

    error = error_info.value

    assert error.code == "unknown_variable"
    assert error.module_key == "django"
    assert (
        error.field_path
        == "modules.django.variables.unknown_variable"
    )
    assert error.context["variable"] == "unknown_variable"
    assert "project_name" in error.context["available_variables"]
    assert error.suggestion is not None


def test_resolver_raises_when_option_is_unknown(
    registry,
    valid_manifest_data,
):
    django_module = next(
        module
        for module in valid_manifest_data["modules"]
        if module["key"] == "django"
    )

    django_module["options"]["unknown_option"] = True

    manifest = load_project_manifest_from_dict(
        valid_manifest_data
    )

    with pytest.raises(UnknownOptionError) as error_info:
        Resolver(registry).resolve(manifest)

    error = error_info.value

    assert error.code == "unknown_option"
    assert error.module_key == "django"
    assert (
        error.field_path
        == "modules.django.options.unknown_option"
    )
    assert error.context["option"] == "unknown_option"
    assert "cors" in error.context["available_options"]
    assert error.suggestion is not None


def test_resolver_raises_when_option_type_is_invalid(
    registry,
    valid_manifest_data,
):
    django_module = next(
        module
        for module in valid_manifest_data["modules"]
        if module["key"] == "django"
    )

    django_module["options"]["rest_framework"] = "enabled"

    manifest = load_project_manifest_from_dict(
        valid_manifest_data
    )

    with pytest.raises(InvalidOptionTypeError) as error_info:
        Resolver(registry).resolve(manifest)

    error = error_info.value

    assert error.code == "invalid_option_type"
    assert error.module_key == "django"
    assert (
        error.field_path
        == "modules.django.options.rest_framework"
    )
    assert error.context["option"] == "rest_framework"
    assert error.context["expected_type"] == "boolean"
    assert error.context["actual_type"] == "str"
    assert error.suggestion is not None