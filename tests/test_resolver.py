import pytest

from boilr_generator.manifest import load_project_manifest_from_dict
from boilr_generator.resolver import Resolver
from boilr_generator.resolver.validator import (
    RequirementValidationError,
    VariableTypeValidationError,
    VariableValidationError,
)


def test_resolver_resolves_valid_project(registry, manifest):
    resolved_project = Resolver(registry).resolve(manifest)

    assert resolved_project.project.name == "my_app"
    assert resolved_project.has_module("postgres") is True
    assert resolved_project.has_module("django") is True


def test_resolver_orders_modules_by_priority(resolved_project):
    ordered_keys = [
        module.key
        for module in resolved_project.ordered_modules()
    ]

    assert ordered_keys == ["postgres", "django"]


def test_resolver_raises_when_required_database_is_missing(registry, valid_manifest_data):
    valid_manifest_data["modules"] = [
        module
        for module in valid_manifest_data["modules"]
        if module["key"] != "postgres"
    ]

    manifest = load_project_manifest_from_dict(valid_manifest_data)

    with pytest.raises(RequirementValidationError):
        Resolver(registry).resolve(manifest)


def test_resolver_raises_when_required_variable_is_missing(registry, valid_manifest_data):
    django_module = next(
        module for module in valid_manifest_data["modules"]
        if module["key"] == "django"
    )

    del django_module["variables"]["secret_key"]

    manifest = load_project_manifest_from_dict(valid_manifest_data)

    with pytest.raises(VariableValidationError):
        Resolver(registry).resolve(manifest)


def test_resolver_raises_when_variable_type_is_invalid(registry, valid_manifest_data):
    postgres_module = next(
        module for module in valid_manifest_data["modules"]
        if module["key"] == "postgres"
    )

    postgres_module["variables"]["db_port"] = "5432"

    manifest = load_project_manifest_from_dict(valid_manifest_data)

    with pytest.raises(VariableTypeValidationError):
        Resolver(registry).resolve(manifest)