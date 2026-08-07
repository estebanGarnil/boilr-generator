import pytest
from boilr_generator.exceptions import (
    AmbiguousRequirementError,
    IncompatibleModuleError,
    InvalidVariableTypeError,
    MissingRequirementError,
    MissingVariableError,
)
from boilr_generator.manifest import load_project_manifest_from_dict
from boilr_generator.resolver import Resolver
from boilr_generator.resolver.validator import ProjectValidator


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

def test_resolver_raises_when_required_database_is_missing(
    registry,
    valid_manifest_data,
):
    valid_manifest_data["modules"] = [
        module
        for module in valid_manifest_data["modules"]
        if module["key"] != "postgres"
    ]

    manifest = load_project_manifest_from_dict(valid_manifest_data)

    with pytest.raises(MissingRequirementError) as error_info:
        Resolver(registry).resolve(manifest)

    error = error_info.value

    assert error.code == "missing_requirement"
    assert error.module_key == "django"
    assert error.field_path == "modules.django.requirements.database"
    assert error.context["required_type"] == "database"
    assert error.suggestion is not None


def test_resolver_raises_when_unique_requirement_is_ambiguous(
    resolved_project,
):
    postgres = resolved_project.get_module("postgres")
    django = resolved_project.get_module("django")

    assert postgres is not None
    assert django is not None

    duplicate_postgres = postgres.model_copy(deep=True)

    modules = [
        postgres,
        duplicate_postgres,
        django,
    ]

    with pytest.raises(AmbiguousRequirementError) as error_info:
        ProjectValidator().validate_requirements(modules)

    error = error_info.value

    assert error.code == "ambiguous_requirement"
    assert error.module_key == "django"
    assert error.field_path == "modules.django.requirements.database"
    assert error.context["required_type"] == "database"
    assert error.context["candidate_count"] == 2
    assert error.context["candidate_modules"] == [
        "postgres",
        "postgres",
    ]


def test_resolver_raises_when_modules_are_incompatible(
    resolved_project,
):
    postgres = resolved_project.get_module("postgres")
    django = resolved_project.get_module("django")

    assert postgres is not None
    assert django is not None

    incompatible_manifest = django.manifest.model_copy(deep=True)
    incompatible_manifest.compatibility.matrix["database"] = []

    incompatible_django = django.model_copy(
        update={"manifest": incompatible_manifest},
    )

    with pytest.raises(IncompatibleModuleError) as error_info:
        ProjectValidator().validate_compatibility(
            [incompatible_django, postgres]
        )

    error = error_info.value

    assert error.code == "incompatible_module"
    assert error.module_key == "django"
    assert error.field_path == "modules.django.compatibility.database"
    assert error.context["incompatible_module"] == "postgres"
    assert error.context["incompatible_module_type"] == "database"


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