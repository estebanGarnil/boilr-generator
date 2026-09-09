import json
from copy import deepcopy

import pytest

import boilr_generator.generation as generation_api
from boilr_generator.core.module_lifecycle import (
    build_project_module_lifecycle_graph,
)
from boilr_generator.generation import ProjectGenerator
from boilr_generator.generation.module_update import (
    build_project_module_transition_plan,
)
from boilr_generator.state.schemas import (
    ProjectState,
    StateBinding,
)


def _candidate_plan(
    registry,
    manifest,
    tmp_path,
):
    plan = ProjectGenerator(registry).plan(
        manifest=manifest,
        output_path=tmp_path / "output",
    )

    assert plan.desired_state is not None
    return plan


def _state_without_modules(
    state: ProjectState,
    removed: set[str],
) -> ProjectState:
    data = state.model_dump(mode="python")

    data["modules"] = [
        module
        for module in data["modules"]
        if module["key"] not in removed
    ]
    data["bindings"] = [
        binding
        for binding in data["bindings"]
        if (
            binding["consumer_module"]
            not in removed
            and binding["provider_module"]
            not in removed
        )
    ]
    data["resources"] = [
        resource
        for resource in data["resources"]
        if (
            resource["owner"] not in removed
            and not (
                set(resource["contributors"])
                & removed
            )
        )
    ]

    return ProjectState.model_validate(data)


def _plan_without_modules(
    candidate_plan,
    removed: set[str],
):
    plan = deepcopy(candidate_plan)
    project = plan.resolved_project
    dependency_graph = project.dependency_graph

    plan.resolved_project = project.model_copy(
        update={
            "modules": [
                module
                for module in project.modules
                if module.key not in removed
            ],
            "providers": [
                provider
                for provider in project.providers
                if provider.module_key not in removed
            ],
            "requirements": [
                requirement
                for requirement
                in project.requirements
                if requirement.module_key
                not in removed
            ],
            "bindings": [
                binding
                for binding in project.bindings
                if (
                    binding.consumer_module_key
                    not in removed
                    and binding.provider_module_key
                    not in removed
                )
            ],
            "dependency_graph": (
                dependency_graph.model_copy(
                    update={
                        "nodes": [
                            module_key
                            for module_key
                            in dependency_graph.nodes
                            if (
                                module_key
                                not in removed
                            )
                        ],
                        "edges": [
                            edge
                            for edge
                            in dependency_graph.edges
                            if (
                                edge.consumer_module_key
                                not in removed
                                and edge.provider_module_key
                                not in removed
                            )
                        ],
                        "ordered_module_keys": [
                            module_key
                            for module_key
                            in dependency_graph
                            .ordered_module_keys
                            if (
                                module_key
                                not in removed
                            )
                        ],
                    }
                )
            ),
            "extension_points": [
                extension_point
                for extension_point
                in project.extension_points
                if (
                    extension_point.module_key
                    not in removed
                )
            ],
            "contributions": [
                contribution
                for contribution
                in project.contributions
                if (
                    contribution
                    .contributor_module_key
                    not in removed
                    and contribution
                    .target_module_key
                    not in removed
                )
            ],
            "extension_point_values": [
                value.model_copy(
                    update={
                        "contributor_module_keys": [
                            module_key
                            for module_key
                            in value
                            .contributor_module_keys
                            if (
                                module_key
                                not in removed
                            )
                        ]
                    }
                )
                for value
                in project.extension_point_values
                if value.module_key not in removed
            ],
        },
        deep=True,
    )

    plan.desired_state = (
        _state_without_modules(
            plan.desired_state,
            removed,
        )
    )

    return plan


def _state_with_binding(
    state: ProjectState,
    binding,
) -> ProjectState:
    data = state.model_dump(mode="python")
    data["bindings"] = list(
        data["bindings"]
    )

    data["bindings"].append(
        StateBinding(
            consumer_module=(
                binding.consumer_module_key
            ),
            binding=binding.binding_key,
            capability=binding.capability,
            provider_module=(
                binding.provider_module_key
            ),
        ).model_dump(mode="python")
    )

    return ProjectState.model_validate(data)


