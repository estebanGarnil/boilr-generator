import pytest
from boilr_generator.exceptions import (
    InvalidContributionError,
    UnknownExtensionPointError,
)
from boilr_generator.modules.schemas import (
    ContributionDeclaration,
    ExtensionPointDefinition,
    RequiredCapability,
)
from boilr_generator.resolver import Resolver
from boilr_generator.resolver.contributions import (
    ContributionCollector,
)


def configure_contribution(
    project,
    *,
    extension_point="database.options",
    value=None,
):
    postgres = project.get_module("postgres")
    django = project.get_module("django")

    assert postgres is not None
    assert django is not None

    project.modules = [
        django,
    ]

    project.modules = [
        postgres,
        django,
    ]

    django.manifest.extension_points = {}

    postgres.manifest.extension_points = {
        "database.options": ExtensionPointDefinition(
            type="dict",
            merge="deep_merge",
            default={},
        )
    }

    django.manifest.contributions = [
        ContributionDeclaration.model_validate(
            {
                "target": "primary_database",
                "extension_point": extension_point,
                "value": (
                    {"pool_size": 10}
                    if value is None
                    else value
                ),
            }
        )
    ]

    return postgres, django


def test_collector_collects_extension_points(
    resolved_project,
):
    project = resolved_project.model_copy(deep=True)
    postgres, _ = configure_contribution(project)

    extension_points = (
        ContributionCollector().collect_extension_points(
            project.modules
        )
    )

    assert len(extension_points) == 1

    extension_point = extension_points[0]

    assert extension_point.module_key == "postgres"
    assert extension_point.key == "database.options"
    assert extension_point.value_type == "dict"
    assert extension_point.merge_strategy == "deep_merge"
    assert extension_point.default == {}

    extension_point.default["changed"] = True

    assert (
        postgres.manifest.extension_points[
            "database.options"
        ].default
        == {}
    )


def test_collector_resolves_target_through_binding(
    resolved_project,
):
    project = resolved_project.model_copy(deep=True)
    configure_contribution(project)

    collector = ContributionCollector()

    extension_points = collector.collect_extension_points(
        project.modules
    )
    contributions = collector.collect_contributions(
        project.modules,
        project.bindings,
        extension_points,
    )

    assert len(contributions) == 1

    contribution = contributions[0]

    assert contribution.contributor_module_key == "django"
    assert contribution.target_module_key == "postgres"
    assert contribution.target_binding == (
        "primary_database"
    )
    assert contribution.extension_point == (
        "database.options"
    )
    assert contribution.value == {
        "pool_size": 10,
    }


def test_collector_skips_contribution_without_optional_binding(
    resolved_project,
):
    project = resolved_project.model_copy(deep=True)
    django = project.get_module("django")

    assert django is not None

    project.modules = [
        django,
    ]
    project.bindings = []

    django.manifest.requires.append(
        RequiredCapability.model_validate(
            {
                "capability": "cache.connection",
                "binding": "optional_cache",
                "optional": True,
                "unique": True,
            }
        )
    )

    django.manifest.contributions = [
        ContributionDeclaration.model_validate(
            {
                "target": "optional_cache",
                "extension_point": "cache.options",
                "value": {},
            }
        )
    ]

    collector = ContributionCollector()

    extension_points = collector.collect_extension_points(
        project.modules
    )
    contributions = collector.collect_contributions(
        project.modules,
        project.bindings,
        extension_points,
    )

    assert contributions == []

def test_collector_rejects_unknown_extension_point(
    resolved_project,
):
    project = resolved_project.model_copy(deep=True)

    configure_contribution(
        project,
        extension_point="missing.extension",
    )

    collector = ContributionCollector()

    extension_points = collector.collect_extension_points(
        project.modules
    )

    with pytest.raises(
        UnknownExtensionPointError
    ) as error_info:
        collector.collect_contributions(
            project.modules,
            project.bindings,
            extension_points,
        )

    error = error_info.value

    assert error.code == "unknown_extension_point"
    assert error.module_key == "django"
    assert error.context["target_module"] == "postgres"
    assert error.context["target_binding"] == (
        "primary_database"
    )
    assert error.context["extension_point"] == (
        "missing.extension"
    )
    assert error.context[
        "available_extension_points"
    ] == ["database.options"]


def test_collector_rejects_invalid_contribution_type(
    resolved_project,
):
    project = resolved_project.model_copy(deep=True)

    configure_contribution(
        project,
        value=["not", "a", "dict"],
    )

    collector = ContributionCollector()

    extension_points = collector.collect_extension_points(
        project.modules
    )

    with pytest.raises(
        InvalidContributionError
    ) as error_info:
        collector.collect_contributions(
            project.modules,
            project.bindings,
            extension_points,
        )

    error = error_info.value

    assert error.code == "invalid_contribution"
    assert error.module_key == "django"
    assert error.context["target_module"] == "postgres"
    assert error.context["extension_point"] == (
        "database.options"
    )
    assert error.context["expected_type"] == "dict"
    assert error.context["actual_type"] == "list"

def test_resolver_stores_collected_contributions(
    registry,
    manifest,
    resolved_project,
    monkeypatch,
):
    project = resolved_project.model_copy(deep=True)
    configure_contribution(project)

    resolver = Resolver(registry)

    monkeypatch.setattr(
        resolver,
        "_resolve_modules",
        lambda _: project.modules,
    )

    result = resolver.resolve(manifest)

    assert len(result.extension_points) == 1
    assert len(result.contributions) == 1

    extension_point = result.extension_point_for(
        "postgres",
        "database.options",
    )

    assert extension_point is not None
    assert extension_point.value_type == "dict"
    assert extension_point.merge_strategy == "deep_merge"

    contributions = result.contributions_for_target(
        "postgres",
        "database.options",
    )

    assert len(contributions) == 1
    assert contributions[0].contributor_module_key == (
        "django"
    )
    assert contributions[0].value == {
        "pool_size": 10,
    }

    assert len(result.extension_point_values) == 1

    extension_value = result.extension_value_for(
        "postgres",
        "database.options",
    )

    assert extension_value is not None
    assert extension_value.value == {
        "pool_size": 10,
    }
    assert extension_value.contributor_module_keys == [
        "django"
    ]