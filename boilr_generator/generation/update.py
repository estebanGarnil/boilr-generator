"""Read-only planning of safe generated-project updates."""

from boilr_generator.core.generation_plan import (
    GenerationPlan,
    PlannedFile,
    PlannedPathState,
    PlannedUpdateChange,
    PlannedUpdateConflict,
    ProjectUpdatePlan,
    UpdateConflictReason,
)
from boilr_generator.state.observation import (
    ProjectObservation,
    TrackedResourceObservation,
)
from boilr_generator.state.schemas import (
    ProjectState,
    StateResource,
)

_RESOURCE_COMPARISON_FIELDS = (
    "kind",
    "default_path",
    "desired_path",
    "management",
    "scope",
    "owner",
    "contributors",
    "content_size",
    "content_sha256",
    "mode",
    "link_target",
)
_FILESYSTEM_REPRESENTATION_FIELDS = (
    "kind",
    "content_size",
    "content_sha256",
    "mode",
    "link_target",
)


def _resource_from_planned_file(
    planned_file: PlannedFile,
) -> StateResource:
    """Build desired resource metadata independent of file action."""
    return StateResource(
        id=planned_file.resource_id,
        kind="file",
        default_path=(
            planned_file.default_relative_path
        ),
        desired_path=(
            planned_file.relative_destination_path
        ),
        materialized_path=(
            planned_file.relative_destination_path
        ),
        management="generated",
        scope="shared",
        owner=planned_file.owner,
        contributors=tuple(
            planned_file.contributors
        ),
        content_size=planned_file.content_size,
        content_sha256=(
            planned_file.content_sha256
        ),
        mode=planned_file.mode,
        link_target=None,
    )


def _desired_resources(
    candidate_plan: GenerationPlan,
) -> tuple[
    dict[str, PlannedFile],
    dict[str, StateResource],
]:
    """Collect all declared files, including skipped files."""
    files_by_id: dict[str, PlannedFile] = {}
    resources_by_id: dict[str, StateResource] = {}

    for planned_file in candidate_plan.files:
        resource_id = planned_file.resource_id

        if resource_id in files_by_id:
            raise ValueError(
                "Duplicate desired resource identifier: "
                f"'{resource_id}'."
            )

        files_by_id[resource_id] = planned_file
        resources_by_id[resource_id] = (
            _resource_from_planned_file(
                planned_file
            )
        )

    desired_paths = [
        resource.desired_path
        for resource in resources_by_id.values()
    ]

    if len(desired_paths) != len(set(desired_paths)):
        raise ValueError(
            "Desired resources must have unique paths."
        )

    return files_by_id, resources_by_id


def _index_observations(
    state: ProjectState,
    observation: ProjectObservation,
) -> dict[str, TrackedResourceObservation]:
    """Validate that an observation describes the current state."""
    observations_by_id: dict[
        str,
        TrackedResourceObservation,
    ] = {}

    for item in observation.resources:
        if item.resource_id in observations_by_id:
            raise ValueError(
                "Duplicate tracked resource observation: "
                f"'{item.resource_id}'."
            )

        observations_by_id[item.resource_id] = item

    resources_by_id = {
        resource.id: resource
        for resource in state.resources
    }
    expected_ids = set(resources_by_id)
    observed_ids = set(observations_by_id)

    if expected_ids != observed_ids:
        missing_ids = sorted(
            expected_ids - observed_ids
        )
        unexpected_ids = sorted(
            observed_ids - expected_ids
        )
        raise ValueError(
            "The project observation does not match the "
            "current state. "
            f"Missing: {missing_ids}. "
            f"Unexpected: {unexpected_ids}."
        )

    for resource_id, resource in resources_by_id.items():
        item = observations_by_id[resource_id]
        expected_metadata = (
            resource.materialized_path,
            resource.kind,
            resource.content_size,
            resource.content_sha256,
            resource.mode,
            resource.link_target,
        )
        observation_metadata = (
            item.materialized_path,
            item.expected_kind,
            item.expected_content_size,
            item.expected_content_sha256,
            item.expected_mode,
            item.expected_link_target,
        )

        if expected_metadata != observation_metadata:
            raise ValueError(
                "Tracked resource observation metadata is "
                "stale for resource "
                f"'{resource_id}'."
            )

    return observations_by_id


