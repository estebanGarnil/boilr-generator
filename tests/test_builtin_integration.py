from copy import deepcopy

from boilr_generator.generation import ProjectGenerator
from boilr_generator.manifest import (
    load_project_manifest_from_dict,
)
from boilr_generator.resolver import Resolver


def build_integration_manifest(valid_manifest_data):
    data = deepcopy(valid_manifest_data)

    data["modules"].append(
        {
            "key": "django-postgres",
        }
    )

    return load_project_manifest_from_dict(data)


def test_registry_discovers_django_postgres_integration(
    registry,
):
    assert registry.has("django-postgres") is True

    integration = registry.get("django-postgres")

    assert integration.meta.type == "integration"
    assert len(integration.requires) == 2
    assert len(integration.contributions) == 1


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

    contributions = project.contributions_for_target(
        "django",
        "python.dependencies",
    )

    assert len(contributions) == 1
    assert contributions[0].contributor_module_key == (
        "django-postgres"
    )
    assert contributions[0].value == [
        "psycopg[binary]"
    ]

    extension_value = project.extension_value_for(
        "django",
        "python.dependencies",
    )

    assert extension_value is not None
    assert extension_value.value == [
        "psycopg[binary]"
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

    ProjectGenerator(registry).generate(
        manifest=manifest,
        output_path=output_path,
        clean=True,
    )

    requirements = (
        output_path / "backend" / "requirements.txt"
    ).read_text(encoding="utf-8")

    assert "psycopg[binary]" in (
        line.strip()
        for line in requirements.splitlines()
    )