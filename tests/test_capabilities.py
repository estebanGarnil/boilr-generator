from boilr_generator.core import (
    CapabilityBinding,
    CapabilityProvider,
    CapabilityRequirement,
)


def test_capability_domain_models_store_resolution_data():
    provider = CapabilityProvider(
        module_key="postgres",
        capability="database.connection",
        values={
            "host": "db",
            "port": 5432,
        },
    )

    requirement = CapabilityRequirement(
        module_key="django",
        binding_key="primary_database",
        capability="database.connection",
    )

    binding = CapabilityBinding(
        binding_key="primary_database",
        capability="database.connection",
        consumer_module_key="django",
        provider_module_key="postgres",
        values={
            "host": "db",
            "port": 5432,
        },
    )

    assert provider.module_key == "postgres"
    assert provider.capability == "database.connection"
    assert provider.values["port"] == 5432

    assert requirement.module_key == "django"
    assert requirement.binding_key == "primary_database"
    assert requirement.optional is False
    assert requirement.unique is True

    assert binding.consumer_module_key == "django"
    assert binding.provider_module_key == "postgres"
    assert binding.values == provider.values


def test_resolved_project_uses_empty_resolution_collections_by_default(
    resolved_project,
):
    assert resolved_project.providers == []
    assert resolved_project.requirements == []
    assert resolved_project.bindings == []


def test_resolved_project_queries_capability_relationships(
    resolved_project,
):
    provider = CapabilityProvider(
        module_key="postgres",
        capability="database.connection",
        values={
            "host": "db",
        },
    )

    requirement = CapabilityRequirement(
        module_key="django",
        binding_key="primary_database",
        capability="database.connection",
    )

    binding = CapabilityBinding(
        binding_key="primary_database",
        capability="database.connection",
        consumer_module_key="django",
        provider_module_key="postgres",
        values={
            "host": "db",
        },
    )

    project = resolved_project.model_copy(
        update={
            "providers": [provider],
            "requirements": [requirement],
            "bindings": [binding],
        }
    )

    assert project.providers_for(
        "database.connection"
    ) == [provider]

    assert project.requirements_for(
        "database.connection"
    ) == [requirement]

    assert project.bindings_for_consumer(
        "django"
    ) == [binding]

    assert project.bindings_for_provider(
        "postgres"
    ) == [binding]

    assert project.providers_for("cache.connection") == []