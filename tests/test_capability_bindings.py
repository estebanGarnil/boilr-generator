import pytest
from boilr_generator.core import (
    CapabilityProvider,
    CapabilityRequirement,
)
from boilr_generator.exceptions import (
    AmbiguousProviderError,
    BindingError,
    MissingCapabilityError,
    ProviderSelectionError,
)
from boilr_generator.manifest import (
    load_project_manifest_from_dict,
)
from boilr_generator.resolver import Resolver
from boilr_generator.resolver.bindings import CapabilityBinder


def make_provider(
    module_key,
    *,
    host="db",
):
    return CapabilityProvider(
        module_key=module_key,
        capability="database.connection",
        values={
            "host": host,
            "port": 5432,
        },
    )


def make_requirement(
    *,
    optional=False,
    unique=True,
    contract=None,
):
    return CapabilityRequirement(
        module_key="django",
        binding_key="primary_database",
        capability="database.connection",
        optional=optional,
        unique=unique,
        contract=contract or {},
    )


def test_binder_creates_binding_for_unique_provider():
    provider = make_provider("postgres")
    requirement = make_requirement()

    bindings = CapabilityBinder().bind(
        [provider],
        [requirement],
    )

    assert len(bindings) == 1

    binding = bindings[0]

    assert binding.binding_key == "primary_database"
    assert binding.capability == "database.connection"
    assert binding.consumer_module_key == "django"
    assert binding.provider_module_key == "postgres"
    assert binding.values == {
        "host": "db",
        "port": 5432,
    }

    binding.values["host"] = "changed"

    assert provider.values["host"] == "db"


def test_binder_rejects_missing_required_capability():
    requirement = make_requirement()

    with pytest.raises(MissingCapabilityError) as error_info:
        CapabilityBinder().bind(
            [],
            [requirement],
        )

    error = error_info.value

    assert error.code == "missing_capability"
    assert error.module_key == "django"
    assert error.field_path == (
        "modules.django.requires.primary_database"
    )
    assert error.context["capability"] == (
        "database.connection"
    )
    assert error.context["binding_key"] == (
        "primary_database"
    )
    assert error.context["available_capabilities"] == []
    assert error.suggestion is not None


def test_binder_skips_missing_optional_capability():
    requirement = make_requirement(optional=True)

    bindings = CapabilityBinder().bind(
        [],
        [requirement],
    )

    assert bindings == []


def test_binder_rejects_ambiguous_unique_provider():
    providers = [
        make_provider("postgres"),
        make_provider(
            "mysql",
            host="mysql",
        ),
    ]
    requirement = make_requirement(unique=True)

    with pytest.raises(
        AmbiguousProviderError
    ) as error_info:
        CapabilityBinder().bind(
            providers,
            [requirement],
        )

    error = error_info.value

    assert error.code == "ambiguous_provider"
    assert error.module_key == "django"
    assert error.context["candidate_count"] == 2
    assert error.context["candidate_modules"] == [
        "postgres",
        "mysql",
    ]


def test_binder_accepts_multiple_providers_when_not_unique():
    providers = [
        make_provider("postgres"),
        make_provider(
            "mysql",
            host="mysql",
        ),
    ]
    requirement = make_requirement(unique=False)

    bindings = CapabilityBinder().bind(
        providers,
        [requirement],
    )

    assert len(bindings) == 2
    assert [
        binding.provider_module_key
        for binding in bindings
    ] == [
        "postgres",
        "mysql",
    ]


def test_resolver_stores_created_bindings(
    registry,
    manifest,
    monkeypatch,
):
    provider = make_provider("postgres")
    requirement = make_requirement()

    resolver = Resolver(registry)

    monkeypatch.setattr(
        resolver.capability_collector,
        "collect_providers",
        lambda _: [provider],
    )
    monkeypatch.setattr(
        resolver.capability_collector,
        "collect_requirements",
        lambda _: [requirement],
    )
    monkeypatch.setattr(
        resolver.contribution_applier,
        "apply",
        lambda *_: [],
    )

    result = resolver.resolve(manifest)

    assert len(result.bindings) == 1
    assert result.bindings[0].consumer_module_key == (
        "django"
    )
    assert result.bindings[0].provider_module_key == (
        "postgres"
    )

def test_builtin_django_uses_postgres_binding(
    resolved_project,
):
    django = resolved_project.get_module("django")

    assert django is not None

    database_providers = resolved_project.providers_for(
        "database.connection"
    )

    assert len(database_providers) == 1
    assert database_providers[0].module_key == "postgres"

    django_requirements = [
        requirement
        for requirement in resolved_project.requirements
        if requirement.module_key == "django"
    ]

    django_bindings = (
        resolved_project.bindings_for_consumer("django")
    )

    assert len(django_requirements) == 1
    assert len(django_bindings) == 1

    requirement = django_requirements[0]
    binding = django_bindings[0]

    assert requirement.binding_key == "primary_database"
    assert requirement.capability == "database.connection"
    assert requirement.contract == {
        "engine": "string",
        "host": "string",
        "port": "int",
        "name": "string",
        "user": "string",
        "password": "string",
        "service": "string",
    }

    assert binding.consumer_module_key == "django"
    assert binding.provider_module_key == "postgres"
    assert binding.binding_key == "primary_database"
    assert binding.capability == "database.connection"
    assert binding.values == {
        "engine": "postgresql",
        "host": "db",
        "port": 5432,
        "name": "my_app",
        "user": "my_app",
        "password": "password",
        "service": "db",
    }

    duplicated_variables = {
        "db_engine",
        "db_host",
        "db_port",
        "db_name",
        "db_user",
        "db_password",
    }

    assert duplicated_variables.isdisjoint(
        django.variables
    )