def _changed_fields(
    current: StateResource,
    desired: StateResource,
) -> tuple[str, ...]:
    """Return declarative resource fields changed by the update."""
    return tuple(
        field_name
        for field_name in _RESOURCE_COMPARISON_FIELDS
        if getattr(current, field_name)
        != getattr(desired, field_name)
    )


def _representation_changed(
    current: StateResource,
    desired: StateResource,
) -> bool:
    """Return whether materialized filesystem data must change."""
    return any(
        getattr(current, field_name)
        != getattr(desired, field_name)
        for field_name
        in _FILESYSTEM_REPRESENTATION_FIELDS
    )


def _resource_with_materialized_path(
    resource: StateResource,
    materialized_path: str,
) -> StateResource:
    """Create validated resource metadata for its final path."""
    data = resource.model_dump(mode="python")
    data["materialized_path"] = materialized_path
    return StateResource.model_validate(data)


def _drift_conflict_reason(
    status: str,
) -> UpdateConflictReason:
    """Map observed drift to one stable update conflict reason."""
    reasons: dict[str, UpdateConflictReason] = {
        "modified": "modified_resource",
        "type_changed": "type_changed_resource",
        "mode_changed": "mode_changed_resource",
        "moved": "unresolved_move",
        "move_candidate": "unresolved_move",
        "ambiguous_move": "unresolved_move",
    }

    try:
        return reasons[status]
    except KeyError as error:
        raise ValueError(
            "Unsupported tracked resource status for an "
            f"unsafe transition: '{status}'."
        ) from error


def _existing_paths(
    initial_state: list[PlannedPathState],
) -> set[str]:
    """Return occupied output paths captured by the candidate plan."""
    return {
        path_state.relative_path
        for path_state in initial_state
        if (
            path_state.exists
            and path_state.relative_path != "."
        )
    }


def _destination_conflict(
    *,
    resource_id: str,
    target_path: str,
    occupied_paths: set[str],
    tracked_paths: dict[str, str],
) -> PlannedUpdateConflict | None:
    """Reject writing a resource over an occupied foreign path."""
    if target_path not in occupied_paths:
        return None

    tracked_resource_id = tracked_paths.get(
        target_path
    )
    reason: UpdateConflictReason = (
        "tracked_destination"
        if tracked_resource_id is not None
        and tracked_resource_id != resource_id
        else "untracked_destination"
    )

    return PlannedUpdateConflict(
        resource_id=resource_id,
        reason=reason,
        path=target_path,
    )


def _validated_desired_state(
    candidate_state: ProjectState,
    resources: list[StateResource],
) -> ProjectState:
    """Build validated desired state with final materialized paths."""
    data = candidate_state.model_dump(mode="python")
    data["resources"] = tuple(resources)
    return ProjectState.model_validate(data)