def test_unchanged_modules_build_noop_transition_plan(
    registry,
    manifest,
    tmp_path,
):
    candidate_plan = _candidate_plan(
        registry,
        manifest,
        tmp_path,
    )
    current_state = candidate_plan.desired_state
    before_plan = candidate_plan.to_dict()
    before_state = current_state.model_dump(
        mode="json"
    )

    transition_plan = (
        build_project_module_transition_plan(
            candidate_plan,
            current_state,
        )
    )

    assert transition_plan.can_execute is True
    assert transition_plan.has_changes is False
    assert transition_plan.activation_order == ()
    assert transition_plan.removal_order == ()

    assert all(
        transition.action == "retain"
        for transition in transition_plan.modules
    )
    assert all(
        transition.action == "retain"
        for transition in transition_plan.bindings
    )

    assert candidate_plan.to_dict() == before_plan
    assert (
        current_state.model_dump(mode="json")
        == before_state
    )


def test_added_module_uses_candidate_resolution_order(
    registry,
    manifest,
    tmp_path,
):
    candidate_plan = _candidate_plan(
        registry,
        manifest,
        tmp_path,
    )
    added_module = (
        candidate_plan
        .resolved_project
        .ordered_modules()[-1]
        .key
    )
    current_state = _state_without_modules(
        candidate_plan.desired_state,
        {added_module},
    )

    transition_plan = (
        build_project_module_transition_plan(
            candidate_plan,
            current_state,
        )
    )

    transition = next(
        item
        for item in transition_plan.modules
        if item.module_key == added_module
    )

    assert transition.action == "add"
    assert transition.current_version is None
    assert transition.target_version is not None
    assert transition_plan.activation_order == (
        added_module,
    )
    assert transition_plan.can_execute is True


def test_removed_modules_are_ordered_dependents_first(
    registry,
    manifest,
    tmp_path,
):
    baseline_plan = _candidate_plan(
        registry,
        manifest,
        tmp_path,
    )
    current_state = baseline_plan.desired_state

    graph = build_project_module_lifecycle_graph(
        baseline_plan.resolved_project
    )
    relation = next(
        item
        for item in graph.relations
        if item.kind == "capability_binding"
    )
    removed = {
        relation.dependent_module,
        relation.dependency_module,
    }

    candidate_plan = _plan_without_modules(
        baseline_plan,
        removed,
    )

    transition_plan = (
        build_project_module_transition_plan(
            candidate_plan,
            current_state,
        )
    )

    positions = {
        module_key: index
        for index, module_key
        in enumerate(
            transition_plan.removal_order
        )
    }

    assert {
        transition.module_key
        for transition in transition_plan.modules
        if transition.action == "remove"
    } == removed

    assert (
        positions[relation.dependent_module]
        < positions[relation.dependency_module]
    )
    assert transition_plan.can_execute is True


def test_module_and_binding_changes_are_explicit(
    registry,
    manifest,
    tmp_path,
):
    candidate_plan = _candidate_plan(
        registry,
        manifest,
        tmp_path,
    )
    current_state = candidate_plan.desired_state

    desired_data = current_state.model_dump(
        mode="python"
    )
    desired_data["modules"][0][
        "manifest_sha256"
    ] = "f" * 64

    resolved_binding = (
        candidate_plan
        .resolved_project
        .bindings[0]
    )
    changed_capability = (
        f"{resolved_binding.capability}.updated"
    )
    resolved_binding.capability = (
        changed_capability
    )

    binding_identity = (
        resolved_binding.consumer_module_key,
        resolved_binding.binding_key,
    )

    for binding in desired_data["bindings"]:
        if (
            binding["consumer_module"],
            binding["binding"],
        ) == binding_identity:
            binding["capability"] = (
                changed_capability
            )
            break

    candidate_plan.desired_state = (
        ProjectState.model_validate(
            desired_data
        )
    )

    transition_plan = (
        build_project_module_transition_plan(
            candidate_plan,
            current_state,
        )
    )

    module_change = next(
        transition
        for transition in transition_plan.modules
        if transition.action == "update"
    )
    binding_change = next(
        transition
        for transition in transition_plan.bindings
        if (
            transition.identity
            == binding_identity
        )
    )

    assert module_change.changed_fields == (
        "manifest_sha256",
    )
    assert binding_change.action == "update"
    assert binding_change.changed_fields == (
        "capability",
    )
    assert transition_plan.has_changes is True


