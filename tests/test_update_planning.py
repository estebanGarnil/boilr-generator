import json

import pytest

import boilr_generator.generation as generation_api
from boilr_generator.core.generation_plan import (
    PlannedFile,
    ProjectUpdatePlan,
)
from boilr_generator.generation import (
    ProjectGenerator,
    apply_reconciliation_plan,
    build_project_update_plan,
    observe_project,
)
from boilr_generator.state import (
    ProjectObservation,
    ProjectStateStorage,
    build_reconciliation_plan,
)


def _generated_project(
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

    return generator, storage, current_state


def _candidate_context(
    generator,
    manifest,
    output_path,
):
    candidate_plan = generator.plan(
        manifest=manifest,
        output_path=output_path,
    )
    observation = observe_project(output_path)

    assert observation is not None

    return candidate_plan, observation


def _change_for(
    update_plan: ProjectUpdatePlan,
    resource_id: str,
):
    return next(
        change
        for change in update_plan.changes
        if change.resource_id == resource_id
    )


def _resource_for_path(
    state,
    path: str,
):
    return next(
        resource
        for resource in state.resources
        if resource.materialized_path == path
    )


def test_unchanged_project_builds_noop_update_plan(
    registry,
    manifest,
    tmp_path,
):
    output_path = tmp_path / "output"
    generator, _, current_state = (
        _generated_project(
            registry,
            manifest,
            output_path,
        )
    )
    candidate_plan, observation = (
        _candidate_context(
            generator,
            manifest,
            output_path,
        )
    )

    update_plan = build_project_update_plan(
        candidate_plan,
        current_state,
        observation,
    )

    assert update_plan.can_execute is True
    assert update_plan.has_changes is False
    assert update_plan.has_filesystem_changes is False
    assert update_plan.desired_state == current_state
    assert update_plan.conflicts == ()
    assert all(
        change.action == "retain"
        for change in update_plan.changes
    )
    assert update_plan.summary == {
        "resources_count": len(
            current_state.resources
        ),
        "create_count": 0,
        "replace_count": 0,
        "remove_count": 0,
        "retain_count": len(
            current_state.resources
        ),
        "relocate_count": 0,
        "forget_count": 0,
        "filesystem_changes_count": 0,
        "conflicts_count": 0,
    }


def test_changed_desired_content_plans_safe_replacement(
    registry,
    manifest,
    tmp_path,
):
    output_path = tmp_path / "output"
    generator, _, current_state = (
        _generated_project(
            registry,
            manifest,
            output_path,
        )
    )
    candidate_plan, observation = (
        _candidate_context(
            generator,
            manifest,
            output_path,
        )
    )
    planned_file = next(
        item
        for item in candidate_plan.files
        if item.relative_destination_path == ".env"
    )
    planned_file.content = b"UPDATED=value\n"

    update_plan = build_project_update_plan(
        candidate_plan,
        current_state,
        observation,
    )
    change = _change_for(
        update_plan,
        planned_file.resource_id,
    )

    assert change.action == "replace"
    assert change.current_path == ".env"
    assert change.target_path == ".env"
    assert change.observed_status == "unchanged"
    assert change.changed_fields == (
        "content_size",
        "content_sha256",
    )
    assert update_plan.can_execute is True
    assert update_plan.has_filesystem_changes is True
    assert update_plan.conflicts == ()


def test_modified_resource_blocks_desired_replacement(
    registry,
    manifest,
    tmp_path,
):
    output_path = tmp_path / "output"
    generator, _, current_state = (
        _generated_project(
            registry,
            manifest,
            output_path,
        )
    )
    (output_path / ".env").write_bytes(
        b"LOCAL=value\n"
    )
    candidate_plan, observation = (
        _candidate_context(
            generator,
            manifest,
            output_path,
        )
    )
    planned_file = next(
        item
        for item in candidate_plan.files
        if item.relative_destination_path == ".env"
    )
    planned_file.content = b"DESIRED=value\n"

    update_plan = build_project_update_plan(
        candidate_plan,
        current_state,
        observation,
    )
    change = _change_for(
        update_plan,
        planned_file.resource_id,
    )

    assert change.action == "replace"
    assert change.observed_status == "modified"
    assert update_plan.can_execute is False
    assert [
        conflict.to_dict()
        for conflict in update_plan.conflicts
        if conflict.resource_id
        == planned_file.resource_id
    ] == [
        {
            "resource_id": planned_file.resource_id,
            "reason": "modified_resource",
            "path": ".env",
            "observed_status": "modified",
        }
    ]


def test_unchanged_desired_resource_preserves_local_modification(
    registry,
    manifest,
    tmp_path,
):
    output_path = tmp_path / "output"
    generator, _, current_state = (
        _generated_project(
            registry,
            manifest,
            output_path,
        )
    )
    (output_path / ".env").write_bytes(
        b"LOCAL=value\n"
    )
    candidate_plan, observation = (
        _candidate_context(
            generator,
            manifest,
            output_path,
        )
    )

    update_plan = build_project_update_plan(
        candidate_plan,
        current_state,
        observation,
    )
    resource = _resource_for_path(
        current_state,
        ".env",
    )
    change = _change_for(
        update_plan,
        resource.id,
    )

    assert change.action == "retain"
    assert change.observed_status == "modified"
    assert change.changed_fields == ()
    assert update_plan.can_execute is True
    assert update_plan.conflicts == ()
    assert update_plan.desired_state == current_state


def test_missing_desired_resource_is_safely_recreated(
    registry,
    manifest,
    tmp_path,
):
    output_path = tmp_path / "output"
    generator, _, current_state = (
        _generated_project(
            registry,
            manifest,
            output_path,
        )
    )
    resource = _resource_for_path(
        current_state,
        ".env",
    )
    (output_path / ".env").unlink()
    candidate_plan, observation = (
        _candidate_context(
            generator,
            manifest,
            output_path,
        )
    )

    update_plan = build_project_update_plan(
        candidate_plan,
        current_state,
        observation,
    )
    change = _change_for(
        update_plan,
        resource.id,
    )

    assert change.action == "create"
    assert change.observed_status == "missing"
    assert update_plan.can_execute is True
    assert update_plan.has_filesystem_changes is True
    assert update_plan.conflicts == ()


def test_removed_unchanged_resource_is_planned_for_removal(
    registry,
    manifest,
    tmp_path,
):
    output_path = tmp_path / "output"
    generator, _, current_state = (
        _generated_project(
            registry,
            manifest,
            output_path,
        )
    )
    resource = _resource_for_path(
        current_state,
        ".env",
    )
    candidate_plan, observation = (
        _candidate_context(
            generator,
            manifest,
            output_path,
        )
    )
    candidate_plan.files = [
        item
        for item in candidate_plan.files
        if item.resource_id != resource.id
    ]

    update_plan = build_project_update_plan(
        candidate_plan,
        current_state,
        observation,
    )
    change = _change_for(
        update_plan,
        resource.id,
    )

    assert change.action == "remove"
    assert change.current_path == ".env"
    assert change.target_path is None
    assert change.observed_status == "unchanged"
    assert update_plan.can_execute is True
    assert resource.id not in {
        item.id
        for item in update_plan.desired_state.resources
    }


def test_removed_modified_resource_is_a_conflict(
    registry,
    manifest,
    tmp_path,
):
    output_path = tmp_path / "output"
    generator, _, current_state = (
        _generated_project(
            registry,
            manifest,
            output_path,
        )
    )
    resource = _resource_for_path(
        current_state,
        ".env",
    )
    (output_path / ".env").write_bytes(
        b"LOCAL=value\n"
    )
    candidate_plan, observation = (
        _candidate_context(
            generator,
            manifest,
            output_path,
        )
    )
    candidate_plan.files = [
        item
        for item in candidate_plan.files
        if item.resource_id != resource.id
    ]

    update_plan = build_project_update_plan(
        candidate_plan,
        current_state,
        observation,
    )

    assert _change_for(
        update_plan,
        resource.id,
    ).action == "remove"
    assert update_plan.can_execute is False
    assert any(
        conflict.resource_id == resource.id
        and conflict.reason == "modified_resource"
        for conflict in update_plan.conflicts
    )


def test_new_resource_cannot_replace_untracked_file(
    registry,
    manifest,
    tmp_path,
):
    output_path = tmp_path / "output"
    generator, _, current_state = (
        _generated_project(
            registry,
            manifest,
            output_path,
        )
    )
    untracked_path = output_path / "notes.txt"
    untracked_path.write_bytes(b"user content")
    candidate_plan, observation = (
        _candidate_context(
            generator,
            manifest,
            output_path,
        )
    )
    candidate_plan.files.append(
        PlannedFile(
            source_path=None,
            destination_path=untracked_path,
            relative_destination_path="notes.txt",
            resource_id="core:notes",
            default_relative_path="notes.txt",
            operation="generate",
            action="overwrite",
            content=b"generated content",
        )
    )

    update_plan = build_project_update_plan(
        candidate_plan,
        current_state,
        observation,
    )
    change = _change_for(
        update_plan,
        "core:notes",
    )

    assert change.action == "create"
    assert update_plan.can_execute is False
    assert any(
        conflict.resource_id == "core:notes"
        and conflict.reason
        == "untracked_destination"
        and conflict.path == "notes.txt"
        for conflict in update_plan.conflicts
    )


def test_reconciled_move_keeps_materialized_path(
    registry,
    manifest,
    tmp_path,
):
    output_path = tmp_path / "output"
    generator, storage, current_state = (
        _generated_project(
            registry,
            manifest,
            output_path,
        )
    )
    resource = _resource_for_path(
        current_state,
        ".env",
    )
    (output_path / ".env").rename(
        output_path / ".env.local"
    )
    moved_observation = observe_project(
        output_path
    )

    assert moved_observation is not None

    reconciliation_plan = build_reconciliation_plan(
        current_state,
        moved_observation,
        {
            resource.id: ".env.local",
        },
    )
    apply_reconciliation_plan(
        output_path,
        reconciliation_plan,
    )

    reconciled_state = storage.read()

    assert reconciled_state is not None

    candidate_plan, observation = (
        _candidate_context(
            generator,
            manifest,
            output_path,
        )
    )
    update_plan = build_project_update_plan(
        candidate_plan,
        reconciled_state,
        observation,
    )
    change = _change_for(
        update_plan,
        resource.id,
    )
    desired_resource = next(
        item
        for item in update_plan.desired_state.resources
        if item.id == resource.id
    )

    assert change.action == "retain"
    assert change.current_path == ".env.local"
    assert change.target_path == ".env.local"
    assert desired_resource.default_path == ".env"
    assert desired_resource.desired_path == ".env"
    assert desired_resource.materialized_path == (
        ".env.local"
    )
    assert update_plan.can_execute is True
    assert update_plan.has_changes is False


def test_changed_desired_path_plans_relocation(
    registry,
    manifest,
    tmp_path,
):
    output_path = tmp_path / "output"
    generator, _, current_state = (
        _generated_project(
            registry,
            manifest,
            output_path,
        )
    )
    candidate_plan, observation = (
        _candidate_context(
            generator,
            manifest,
            output_path,
        )
    )
    planned_file = next(
        item
        for item in candidate_plan.files
        if item.relative_destination_path == ".env"
    )
    planned_file.destination_path = (
        output_path / ".env.production"
    )
    planned_file.relative_destination_path = (
        ".env.production"
    )

    update_plan = build_project_update_plan(
        candidate_plan,
        current_state,
        observation,
    )
    change = _change_for(
        update_plan,
        planned_file.resource_id,
    )
    desired_resource = next(
        item
        for item in update_plan.desired_state.resources
        if item.id == planned_file.resource_id
    )

    assert change.action == "relocate"
    assert change.current_path == ".env"
    assert change.target_path == ".env.production"
    assert change.changed_fields == (
        "desired_path",
    )
    assert desired_resource.default_path == ".env"
    assert desired_resource.desired_path == (
        ".env.production"
    )
    assert desired_resource.materialized_path == (
        ".env.production"
    )
    assert update_plan.can_execute is True
    assert update_plan.has_filesystem_changes is True


def test_unresolved_move_blocks_changed_desired_content(
    registry,
    manifest,
    tmp_path,
):
    output_path = tmp_path / "output"
    generator, _, current_state = (
        _generated_project(
            registry,
            manifest,
            output_path,
        )
    )
    resource = _resource_for_path(
        current_state,
        ".env",
    )
    (output_path / ".env").rename(
        output_path / ".env.local"
    )
    candidate_plan, observation = (
        _candidate_context(
            generator,
            manifest,
            output_path,
        )
    )
    planned_file = next(
        item
        for item in candidate_plan.files
        if item.resource_id == resource.id
    )
    planned_file.content = b"DESIRED=value\n"

    update_plan = build_project_update_plan(
        candidate_plan,
        current_state,
        observation,
    )

    assert _change_for(
        update_plan,
        resource.id,
    ).action == "replace"
    assert update_plan.can_execute is False
    assert any(
        conflict.resource_id == resource.id
        and conflict.reason == "unresolved_move"
        for conflict in update_plan.conflicts
    )


def test_update_plan_serialization_is_deterministic(
    registry,
    manifest,
    tmp_path,
):
    output_path = tmp_path / "output"
    generator, _, current_state = (
        _generated_project(
            registry,
            manifest,
            output_path,
        )
    )
    candidate_plan, observation = (
        _candidate_context(
            generator,
            manifest,
            output_path,
        )
    )

    update_plan = build_project_update_plan(
        candidate_plan,
        current_state,
        observation,
    )
    first = update_plan.to_dict()
    second = update_plan.to_dict()

    assert first == second
    assert json.loads(json.dumps(first)) == first
    assert first["output_path"] == str(output_path)
    assert first["can_execute"] is True
    assert first["has_changes"] is False
    assert first["conflicts"] == []
    assert first["current_state"] == (
        first["desired_state"]
    )


def test_update_plan_rejects_mismatched_observation(
    registry,
    manifest,
    tmp_path,
):
    output_path = tmp_path / "output"
    generator, _, current_state = (
        _generated_project(
            registry,
            manifest,
            output_path,
        )
    )
    candidate_plan, observation = (
        _candidate_context(
            generator,
            manifest,
            output_path,
        )
    )
    incomplete_observation = ProjectObservation(
        resources=observation.resources[:-1],
        untracked=observation.untracked,
    )

    with pytest.raises(
        ValueError,
        match="does not match",
    ):
        build_project_update_plan(
            candidate_plan,
            current_state,
            incomplete_observation,
        )


def test_generation_public_api_exports_update_planner():
    assert (
        generation_api.build_project_update_plan
        is build_project_update_plan
    )
    assert (
        build_project_update_plan.__module__
        == "boilr_generator.generation.update"
    )