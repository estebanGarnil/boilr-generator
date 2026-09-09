import json

from boilr_generator.generation import (
    ProjectGenerator,
    build_project_update_plan,
    observe_project,
)
from boilr_generator.state import (
    ProjectStateStorage,
)
from boilr_generator.state.schemas import (
    ProjectState,
    StateBinding,
)


def _update_context(
    registry,
    manifest,
    output_path,
):
    generator = ProjectGenerator(registry)

    initial_plan = generator.plan(
        manifest=manifest,
        output_path=output_path,
    )
    generator.execute(initial_plan)

    storage = ProjectStateStorage(output_path)
    current_state = storage.read()

    assert current_state is not None

    candidate_plan = generator.plan(
        manifest=manifest,
        output_path=output_path,
    )
    observation = observe_project(output_path)

    assert candidate_plan.desired_state is not None
    assert observation is not None

    return (
        candidate_plan,
        current_state,
        observation,
    )


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


def test_update_plan_contains_module_transitions(
    registry,
    manifest,
    tmp_path,
):
    output_path = tmp_path / "output"

    (
        candidate_plan,
        current_state,
        observation,
    ) = _update_context(
        registry,
        manifest,
        output_path,
    )

    update_plan = build_project_update_plan(
        candidate_plan,
        current_state,
        observation,
    )

    module_plan = update_plan.module_transitions

    assert module_plan.can_execute is True
    assert module_plan.has_changes is False
    assert module_plan.activation_order == ()
    assert module_plan.removal_order == ()
    assert module_plan.current_state == current_state
    assert module_plan.desired_state == (
        update_plan.desired_state
    )
    assert all(
        transition.action == "retain"
        for transition in module_plan.modules
    )
    assert all(
        transition.action == "retain"
        for transition in module_plan.bindings
    )
    assert update_plan.can_execute is True

    serialized = update_plan.to_dict()

    assert serialized["module_transitions"] == (
        module_plan.to_dict()
    )
    assert json.loads(
        json.dumps(serialized)
    ) == serialized


def test_safe_module_metadata_change_remains_executable(
    registry,
    manifest,
    tmp_path,
):
    output_path = tmp_path / "output"

    (
        candidate_plan,
        current_state,
        observation,
    ) = _update_context(
        registry,
        manifest,
        output_path,
    )

    candidate_state = (
        candidate_plan.desired_state
    )
    state_data = candidate_state.model_dump(
        mode="python"
    )

    current_fingerprint = (
        state_data["modules"][0][
            "manifest_sha256"
        ]
    )
    replacement_fingerprint = (
        "0" * 64
        if current_fingerprint != "0" * 64
        else "f" * 64
    )

    state_data["modules"][0][
        "manifest_sha256"
    ] = replacement_fingerprint

    candidate_plan.desired_state = (
        ProjectState.model_validate(
            state_data
        )
    )

    update_plan = build_project_update_plan(
        candidate_plan,
        current_state,
        observation,
    )

    module_changes = [
        transition
        for transition
        in update_plan.module_transitions.modules
        if transition.action == "update"
    ]

    assert len(module_changes) == 1
    assert module_changes[0].changed_fields == (
        "manifest_sha256",
    )
    assert (
        update_plan
        .module_transitions
        .has_changes
        is True
    )
    assert (
        update_plan
        .module_transitions
        .can_execute
        is True
    )
    assert update_plan.execution_plan is not None
    assert update_plan.can_execute is True
    assert update_plan.has_changes is True


def test_module_cycle_blocks_update_execution_plan(
    registry,
    manifest,
    tmp_path,
):
    output_path = tmp_path / "output"

    (
        candidate_plan,
        current_state,
        observation,
    ) = _update_context(
        registry,
        manifest,
        output_path,
    )

    binding = (
        candidate_plan
        .resolved_project
        .bindings[0]
    )

    reverse_binding = binding.model_copy(
        update={
            "binding_key": (
                f"{binding.binding_key}"
                "-update-cycle"
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

    update_plan = build_project_update_plan(
        candidate_plan,
        current_state,
        observation,
    )

    module_plan = update_plan.module_transitions

    assert module_plan.can_execute is False
    assert len(module_plan.conflicts) == 1
    assert (
        module_plan.conflicts[0].reason
        == "candidate_cycle"
    )
    assert {
        binding.consumer_module_key,
        binding.provider_module_key,
    } <= set(
        module_plan.conflicts[0].module_keys
    )

    assert update_plan.conflicts == ()
    assert update_plan.execution_plan is None
    assert update_plan.can_execute is False

    serialized = update_plan.to_dict()

    assert (
        serialized["can_execute"]
        is False
    )
    assert (
        serialized["execution_plan"]
        is None
    )
    assert (
        serialized["module_transitions"][
            "conflicts"
        ][0]["reason"]
        == "candidate_cycle"
    )