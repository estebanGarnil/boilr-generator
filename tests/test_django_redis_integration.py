import ast
from copy import deepcopy

import pytest
from boilr_generator.exceptions import (
    MissingCapabilityError,
)
from boilr_generator.generation import ProjectGenerator
from boilr_generator.manifest import (
    load_project_manifest_from_dict,
)
from boilr_generator.resolver import Resolver

DJANGO_REDIS_DEPENDENCY = "django-redis>=7.0,<8.0"

EXPECTED_CACHES = {
    "default": {
        "BACKEND": "django_redis.cache.RedisCache",
        "LOCATION": "redis://redis:6379/2",
        "OPTIONS": {
            "CLIENT_CLASS": (
                "django_redis.client.DefaultClient"
            ),
        },
    }
}


def build_django_redis_manifest(
    valid_manifest_data,
    *,
    include_redis=True,
):
    manifest_data = deepcopy(valid_manifest_data)

    if include_redis:
        manifest_data["modules"].insert(
            1,
            {
                "key": "redis",
                "variables": {
                    "redis_host_port": 6380,
                    "redis_database": 2,
                },
            },
        )

    manifest_data["modules"].append(
        {
            "key": "django-redis",
        }
    )

    return load_project_manifest_from_dict(
        manifest_data
    )


def find_assignment_value(
    source,
    variable_name,
):
    parsed_module = ast.parse(source)

    assignment = next(
        node
        for node in parsed_module.body
        if (
            isinstance(node, ast.Assign)
            and any(
                isinstance(target, ast.Name)
                and target.id == variable_name
                for target in node.targets
            )
        )
    )

    return ast.literal_eval(assignment.value)


def test_registry_discovers_django_redis_integration(
    registry,
):
    assert registry.has("django-redis") is True

    integration = registry.get("django-redis")

    assert integration.meta.type == "integration"
    assert len(integration.requires) == 2
    assert len(integration.contributions) == 2


def test_django_redis_integration_resolves_declaratively(
    registry,
    valid_manifest_data,
):
    manifest = build_django_redis_manifest(
        valid_manifest_data
    )

    project = Resolver(registry).resolve(manifest)

    integration_bindings = (
        project.bindings_for_consumer("django-redis")
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
            "redis",
            "cache.connection",
        ),
    }

    dependency_value = project.extension_value_for(
        "django",
        "python.dependencies",
    )

    assert dependency_value is not None
    assert set(dependency_value.value) == {
        "psycopg[binary]",
        DJANGO_REDIS_DEPENDENCY,
    }
    assert set(
        dependency_value.contributor_module_keys
    ) == {
        "django-postgres",
        "django-redis",
    }

    settings_value = project.extension_value_for(
        "django",
        "django.settings",
    )

    assert settings_value is not None
    assert settings_value.value == {
        "CACHES": EXPECTED_CACHES,
    }
    assert settings_value.contributor_module_keys == [
        "django-redis",
    ]

    ordered_keys = [
        module.key
        for module in project.ordered_modules()
    ]

    assert ordered_keys.index("django") < (
        ordered_keys.index("django-redis")
    )
    assert ordered_keys.index("redis") < (
        ordered_keys.index("django-redis")
    )


def test_django_redis_integration_generates_configuration(
    registry,
    valid_manifest_data,
    tmp_path,
):
    manifest = build_django_redis_manifest(
        valid_manifest_data
    )

    plan = ProjectGenerator(registry).plan(
        manifest=manifest,
        output_path=tmp_path / "generated",
    )

    planned_files = {
        planned_file.relative_destination_path: (
            planned_file
        )
        for planned_file in plan.files
    }

    requirements = planned_files[
        "backend/requirements.txt"
    ].content.decode("utf-8")

    assert DJANGO_REDIS_DEPENDENCY in {
        line.strip()
        for line in requirements.splitlines()
    }

    settings = planned_files[
        "backend/config/settings/base.py"
    ].content.decode("utf-8")

    assert find_assignment_value(
        settings,
        "CACHES",
    ) == EXPECTED_CACHES


def test_django_redis_requires_cache_provider(
    registry,
    valid_manifest_data,
):
    manifest = build_django_redis_manifest(
        valid_manifest_data,
        include_redis=False,
    )

    with pytest.raises(
        MissingCapabilityError
    ) as error_info:
        Resolver(registry).resolve(manifest)

    error = error_info.value

    assert error.code == "missing_capability"
    assert error.module_key == "django-redis"
    assert error.field_path == (
        "modules.django-redis.requires.cache"
    )
    assert error.context["capability"] == (
        "cache.connection"
    )
    assert error.context["binding_key"] == "cache"
    assert error.suggestion is not None