def test_binder_rejects_missing_contract_field():
    provider = make_provider("postgres")
    del provider.values["port"]

    requirement = make_requirement(
        contract={
            "host": "string",
            "port": "int",
        }
    )

    with pytest.raises(BindingError) as error_info:
        CapabilityBinder().bind([provider], [requirement])

    error = error_info.value

    assert error.code == "binding_error"
    assert error.module_key == "django"
    assert error.field_path == (
        "modules.django.requires.primary_database.contract.port"
    )
    assert error.context["reason"] == "missing_field"
    assert error.context["provider_module"] == "postgres"
    assert error.context["field"] == "port"
    assert error.context["expected_type"] == "int"


def test_binder_rejects_invalid_contract_field_type():
    provider = make_provider("postgres")
    provider.values["port"] = "5432"

    requirement = make_requirement(
        contract={"port": "int"}
    )

    with pytest.raises(BindingError) as error_info:
        CapabilityBinder().bind([provider], [requirement])

    error = error_info.value

    assert error.context["reason"] == "invalid_type"
    assert error.context["expected_type"] == "int"
    assert error.context["actual_type"] == "str"


def test_binder_rejects_boolean_for_integer_contract_field():
    provider = make_provider("postgres")
    provider.values["port"] = True

    requirement = make_requirement(
        contract={"port": "int"}
    )

    with pytest.raises(BindingError) as error_info:
        CapabilityBinder().bind([provider], [requirement])

    assert error_info.value.context["actual_type"] == "bool"


def test_binder_accepts_additional_provider_fields():
    provider = make_provider("postgres")
    provider.values["engine"] = "postgresql"

    requirement = make_requirement(
        contract={"host": "string"}
    )

    bindings = CapabilityBinder().bind(
        [provider],
        [requirement],
    )

    assert bindings[0].values == {
        "host": "db",
        "port": 5432,
        "engine": "postgresql",
    }

@pytest.mark.parametrize("unique", [True, False])
def test_binder_uses_explicit_provider_selection(unique):
    providers = [
        make_provider("postgres"),
        make_provider(
            "mysql",
            host="mysql",
        ),
    ]
    requirement = make_requirement(unique=unique)

    bindings = CapabilityBinder().bind(
        providers,
        [requirement],
        provider_selections={
            "django": {
                "primary_database": "mysql",
            }
        },
        selected_module_keys={
            "django",
            "postgres",
            "mysql",
        },
    )

    assert len(bindings) == 1
    assert bindings[0].provider_module_key == "mysql"
    assert bindings[0].values["host"] == "mysql"


def test_binder_rejects_unknown_binding_selection():
    provider = make_provider("postgres")
    requirement = make_requirement()

    with pytest.raises(
        ProviderSelectionError
    ) as error_info:
        CapabilityBinder().bind(
            [provider],
            [requirement],
            provider_selections={
                "django": {
                    "unknown_database": "postgres",
                }
            },
            selected_module_keys={
                "django",
                "postgres",
            },
        )

    error = error_info.value

    assert error.code == "provider_selection_error"
    assert error.field_path == (
        "modules.django.bindings.unknown_database"
    )
    assert error.context["reason"] == "unknown_binding"
    assert error.context["available_bindings"] == [
        "primary_database"
    ]


@pytest.mark.parametrize("optional", [False, True])
def test_binder_rejects_provider_not_selected(
    optional,
):
    provider = make_provider("postgres")
    requirement = make_requirement(optional=optional)

    with pytest.raises(
        ProviderSelectionError
    ) as error_info:
        CapabilityBinder().bind(
            [provider],
            [requirement],
            provider_selections={
                "django": {
                    "primary_database": "mysql",
                }
            },
            selected_module_keys={
                "django",
                "postgres",
            },
        )

    error = error_info.value

    assert error.context["reason"] == (
        "provider_not_selected"
    )
    assert error.context["provider_module"] == "mysql"


def test_binder_rejects_provider_capability_mismatch():
    providers = [
        make_provider("postgres"),
        CapabilityProvider(
            module_key="redis",
            capability="cache.connection",
            values={},
        ),
    ]
    requirement = make_requirement()

    with pytest.raises(
        ProviderSelectionError
    ) as error_info:
        CapabilityBinder().bind(
            providers,
            [requirement],
            provider_selections={
                "django": {
                    "primary_database": "redis",
                }
            },
            selected_module_keys={
                "django",
                "postgres",
                "redis",
            },
        )

    error = error_info.value

    assert error.context["reason"] == (
        "capability_mismatch"
    )
    assert error.context["provider_module"] == "redis"
    assert error.context["provided_capabilities"] == [
        "cache.connection"
    ]

def test_resolver_honors_explicit_provider_selection(
    registry,
    valid_manifest_data,
):
    valid_manifest_data["modules"][1]["bindings"] = {
        "primary_database": {
            "provider": "postgres",
        }
    }

    manifest = load_project_manifest_from_dict(
        valid_manifest_data
    )

    result = Resolver(registry).resolve(manifest)

    django_bindings = result.bindings_for_consumer(
        "django"
    )

    assert len(django_bindings) == 1
    assert (
        django_bindings[0].provider_module_key
        == "postgres"
    )