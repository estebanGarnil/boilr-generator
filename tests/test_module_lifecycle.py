import json
from dataclasses import FrozenInstanceError

import pytest

from boilr_generator import core as core_api
from boilr_generator.core.module_lifecycle import (
    build_project_module_lifecycle_graph,
)


def test_lifecycle_graph_describes_every_resolved_module(
    resolved_project,
):
    before = resolved_project.model_dump(
        mode="python"
    )

    graph = build_project_module_lifecycle_graph(
        resolved_project
    )

    assert graph.module_keys == tuple(
        sorted(
            resolved_project.list_module_keys()
        )
    )
    assert graph.resolution_order == tuple(
        module.key
        for module
        in resolved_project.ordered_modules()
    )

    for module in resolved_project.modules:
        node = graph.node_for(module.key)

        assert (
            node.version
            == module.manifest.meta.version
        )
        assert node.module_type == module.type

        assert (
            node.provided_capabilities
            == tuple(
                sorted(
                    {
                        provider.capability
                        for provider
                        in resolved_project.providers
                        if (
                            provider.module_key
                            == module.key
                        )
                    }
                )
            )
        )

        assert (
            node.required_capabilities
            == tuple(
                sorted(
                    {
                        requirement.capability
                        for requirement
                        in resolved_project.requirements
                        if (
                            requirement.module_key
                            == module.key
                        )
                    }
                )
            )
        )

    assert (
        resolved_project.model_dump(
            mode="python"
        )
        == before
    )


def test_lifecycle_graph_records_relationships(
    resolved_project,
):
    graph = build_project_module_lifecycle_graph(
        resolved_project
    )

    capability_relations = {
        (
            relation.dependent_module,
            relation.dependency_module,
            relation.binding,
            relation.capability,
        )
        for relation in graph.relations
        if relation.kind == "capability_binding"
    }

    contribution_relations = {
        (
            relation.dependent_module,
            relation.dependency_module,
            relation.binding,
            relation.extension_point,
        )
        for relation in graph.relations
        if (
            relation.kind
            == "extension_contribution"
        )
    }

    assert capability_relations == {
        (
            binding.consumer_module_key,
            binding.provider_module_key,
            binding.binding_key,
            binding.capability,
        )
        for binding in resolved_project.bindings
        if (
            binding.consumer_module_key
            != binding.provider_module_key
        )
    }

    assert contribution_relations == {
        (
            contribution.contributor_module_key,
            contribution.target_module_key,
            contribution.target_binding,
            contribution.extension_point,
        )
        for contribution
        in resolved_project.contributions
        if (
            contribution.contributor_module_key
            != contribution.target_module_key
        )
    }

    for relation in graph.relations:
        assert relation.dependency_module in (
            graph.dependencies_of(
                relation.dependent_module
            )
        )
        assert relation.dependent_module in (
            graph.dependents_of(
                relation.dependency_module
            )
        )


def test_lifecycle_graph_orders_removals_safely(
    resolved_project,
):
    graph = build_project_module_lifecycle_graph(
        resolved_project
    )

    removal_order = graph.removal_order()
    positions = {
        module_key: index
        for index, module_key
        in enumerate(removal_order)
    }

    assert set(removal_order) == set(
        graph.module_keys
    )

    for relation in graph.relations:
        assert (
            positions[
                relation.dependent_module
            ]
            < positions[
                relation.dependency_module
            ]
        )

    relation = graph.relations[0]

    blockers = graph.removal_blockers(
        relation.dependency_module
    )

    assert (
        relation.dependent_module
        in blockers
    )

    with pytest.raises(
        ValueError,
        match="dependents remain",
    ):
        graph.removal_order(
            relation.dependency_module
        )


def test_lifecycle_graph_exposes_transitive_links(
    resolved_project,
):
    graph = build_project_module_lifecycle_graph(
        resolved_project
    )

    for module_key in graph.module_keys:
        assert set(
            graph.dependencies_of(module_key)
        ) <= set(
            graph.dependencies_of(
                module_key,
                transitive=True,
            )
        )

        assert set(
            graph.dependents_of(module_key)
        ) <= set(
            graph.dependents_of(
                module_key,
                transitive=True,
            )
        )


def test_lifecycle_graph_detects_cycles(
    resolved_project,
):
    project = resolved_project.model_copy(
        deep=True
    )
    binding = project.bindings[0]

    project.bindings.append(
        binding.model_copy(
            update={
                "binding_key": (
                    f"{binding.binding_key}-cycle"
                ),
                "consumer_module_key": (
                    binding.provider_module_key
                ),
                "provider_module_key": (
                    binding.consumer_module_key
                ),
            }
        )
    )

    graph = build_project_module_lifecycle_graph(
        project
    )

    assert graph.has_cycles is True

    assert {
        binding.consumer_module_key,
        binding.provider_module_key,
    } <= set(graph.cycle_module_keys)

    with pytest.raises(
        ValueError,
        match="cyclic modules",
    ):
        graph.removal_order()


def test_lifecycle_graph_is_immutable_and_stable(
    resolved_project,
):
    graph = build_project_module_lifecycle_graph(
        resolved_project
    )

    first = json.dumps(
        graph.to_dict(),
        sort_keys=True,
    )
    second = json.dumps(
        graph.to_dict(),
        sort_keys=True,
    )

    assert first == second
    assert json.loads(first) == graph.to_dict()

    with pytest.raises(FrozenInstanceError):
        graph.nodes[0].key = "changed"


def test_core_api_exports_module_lifecycle_graph():
    assert (
        core_api.build_project_module_lifecycle_graph
        is build_project_module_lifecycle_graph
    )

    assert (
        build_project_module_lifecycle_graph.__module__
        == "boilr_generator.core.module_lifecycle"
    )

    for name in (
        "ModuleLifecycleNode",
        "ModuleLifecycleRelation",
        "ProjectModuleLifecycleGraph",
        "build_project_module_lifecycle_graph",
    ):
        assert name in core_api.__all__