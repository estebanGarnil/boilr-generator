import pytest
from boilr_generator.exceptions import TemplateRenderError
from boilr_generator.modules.schemas import (
    ProvidedCapability,
    RequiredCapability,
)
from boilr_generator.resolver import Resolver
from boilr_generator.resolver.capabilities import (
    CapabilityCollector,
)


def configure_capability_contracts(project):
    postgres = project.get_module("postgres")
    django = project.get_module("django")

    assert postgres is not None
    assert django is not None

    postgres.manifest.provides = [
        ProvidedCapability(
            capability="database.connection",
            values={
                "database": "{{ db_name }}",
                "user": "{{ db_user }}",
                "port": "{{ db_port }}",
            },
        )
    ]

    django.manifest.requires = [
        RequiredCapability.model_validate(
            {
                "capability": "database.connection",
                "binding": "primary_database",
                "optional": False,
                "unique": True,
            }
        )
    ]

    return postgres, django


def test_collector_collects_and_renders_capability_contracts(
    resolved_project,
):
    project = resolved_project.model_copy(deep=True)
    configure_capability_contracts(project)

    collector = CapabilityCollector()

    providers = collector.collect_providers(project.modules)
    requirements = collector.collect_requirements(
        project.modules
    )

    assert len(providers) == 1
    assert providers[0].module_key == "postgres"
    assert providers[0].capability == "database.connection"
    assert providers[0].values == {
        "database": "my_app",
        "user": "my_app",
        "port": 5432,
    }
    assert isinstance(providers[0].values["port"], int)

    assert len(requirements) == 1
    assert requirements[0].module_key == "django"
    assert requirements[0].binding_key == "primary_database"
    assert requirements[0].capability == (
        "database.connection"
    )
    assert requirements[0].optional is False
    assert requirements[0].unique is True


def test_resolver_stores_capability_contracts_and_bindings(
    registry,
    manifest,
    resolved_project,
    monkeypatch,
):
    project = resolved_project.model_copy(deep=True)
    configure_capability_contracts(project)

    resolver = Resolver(registry)

    monkeypatch.setattr(
        resolver,
        "_resolve_modules",
        lambda _: project.modules,
    )

    result = resolver.resolve(manifest)

    assert len(result.providers) == 1
    assert result.providers[0].module_key == "postgres"

    assert len(result.requirements) == 1
    assert result.requirements[0].module_key == "django"

    assert len(result.bindings) == 1

    binding = result.bindings[0]

    assert binding.binding_key == "primary_database"
    assert binding.capability == "database.connection"
    assert binding.consumer_module_key == "django"
    assert binding.provider_module_key == "postgres"
    assert binding.values == {
        "database": "my_app",
        "user": "my_app",
        "port": 5432,
    }


def test_collector_reports_provider_template_errors(
    resolved_project,
):
    project = resolved_project.model_copy(deep=True)
    postgres = project.get_module("postgres")

    assert postgres is not None

    postgres.manifest.provides = [
        ProvidedCapability(
            capability="database.connection",
            values={
                "host": "{{ missing_provider_value }}",
            },
        )
    ]

    with pytest.raises(TemplateRenderError) as error_info:
        CapabilityCollector().collect_providers(
            project.modules
        )

    error = error_info.value

    assert error.code == "template_render_error"
    assert error.module_key == "postgres"
    assert error.field_path == (
        "modules.postgres.provides[0].values.host"
    )
    assert error.context["target"] == (
        "capability_provider"
    )
    assert error.context["capability"] == (
        "database.connection"
    )
    assert error.context["error_type"] == "UndefinedError"