def test_candidate_cycle_is_an_explicit_conflict(
    registry,
    manifest,
    tmp_path,
):
    candidate_plan = _candidate_plan(
        registry,
        manifest,
        tmp_path,
    )
    current_state = candidate_plan.desired_state
    binding = (
        candidate_plan
        .resolved_project
        .bindings[0]
    )

    reverse_binding = binding.model_copy(
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

    candidate_plan.resolved_project.bindings.append(
        reverse_binding
    )
    candidate_plan.desired_state = (
        _state_with_binding(
            candidate_plan.desired_state,
            reverse_binding,
        )
    )

    transition_plan = (
        build_project_module_transition_plan(
            candidate_plan,
            current_state,
        )
    )

    assert transition_plan.can_execute is False
    assert (
        transition_plan.conflicts[0].reason
        == "candidate_cycle"
    )
    assert {
        binding.consumer_module_key,
        binding.provider_module_key,
    } <= set(
        transition_plan
        .conflicts[0]
        .module_keys
    )


def test_removed_binding_cycle_is_a_conflict(
    registry,
    manifest,
    tmp_path,
):
    baseline_plan = _candidate_plan(
        registry,
        manifest,
        tmp_path,
    )
    binding = (
        baseline_plan
        .resolved_project
        .bindings[0]
    )

    reverse_binding = binding.model_copy(
        update={
            "binding_key": (
                f"{binding.binding_key}"
                "-removal-cycle"
            ),
            "consumer_module_key": (
                binding.provider_module_key
            ),
            "provider_module_key": (
                binding.consumer_module_key
            ),
        }
    )

    current_state = _state_with_binding(
        baseline_plan.desired_state,
        reverse_binding,
    )
    removed = {
        binding.consumer_module_key,
        binding.provider_module_key,
    }
    candidate_plan = _plan_without_modules(
        baseline_plan,
        removed,
    )

    transition_plan = (
        build_project_module_transition_plan(
            candidate_plan,
            current_state,
        )
    )

    assert transition_plan.can_execute is False
    assert transition_plan.removal_order == ()
    assert (
        transition_plan.conflicts[0].reason
        == "removal_cycle"
    )
    assert removed == set(
        transition_plan
        .conflicts[0]
        .module_keys
    )


def test_module_transition_plan_is_json_stable(
    registry,
    manifest,
    tmp_path,
):
    candidate_plan = _candidate_plan(
        registry,
        manifest,
        tmp_path,
    )
    current_state = candidate_plan.desired_state

    transition_plan = (
        build_project_module_transition_plan(
            candidate_plan,
            current_state,
        )
    )
    first = transition_plan.to_dict()
    second = transition_plan.to_dict()

    assert first == second
    assert json.loads(json.dumps(first)) == first
    assert first["can_execute"] is True
    assert first["has_changes"] is False


def test_module_transition_rejects_mismatched_state(
    registry,
    manifest,
    tmp_path,
):
    candidate_plan = _candidate_plan(
        registry,
        manifest,
        tmp_path,
    )
    current_state = candidate_plan.desired_state
    removed_module = (
        current_state.modules[-1].key
    )

    candidate_plan.desired_state = (
        _state_without_modules(
            current_state,
            {removed_module},
        )
    )

    with pytest.raises(
        ValueError,
        match="does not match",
    ):
        build_project_module_transition_plan(
            candidate_plan,
            current_state,
        )


def test_generation_api_exports_module_transition_planner():
    assert (
        generation_api
        .build_project_module_transition_plan
        is build_project_module_transition_plan
    )
    assert (
        build_project_module_transition_plan
        .__module__
        == (
            "boilr_generator.generation"
            ".module_update"
        )
    )

    for name in (
        "BindingTransition",
        "ModuleTransition",
        "ModuleTransitionConflict",
        "ProjectModuleTransitionPlan",
        "build_project_module_transition_plan",
    ):
        assert name in generation_api.__all__