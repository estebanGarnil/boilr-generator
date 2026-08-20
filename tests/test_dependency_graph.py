import pytest
from boilr_generator.core import CapabilityBinding
from boilr_generator.exceptions import (
    BindingError,
    DependencyCycleError,
)
from boilr_generator.resolver.graph import (
    DependencyGraphBuilder,
)


def test_graph_builds_edges_from_capability_bindings(
    resolved_project,
):
    graph = DependencyGraphBuilder().build(
        resolved_project.modules,
        resolved_project.bindings,
    )

    assert graph.nodes == [
        "postgres",
        "django",
        "django-postgres",
    ]
    assert len(graph.edges) == 3

    database_edge = next(
        edge
        for edge in graph.edges
        if (
            edge.provider_module_key == "postgres"
            and edge.consumer_module_key == "django"
        )
    )

    assert database_edge.capability == (
        "database.connection"
    )
    assert database_edge.binding_key == (
        "primary_database"
    )

    assert graph.dependencies_for("django") == [
        "postgres"
    ]
    assert graph.dependencies_for(
        "django-postgres"
    ) == [
        "django",
        "postgres",
    ]
    assert graph.dependents_for("postgres") == [
        "django",
        "django-postgres",
    ]
    assert graph.dependents_for("django") == [
        "django-postgres"
    ]


def test_graph_orders_provider_before_consumer(
    resolved_project,
):
    project = resolved_project.model_copy(deep=True)

    postgres = project.get_module("postgres")
    django = project.get_module("django")
    integration = project.get_module("django-postgres")

    assert postgres is not None
    assert django is not None
    assert integration is not None

    postgres.manifest.assembly.priority = 200
    django.manifest.assembly.priority = 10
    integration.manifest.assembly.priority = 5

    graph = DependencyGraphBuilder().build(
        project.modules,
        project.bindings,
    )

    assert graph.ordered_module_keys == [
        "postgres",
        "django",
        "django-postgres",
    ]


def test_graph_does_not_duplicate_dependency_indegrees(
    resolved_project,
):
    django_database_binding = next(
        binding
        for binding in resolved_project.bindings
        if (
            binding.consumer_module_key == "django"
            and binding.provider_module_key == "postgres"
        )
    )

    duplicate_binding = django_database_binding.model_copy(
        update={
            "binding_key": "secondary_database",
        }
    )

    graph = DependencyGraphBuilder().build(
        resolved_project.modules,
        [
            *resolved_project.bindings,
            duplicate_binding,
        ],
    )

    assert len(graph.edges) == 4
    assert graph.ordered_module_keys == [
        "postgres",
        "django",
        "django-postgres",
    ]


def test_graph_rejects_unknown_binding_module(
    resolved_project,
):
    binding = CapabilityBinding(
        binding_key="primary_cache",
        capability="cache.connection",
        consumer_module_key="django",
        provider_module_key="missing_cache",
        values={},
    )

    with pytest.raises(BindingError) as error_info:
        DependencyGraphBuilder().build(
            resolved_project.modules,
            [binding],
        )

    error = error_info.value

    assert error.code == "binding_error"
    assert error.module_key == "django"
    assert error.context["missing_modules"] == [
        "missing_cache"
    ]


def test_graph_rejects_dependency_cycles(
    resolved_project,
):
    reverse_binding = CapabilityBinding(
        binding_key="primary_backend",
        capability="backend.application",
        consumer_module_key="postgres",
        provider_module_key="django",
        values={},
    )

    with pytest.raises(
        DependencyCycleError
    ) as error_info:
        DependencyGraphBuilder().build(
            resolved_project.modules,
            [
                *resolved_project.bindings,
                reverse_binding,
            ],
        )

    error = error_info.value

    assert error.code == "dependency_cycle"
    assert error.module_key == "postgres"
    assert error.field_path == "bindings"
    assert error.context == {
        "cycle": [
            "postgres",
            "django",
            "postgres",
        ],
        "modules": [
            "postgres",
            "django",
        ],
    }
    assert error.suggestion is not None


def test_resolver_stores_dependency_graph(
    resolved_project,
):
    graph = resolved_project.dependency_graph

    assert graph.nodes == [
        "postgres",
        "django",
        "django-postgres",
    ]
    assert graph.ordered_module_keys == [
        "postgres",
        "django",
        "django-postgres",
    ]
    assert len(graph.edges) == 3

    edge_pairs = {
        (
            edge.provider_module_key,
            edge.consumer_module_key,
        )
        for edge in graph.edges
    }

    assert edge_pairs == {
        (
            "postgres",
            "django",
        ),
        (
            "django",
            "django-postgres",
        ),
        (
            "postgres",
            "django-postgres",
        ),
    }


def test_resolved_project_uses_dependency_graph_order(
    resolved_project,
):
    project = resolved_project.model_copy(deep=True)

    postgres = project.get_module("postgres")
    django = project.get_module("django")
    integration = project.get_module("django-postgres")

    assert postgres is not None
    assert django is not None
    assert integration is not None

    postgres.manifest.assembly.priority = 200
    django.manifest.assembly.priority = 10
    integration.manifest.assembly.priority = 5

    ordered_keys = [
        module.key
        for module in project.ordered_modules()
    ]

    assert ordered_keys == [
        "postgres",
        "django",
        "django-postgres",
    ]