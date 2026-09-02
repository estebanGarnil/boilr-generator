"""Read-only classification of tracked project resources."""

from __future__ import annotations

from collections import Counter
from collections.abc import Sequence
from dataclasses import asdict, dataclass
from typing import TYPE_CHECKING, Any, Literal

from boilr_generator.state.schemas import (
    ProjectState,
    StateResource,
)

if TYPE_CHECKING:
    from boilr_generator.core.generation_plan import (
        PathKind,
        PlannedPathState,
    )

TrackedResourceStatus = Literal[
    "unchanged",
    "modified",
    "missing",
    "type_changed",
    "mode_changed",
]

_TRACKED_RESOURCE_STATUSES: tuple[
    TrackedResourceStatus,
    ...,
] = (
    "unchanged",
    "modified",
    "missing",
    "type_changed",
    "mode_changed",
)


@dataclass(frozen=True, slots=True)
class TrackedResourceObservation:
    """Observed state of one resource from the stored baseline."""

    resource_id: str
    materialized_path: str
    observed_path: str | None
    status: TrackedResourceStatus
    expected_kind: PathKind
    observed_kind: PathKind | None
    expected_content_size: int | None
    observed_content_size: int | None
    expected_content_sha256: str | None
    observed_content_sha256: str | None
    expected_mode: int | None
    observed_mode: int | None
    expected_link_target: str | None
    observed_link_target: str | None

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-compatible observation."""
        return asdict(self)


@dataclass(frozen=True, slots=True)
class ProjectObservation:
    """Read-only comparison with one stored project state."""

    resources: tuple[
        TrackedResourceObservation,
        ...,
    ]

    @property
    def has_drift(self) -> bool:
        """Return whether at least one resource changed."""
        return any(
            resource.status != "unchanged"
            for resource in self.resources
        )

    @property
    def summary(self) -> dict[str, int]:
        """Count resources by deterministic status."""
        counts = Counter(
            resource.status
            for resource in self.resources
        )

        return {
            status: counts[status]
            for status in _TRACKED_RESOURCE_STATUSES
        }

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-compatible project observation."""
        return {
            "resources": [
                resource.to_dict()
                for resource in self.resources
            ],
            "summary": self.summary,
            "has_drift": self.has_drift,
        }


def _classify_resource(
    resource: StateResource,
    observed: PlannedPathState | None,
) -> TrackedResourceStatus:
    """Classify one resource at its materialized path."""
    if observed is None or not observed.exists:
        return "missing"

    if observed.kind != resource.kind:
        return "type_changed"

    if resource.kind == "file":
        content_changed = (
            observed.content_size
            != resource.content_size
            or observed.content_sha256
            != resource.content_sha256
        )

        if content_changed:
            return "modified"

    if (
        resource.kind == "symlink"
        and observed.link_target
        != resource.link_target
    ):
        return "modified"

    if (
        resource.mode is not None
        and observed.mode != resource.mode
    ):
        return "mode_changed"

    return "unchanged"


def _build_observation(
    resource: StateResource,
    observed: PlannedPathState | None,
) -> TrackedResourceObservation:
    """Build the complete observation for one resource."""
    status = _classify_resource(
        resource,
        observed,
    )

    existing_observation = (
        observed
        if observed is not None
        and observed.exists
        else None
    )

    return TrackedResourceObservation(
        resource_id=resource.id,
        materialized_path=(
            resource.materialized_path
        ),
        observed_path=(
            existing_observation.relative_path
            if existing_observation is not None
            else None
        ),
        status=status,
        expected_kind=resource.kind,
        observed_kind=(
            existing_observation.kind
            if existing_observation is not None
            else None
        ),
        expected_content_size=(
            resource.content_size
        ),
        observed_content_size=(
            existing_observation.content_size
            if existing_observation is not None
            else None
        ),
        expected_content_sha256=(
            resource.content_sha256
        ),
        observed_content_sha256=(
            existing_observation.content_sha256
            if existing_observation is not None
            else None
        ),
        expected_mode=resource.mode,
        observed_mode=(
            existing_observation.mode
            if existing_observation is not None
            else None
        ),
        expected_link_target=(
            resource.link_target
        ),
        observed_link_target=(
            existing_observation.link_target
            if existing_observation is not None
            else None
        ),
    )


def classify_tracked_resources(
    state: ProjectState,
    observed_state: Sequence[
        PlannedPathState
    ],
) -> ProjectObservation:
    """Compare tracked resources with captured filesystem paths."""
    observed_by_path: dict[
        str,
        PlannedPathState,
    ] = {}

    for path_state in observed_state:
        if path_state.relative_path == ".":
            continue

        if (
            path_state.relative_path
            in observed_by_path
        ):
            raise ValueError(
                "Duplicate observed filesystem path: "
                f"'{path_state.relative_path}'."
            )

        observed_by_path[
            path_state.relative_path
        ] = path_state

    resources = tuple(
        _build_observation(
            resource,
            observed_by_path.get(
                resource.materialized_path
            ),
        )
        for resource in sorted(
            state.resources,
            key=lambda item: item.id,
        )
    )

    return ProjectObservation(
        resources=resources
    )