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

    assert graph.nodes == ["postgres", "django"]
    assert len(graph.edges) == 1

    edge = graph.edges[0]

    assert edge.provider_module_key == "postgres"
    assert edge.consumer_module_key == "django"
    assert edge.capability == "database.connection"
    assert edge.binding_key == "primary_database"

    assert graph.dependencies_for("django") == [
        "postgres"
    ]
    assert graph.dependents_for("postgres") == [
        "django"
    ]


def test_graph_orders_provider_before_consumer(
    resolved_project,
):
    project = resolved_project.model_copy(deep=True)

    postgres = project.get_module("postgres")
    django = project.get_module("django")

    assert postgres is not None
    assert django is not None

    postgres.manifest.assembly.priority = 200
    django.manifest.assembly.priority = 10

    graph = DependencyGraphBuilder().build(
        project.modules,
        project.bindings,
    )

    assert graph.ordered_module_keys == [
        "postgres",
        "django",
    ]


def test_graph_does_not_duplicate_dependency_indegrees(
    resolved_project,
):
    duplicate_binding = resolved_project.bindings[
        0
    ].model_copy(
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

    assert len(graph.edges) == 2
    assert graph.ordered_module_keys == [
        "postgres",
        "django",
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
    assert error.field_path == "bindings"
    assert error.context["cycle"] == [
        "postgres",
        "django",
        "postgres",
    ]
    assert error.context["modules"] == [
        "postgres",
        "django",
    ]

def test_resolver_stores_dependency_graph(
    resolved_project,
):
    graph = resolved_project.dependency_graph

    assert graph.nodes == ["postgres", "django"]
    assert graph.ordered_module_keys == [
        "postgres",
        "django",
    ]
    assert len(graph.edges) == 1

    edge = graph.edges[0]

    assert edge.provider_module_key == "postgres"
    assert edge.consumer_module_key == "django"


def test_resolved_project_uses_dependency_graph_order(
    resolved_project,
):
    project = resolved_project.model_copy(deep=True)

    postgres = project.get_module("postgres")
    django = project.get_module("django")

    assert postgres is not None
    assert django is not None

    postgres.manifest.assembly.priority = 200
    django.manifest.assembly.priority = 10

    ordered_keys = [
        module.key
        for module in project.ordered_modules()
    ]

    assert ordered_keys == ["postgres", "django"]