def build_project_update_plan(
    candidate_plan: GenerationPlan,
    current_state: ProjectState,
    observation: ProjectObservation,
) -> ProjectUpdatePlan:
    """Compare stored, observed, and newly desired project state."""
    candidate_state = candidate_plan.desired_state

    if candidate_state is None:
        raise ValueError(
            "A project update requires a candidate desired state."
        )

    current_identity = (
        current_state.project.name,
        current_state.project.type,
    )
    candidate_identity = (
        candidate_state.project.name,
        candidate_state.project.type,
    )

    if current_identity != candidate_identity:
        raise ValueError(
            "The candidate plan targets a different project."
        )

    _, desired_by_id = _desired_resources(
        candidate_plan
    )
    current_by_id = {
        resource.id: resource
        for resource in current_state.resources
    }
    observations_by_id = _index_observations(
        current_state,
        observation,
    )
    occupied_paths = _existing_paths(
        candidate_plan.initial_output_state
    )
    tracked_paths = {
        resource.materialized_path: resource.id
        for resource in current_state.resources
    }

    if len(tracked_paths) != len(
        current_state.resources
    ):
        raise ValueError(
            "Current state resources must have unique "
            "materialized paths."
        )

    changes: list[PlannedUpdateChange] = []
    conflicts: list[PlannedUpdateConflict] = []
    final_resources: list[StateResource] = []
    all_resource_ids = sorted(
        set(current_by_id) | set(desired_by_id)
    )

    for resource_id in all_resource_ids:
        current = current_by_id.get(resource_id)
        desired = desired_by_id.get(resource_id)

        if current is None and desired is not None:
            target_path = desired.desired_path
            final_resources.append(desired)
            changes.append(
                PlannedUpdateChange(
                    resource_id=resource_id,
                    action="create",
                    current_path=None,
                    target_path=target_path,
                    observed_status=None,
                )
            )
            conflict = _destination_conflict(
                resource_id=resource_id,
                target_path=target_path,
                occupied_paths=occupied_paths,
                tracked_paths=tracked_paths,
            )

            if conflict is not None:
                conflicts.append(conflict)

            continue

        if current is not None and desired is None:
            item = observations_by_id[resource_id]
            action = (
                "forget"
                if item.status == "missing"
                else "remove"
            )
            changes.append(
                PlannedUpdateChange(
                    resource_id=resource_id,
                    action=action,
                    current_path=(
                        current.materialized_path
                    ),
                    target_path=None,
                    observed_status=item.status,
                )
            )

            if item.status not in {
                "unchanged",
                "missing",
            }:
                conflicts.append(
                    PlannedUpdateConflict(
                        resource_id=resource_id,
                        reason=(
                            _drift_conflict_reason(
                                item.status
                            )
                        ),
                        path=(
                            current.materialized_path
                        ),
                        observed_status=item.status,
                    )
                )

            continue

        if current is None or desired is None:
            raise AssertionError(
                "Resource transition classification is incomplete."
            )

        item = observations_by_id[resource_id]
        declarative_path_changed = (
            desired.desired_path
            != current.desired_path
        )
        target_path = (
            desired.desired_path
            if declarative_path_changed
            else current.materialized_path
        )
        final_resource = (
            _resource_with_materialized_path(
                desired,
                target_path,
            )
        )
        final_resources.append(final_resource)
        changed_fields = _changed_fields(
            current,
            desired,
        )
        physical_path_changed = (
            target_path
            != current.materialized_path
        )
        representation_changed = (
            _representation_changed(
                current,
                desired,
            )
        )
        unsafe_source_status = (
            item.status
            not in {
                "unchanged",
                "missing",
            }
        )

        if (
            physical_path_changed
            and item.status != "missing"
        ):
            action = "relocate"
        elif item.status == "missing":
            action = "create"
        elif representation_changed:
            action = "replace"
        else:
            action = "retain"

        changes.append(
            PlannedUpdateChange(
                resource_id=resource_id,
                action=action,
                current_path=(
                    current.materialized_path
                ),
                target_path=target_path,
                observed_status=item.status,
                changed_fields=changed_fields,
            )
        )

        if (
            physical_path_changed
            or action == "create"
        ):
            conflict = _destination_conflict(
                resource_id=resource_id,
                target_path=target_path,
                occupied_paths=occupied_paths,
                tracked_paths=tracked_paths,
            )

            if conflict is not None:
                conflicts.append(conflict)

            if (
                physical_path_changed
                and unsafe_source_status
            ):
                conflicts.append(
                    PlannedUpdateConflict(
                        resource_id=resource_id,
                        reason=(
                            _drift_conflict_reason(
                                item.status
                            )
                        ),
                        path=(
                            current.materialized_path
                        ),
                        observed_status=item.status,
                    )
                )
        elif (
            representation_changed
            and unsafe_source_status
        ):
            conflicts.append(
                PlannedUpdateConflict(
                    resource_id=resource_id,
                    reason=(
                        _drift_conflict_reason(
                            item.status
                        )
                    ),
                    path=(
                        current.materialized_path
                    ),
                    observed_status=item.status,
                )
            )

    desired_state = _validated_desired_state(
        candidate_state,
        final_resources,
    )

    return ProjectUpdatePlan(
        candidate_plan=candidate_plan,
        current_state=current_state,
        observation=observation,
        desired_state=desired_state,
        changes=tuple(changes),
        conflicts=tuple(
            sorted(
                conflicts,
                key=lambda conflict: (
                    conflict.resource_id,
                    conflict.reason,
                    conflict.path,
                ),
            )
        ),
    )