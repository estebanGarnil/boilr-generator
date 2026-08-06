import pytest
from boilr_generator.modules.schemas import ModuleManifest
from pydantic import ValidationError


def get_module_manifest_data(
    resolved_project,
    module_key,
):
    module = resolved_project.get_module(module_key)

    assert module is not None

    return module.manifest.model_dump(by_alias=True)


def test_builtin_modules_declare_capability_contracts(
    resolved_project,
):
    postgres = resolved_project.get_module("postgres")
    django = resolved_project.get_module("django")

    assert postgres is not None
    assert django is not None

    assert len(postgres.manifest.provides) == 1
    assert postgres.manifest.provides[0].capability == (
        "database.connection"
    )

    assert len(django.manifest.requires) == 1
    assert django.manifest.requires[0].capability == (
        "database.connection"
    )
    assert django.manifest.requires[0].binding_key == (
        "primary_database"
    )



def test_module_manifest_loads_capability_contracts(
    resolved_project,
):
    data = get_module_manifest_data(
        resolved_project,
        "postgres",
    )

    data["provides"] = [
        {
            "capability": "database.connection",
            "values": {
                "host": "db",
                "port": 5432,
            },
        }
    ]

    data["requires"] = [
        {
            "capability": "network.connection",
            "binding": "primary_network",
            "optional": True,
            "unique": True,
        }
    ]

    manifest = ModuleManifest.model_validate(data)

    assert len(manifest.provides) == 1
    assert manifest.provides[0].capability == (
        "database.connection"
    )
    assert manifest.provides[0].values["port"] == 5432

    assert len(manifest.requires) == 1
    assert manifest.requires[0].binding_key == (
        "primary_network"
    )
    assert manifest.requires[0].optional is True
    assert manifest.requires[0].unique is True

    serialized = manifest.model_dump(by_alias=True)

    assert serialized["requires"][0]["binding"] == (
        "primary_network"
    )


def test_module_manifest_rejects_duplicate_provided_capabilities(
    resolved_project,
):
    data = get_module_manifest_data(
        resolved_project,
        "postgres",
    )

    data["provides"] = [
        {
            "capability": "database.connection",
        },
        {
            "capability": "database.connection",
        },
    ]

    with pytest.raises(
        ValidationError,
        match="Duplicate provided capabilities",
    ):
        ModuleManifest.model_validate(data)


def test_module_manifest_rejects_duplicate_binding_keys(
    resolved_project,
):
    data = get_module_manifest_data(
        resolved_project,
        "django",
    )

    data["requires"] = [
        {
            "capability": "database.connection",
            "binding": "primary_database",
        },
        {
            "capability": "cache.connection",
            "binding": "primary_database",
        },
    ]

    with pytest.raises(
        ValidationError,
        match="Duplicate capability binding keys",
    ):
        ModuleManifest.model_validate(data)

def test_module_manifest_rejects_invalid_contract_types(
    resolved_project,
):
    data = get_module_manifest_data(
        resolved_project,
        "django",
    )

    data["requires"][0]["contract"] = {
        "host": "unknown",
    }

    with pytest.raises(
        ValidationError,
        match="Invalid capability contract types",
    ):
        ModuleManifest.model_validate(data)