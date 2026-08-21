from copy import deepcopy

from boilr_generator.generation.docker import (
    DockerComposeGenerator,
)
from boilr_generator.generation.env import EnvGenerator
from boilr_generator.manifest import (
    load_project_manifest_from_dict,
)
from boilr_generator.resolver import Resolver


def resolve_project_with_redis(
    registry,
    valid_manifest_data,
):
    manifest_data = deepcopy(valid_manifest_data)

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

    manifest = load_project_manifest_from_dict(
        manifest_data
    )

    return Resolver(registry).resolve(manifest)


def test_registry_discovers_redis_provider(
    registry,
):
    assert registry.has("redis") is True

    redis = registry.get("redis")

    assert redis.meta.type == "cache"
    assert redis.role.group == "cache"
    assert len(redis.provides) == 1
    assert (
        redis.provides[0].capability
        == "cache.connection"
    )


def test_redis_provider_exposes_resolved_connection(
    registry,
    valid_manifest_data,
):
    project = resolve_project_with_redis(
        registry,
        valid_manifest_data,
    )

    providers = project.providers_for(
        "cache.connection"
    )

    assert len(providers) == 1

    provider = providers[0]

    assert provider.module_key == "redis"
    assert provider.version == "1.0.0"
    assert provider.values == {
        "host": "redis",
        "port": 6379,
        "database": 2,
        "service": "redis",
        "url": "redis://redis:6379/2",
    }


def test_redis_provider_generates_docker_service(
    registry,
    valid_manifest_data,
):
    project = resolve_project_with_redis(
        registry,
        valid_manifest_data,
    )

    compose = DockerComposeGenerator().generate(
        project
    )

    redis_service = compose["services"]["redis"]

    assert redis_service["image"] == "redis:7-alpine"
    assert redis_service["restart"] == (
        "unless-stopped"
    )
    assert redis_service["ports"] == [
        "6380:6379",
    ]
    assert redis_service["volumes"] == [
        "redis_data:/data",
    ]
    assert redis_service["healthcheck"]["test"] == [
        "CMD",
        "redis-cli",
        "ping",
    ]
    assert compose["volumes"]["redis_data"] == {}


def test_redis_provider_exports_environment(
    registry,
    valid_manifest_data,
):
    project = resolve_project_with_redis(
        registry,
        valid_manifest_data,
    )

    environment = EnvGenerator().generate(project)

    assert environment["REDIS_HOST"] == "redis"
    assert environment["REDIS_PORT"] == "6379"
    assert environment["REDIS_DATABASE"] == "2"
    assert environment["REDIS_URL"] == (
        "redis://redis:6379/2"
    )