"""Planning for explicit generated-resource reconciliation."""

from collections import Counter
from collections.abc import Mapping
from dataclasses import asdict, dataclass
from typing import Any, Literal

from boilr_generator.state.observation import (
    ProjectObservation,
    TrackedResourceObservation,
)
from boilr_generator.state.schemas import (
    ProjectState,
    StateResource,
)
from boilr_generator.state.serialization import (
    fingerprint_model,
)

AcceptedMoveStatus = Literal[
    "move_candidate",
    "ambiguous_move",
]


@dataclass(frozen=True, slots=True)
class ReconciliationMove:
    """One explicitly accepted generated-resource move."""

    resource_id: str
    from_path: str
    to_path: str
    detected_as: AcceptedMoveStatus

    def to_dict(self) -> dict[str, str]:
        """Return a JSON-compatible accepted move."""
        return asdict(self)


@dataclass(frozen=True, slots=True)
class ReconciliationPlan:
    """Pure plan for updating one committed project state."""

    current_state: ProjectState
    desired_state: ProjectState
    moves: tuple[ReconciliationMove, ...]

    @property
    def base_state_sha256(self) -> str:
        """Fingerprint the state used to construct the plan."""
        return fingerprint_model(self.current_state)

    @property
    def desired_state_sha256(self) -> str:
        """Fingerprint the state produced by the plan."""
        return fingerprint_model(self.desired_state)

    @property
    def has_changes(self) -> bool:
        """Return whether the plan changes persisted state."""
        return bool(self.moves)

    @property
    def summary(self) -> dict[str, int]:
        """Return deterministic reconciliation counters."""
        return {
            "moves_count": len(self.moves),
        }

    def to_dict(self) -> dict[str, Any]:
        """Return a deterministic JSON-compatible plan."""
        return {
            "base_state_sha256": self.base_state_sha256,
            "desired_state_sha256": (
                self.desired_state_sha256
            ),
            "moves": [
                move.to_dict()
                for move in self.moves
            ],
            "desired_state": (
                self.desired_state.model_dump(
                    mode="json"
                )
            ),
            "summary": self.summary,
            "has_changes": self.has_changes,
        }


def _index_observations(
    state: ProjectState,
    observation: ProjectObservation,
) -> dict[str, TrackedResourceObservation]:
    """Validate that an observation belongs to the given state."""
    observation_ids = [
        resource.resource_id
        for resource in observation.resources
    ]
    duplicate_ids = sorted(
        resource_id
        for resource_id, count in Counter(
            observation_ids
        ).items()
        if count > 1
    )

    if duplicate_ids:
        raise ValueError(
            "Duplicate observed resource identifiers: "
            f"{', '.join(duplicate_ids)}."
        )

    observations_by_id = {
        resource.resource_id: resource
        for resource in observation.resources
    }
    state_by_id = {
        resource.id: resource
        for resource in state.resources
    }
    missing_ids = sorted(
        set(state_by_id) - set(observations_by_id)
    )
    unknown_ids = sorted(
        set(observations_by_id) - set(state_by_id)
    )

    if missing_ids or unknown_ids:
        details = []

        if missing_ids:
            details.append(
                "missing: "
                f"{', '.join(missing_ids)}"
            )

        if unknown_ids:
            details.append(
                "unknown: "
                f"{', '.join(unknown_ids)}"
            )

        raise ValueError(
            "Project observation does not match state "
            f"resources ({'; '.join(details)})."
        )

    mismatched_ids = sorted(
        resource_id
        for resource_id, resource
        in state_by_id.items()
        if observations_by_id[
            resource_id
        ].materialized_path
        != resource.materialized_path
    )

    if mismatched_ids:
        raise ValueError(
            "Project observation uses stale materialized paths: "
            f"{', '.join(mismatched_ids)}."
        )

    return observations_by_id


def _updated_resource(
    resource: StateResource,
    materialized_path: str,
) -> StateResource:
    """Validate one accepted materialized path."""
    resource_data = resource.model_dump(
        mode="python"
    )
    resource_data["materialized_path"] = (
        materialized_path
    )

    return StateResource.model_validate(
        resource_data
    )


def build_reconciliation_plan(
    state: ProjectState,
    observation: ProjectObservation,
    accepted_moves: Mapping[str, str],
) -> ReconciliationPlan:
    """Plan explicit resource moves without mutating state or files."""
    observations_by_id = _index_observations(
        state,
        observation,
    )
    state_ids = {
        resource.id
        for resource in state.resources
    }
    unknown_selections = sorted(
        set(accepted_moves) - state_ids
    )

    if unknown_selections:
        raise ValueError(
            "Unknown reconciliation resource identifiers: "
            f"{', '.join(unknown_selections)}."
        )

    accepted_paths = list(
        accepted_moves.values()
    )
    duplicate_paths = sorted(
        path
        for path, count in Counter(
            accepted_paths
        ).items()
        if count > 1
    )

    if duplicate_paths:
        raise ValueError(
            "A candidate path cannot be accepted for multiple "
            "resources: "
            f"{', '.join(duplicate_paths)}."
        )

    moves: list[ReconciliationMove] = []
    desired_resources: list[StateResource] = []

    for resource in state.resources:
        if resource.id not in accepted_moves:
            desired_resources.append(resource)
            continue

        accepted_path = accepted_moves[
            resource.id
        ]
        observed = observations_by_id[
            resource.id
        ]

        if observed.status not in {
            "move_candidate",
            "ambiguous_move",
        }:
            raise ValueError(
                "Resource is not awaiting move reconciliation: "
                f"'{resource.id}' ({observed.status})."
            )

        if accepted_path not in observed.candidate_paths:
            raise ValueError(
                "Path is not a candidate for resource "
                f"'{resource.id}': '{accepted_path}'."
            )

        desired_resources.append(
            _updated_resource(
                resource,
                accepted_path,
            )
        )
        moves.append(
            ReconciliationMove(
                resource_id=resource.id,
                from_path=(
                    resource.materialized_path
                ),
                to_path=accepted_path,
                detected_as=observed.status,
            )
        )

    desired_paths = [
        resource.materialized_path
        for resource in desired_resources
    ]
    conflicting_paths = sorted(
        path
        for path, count in Counter(
            desired_paths
        ).items()
        if count > 1
    )

    if conflicting_paths:
        raise ValueError(
            "Reconciliation would assign the same materialized "
            "path to multiple resources: "
            f"{', '.join(conflicting_paths)}."
        )

    desired_state_data = state.model_dump(
        mode="python"
    )
    desired_state_data["resources"] = [
        resource.model_dump(mode="python")
        for resource in desired_resources
    ]
    desired_state = ProjectState.model_validate(
        desired_state_data
    )

    return ReconciliationPlan(
        current_state=state,
        desired_state=desired_state,
        moves=tuple(moves),
    )