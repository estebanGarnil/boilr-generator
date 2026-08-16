from copy import deepcopy

import pytest
from boilr_generator.exceptions import (
    InvalidContributionError,
)
from boilr_generator.manifest import (
    load_project_manifest_from_dict,
)
from boilr_generator.resolver import Resolver

from boilr_generator.generation import ProjectGenerator


def build_integration_manifest(valid_manifest_data):
    return load_project_manifest_from_dict(
        deepcopy(valid_manifest_data)
    )


def test_registry_discovers_django_postgres_integration(
    registry,
):
    assert registry.has("django-postgres") is True

    integration = registry.get("django-postgres")

    assert integration.meta.type == "integration"
    assert len(integration.requires) == 2
    assert len(integration.contributions) == 2


def test_django_postgres_integration_resolves_declaratively(
    registry,
    valid_manifest_data,
):
    manifest = build_integration_manifest(
        valid_manifest_data
    )

    project = Resolver(registry).resolve(manifest)

    integration_bindings = (
        project.bindings_for_consumer(
            "django-postgres"
        )
    )

    assert {
        (
            binding.provider_module_key,
            binding.capability,
        )
        for binding in integration_bindings
    } == {
        (
            "django",
            "backend.python",
        ),
        (
            "postgres",
            "database.connection",
        ),
    }

    dependency_contributions = (
        project.contributions_for_target(
            "django",
            "python.dependencies",
        )
    )

    assert len(dependency_contributions) == 1
    assert (
        dependency_contributions[
            0
        ].contributor_module_key
        == "django-postgres"
    )
    assert dependency_contributions[0].value == [
        "psycopg[binary]"
    ]

    dependency_value = project.extension_value_for(
        "django",
        "python.dependencies",
    )

    assert dependency_value is not None
    assert dependency_value.value == [
        "psycopg[binary]"
    ]
    assert dependency_value.contributor_module_keys == [
        "django-postgres"
    ]

    backend_contributions = (
        project.contributions_for_target(
            "django",
            "database.backend",
        )
    )

    assert len(backend_contributions) == 1
    assert (
        backend_contributions[
            0
        ].contributor_module_key
        == "django-postgres"
    )
    assert backend_contributions[0].value == (
        "django.db.backends.postgresql"
    )

    database_backend = project.extension_value_for(
        "django",
        "database.backend",
    )

    assert database_backend is not None
    assert database_backend.value == (
        "django.db.backends.postgresql"
    )
    assert database_backend.contributor_module_keys == [
        "django-postgres"
    ]

    ordered_keys = [
        module.key
        for module in project.ordered_modules()
    ]

    assert ordered_keys == [
        "postgres",
        "django",
        "django-postgres",
    ]

    django = project.get_module("django")

    assert django is not None
    assert "postgres" not in django.manifest.dependencies
    assert "mysql" not in django.manifest.dependencies

def test_django_postgres_integration_generates_driver(
    registry,
    valid_manifest_data,
    tmp_path,
):
    manifest = build_integration_manifest(
        valid_manifest_data
    )

    output_path = tmp_path / "generated"
    generator = ProjectGenerator(registry)

    plan = generator.plan(
        manifest=manifest,
        output_path=output_path,
        clean=True,
    )
    generator.execute(plan)

    requirements = (
        output_path
        / "backend"
        / "requirements.txt"
    ).read_text(encoding="utf-8")

    assert "psycopg[binary]" in (
        line.strip()
        for line in requirements.splitlines()
    )

    settings = (
        output_path
        / "backend"
        / "config"
        / "settings"
        / "base.py"
    ).read_text(encoding="utf-8")

    assert (
        '"ENGINE": "django.db.backends.postgresql"'
        in settings
    )

def test_django_rejects_missing_database_integration(
    registry,
    valid_manifest_data,
):
    data = deepcopy(valid_manifest_data)

    data["modules"] = [
        module
        for module in data["modules"]
        if module["key"] != "django-postgres"
    ]

    manifest = load_project_manifest_from_dict(data)

    with pytest.raises(
        InvalidContributionError
    ) as error_info:
        Resolver(registry).resolve(manifest)

    error = error_info.value

    assert error.code == "invalid_contribution"
    assert error.module_key == "django"
    assert error.field_path == (
        "modules.django."
        "extension_points.database.backend"
    )
    assert error.context["reason"] == (
        "missing_required_contribution"
    )
    assert error.context["target_module"] == "django"
    assert error.context["extension_point"] == (
        "database.backend"
    )
    assert error.suggestion is not None