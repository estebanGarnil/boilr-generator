"""Read-only classification of tracked project resources."""

from __future__ import annotations

from collections import Counter
from collections.abc import Sequence
from dataclasses import (
    asdict,
    dataclass,
    replace,
)
from pathlib import PurePosixPath
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
    "moved",
    "move_candidate",
    "ambiguous_move",
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
    "moved",
    "move_candidate",
    "ambiguous_move",
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
    candidate_paths: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-compatible observation."""
        data = asdict(self)
        data["candidate_paths"] = list(
            self.candidate_paths
        )
        return data


@dataclass(frozen=True, slots=True)
class UntrackedResourceObservation:
    """Observed resource absent from the stored baseline."""

    path: str
    kind: PathKind
    content_size: int | None
    content_sha256: str | None
    mode: int | None
    link_target: str | None

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
    untracked: tuple[
        UntrackedResourceObservation,
        ...,
    ] = ()

    @property
    def has_drift(self) -> bool:
        """Return whether the observed project has drift."""
        return (
            bool(self.untracked)
            or any(
                resource.status != "unchanged"
                for resource in self.resources
            )
        )

    @property
    def summary(self) -> dict[str, int]:
        """Count resources by deterministic status."""
        counts = Counter(
            resource.status
            for resource in self.resources
        )

        summary = {
            status: counts[status]
            for status in _TRACKED_RESOURCE_STATUSES
        }
        summary["untracked"] = len(
            self.untracked
        )

        return summary

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-compatible project observation."""
        return {
            "resources": [
                resource.to_dict()
                for resource in self.resources
            ],
            "untracked": [
                resource.to_dict()
                for resource in self.untracked
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
    *,
    status_override: (
        TrackedResourceStatus | None
    ) = None,
    candidate_paths: tuple[str, ...] = (),
) -> TrackedResourceObservation:
    """Build the complete observation for one resource."""
    status = (
        status_override
        if status_override is not None
        else _classify_resource(
            resource,
            observed,
        )
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
        candidate_paths=candidate_paths,
    )


def _matches_resource_fingerprint(
    resource: StateResource,
    observed: PlannedPathState,
) -> bool:
    """Check whether an unknown path may be a moved resource."""
    if (
        not observed.exists
        or observed.kind != resource.kind
    ):
        return False

    if resource.kind == "file":
        return (
            resource.content_sha256 is not None
            and observed.content_sha256
            == resource.content_sha256
            and observed.content_size
            == resource.content_size
        )

    if resource.kind == "symlink":
        return (
            resource.link_target is not None
            and observed.link_target
            == resource.link_target
        )

    return False


def _is_implicit_container(
    observed: PlannedPathState,
    resources: Sequence[StateResource],
    all_observed: Sequence[PlannedPathState],
) -> bool:
    """Ignore directories used only to contain exact resources."""
    if observed.kind != "directory":
        return False

    directory_path = PurePosixPath(
        observed.relative_path
    )

    is_tracked_ancestor = any(
        directory_path
        in PurePosixPath(
            resource.materialized_path
        ).parents
        for resource in resources
    )

    if is_tracked_ancestor:
        return True

    return any(
        other.exists
        and other.relative_path
        != observed.relative_path
        and directory_path
        in PurePosixPath(
            other.relative_path
        ).parents
        for other in all_observed
    )


def _build_untracked_observation(
    observed: PlannedPathState,
) -> UntrackedResourceObservation:
    """Build one exact untracked-resource observation."""
    if observed.kind is None:
        raise ValueError(
            "An existing observed path must have a kind: "
            f"'{observed.relative_path}'."
        )

    return UntrackedResourceObservation(
        path=observed.relative_path,
        kind=observed.kind,
        content_size=observed.content_size,
        content_sha256=(
            observed.content_sha256
        ),
        mode=observed.mode,
        link_target=observed.link_target,
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

        if (
            path_state.exists
            and path_state.kind is None
        ):
            raise ValueError(
                "An existing observed path must have a kind: "
                f"'{path_state.relative_path}'."
            )

        observed_by_path[
            path_state.relative_path
        ] = path_state

    resources = tuple(
        sorted(
            state.resources,
            key=lambda item: item.id,
        )
    )
    tracked_paths = {
        resource.materialized_path
        for resource in resources
    }

    initial_observations = {
        resource.id: _build_observation(
            resource,
            observed_by_path.get(
                resource.materialized_path
            ),
        )
        for resource in resources
    }

    unmatched_observed = tuple(
        observed_by_path[path]
        for path in sorted(observed_by_path)
        if (
            observed_by_path[path].exists
            and path not in tracked_paths
        )
    )

    missing_resources = tuple(
        resource
        for resource in resources
        if initial_observations[
            resource.id
        ].status == "missing"
    )

    candidate_paths_by_resource = {
        resource.id: tuple(
            observed.relative_path
            for observed in unmatched_observed
            if _matches_resource_fingerprint(
                resource,
                observed,
            )
        )
        for resource in missing_resources
    }

    candidate_usage = Counter(
        candidate_path
        for candidate_paths
        in candidate_paths_by_resource.values()
        for candidate_path in candidate_paths
    )
    matched_candidate_paths = set(
        candidate_usage
    )

    final_observations: list[
        TrackedResourceObservation
    ] = []

    for resource in resources:
        initial = initial_observations[
            resource.id
        ]
        candidate_paths = (
            candidate_paths_by_resource.get(
                resource.id,
                (),
            )
        )

        if (
            initial.status != "missing"
            or not candidate_paths
        ):
            final_observations.append(
                initial
            )
            continue

        if (
            len(candidate_paths) == 1
            and candidate_usage[
                candidate_paths[0]
            ] == 1
        ):
            candidate_path = candidate_paths[0]
            candidate = observed_by_path[
                candidate_path
            ]

            final_observations.append(
                _build_observation(
                    resource,
                    candidate,
                    status_override=(
                        "move_candidate"
                    ),
                    candidate_paths=(
                        candidate_paths
                    ),
                )
            )
            continue

        final_observations.append(
            replace(
                initial,
                status="ambiguous_move",
                candidate_paths=(
                    candidate_paths
                ),
            )
        )

    all_observed = tuple(
        observed_by_path[path]
        for path in sorted(observed_by_path)
    )

    untracked = tuple(
        _build_untracked_observation(
            observed
        )
        for observed in unmatched_observed
        if (
            observed.relative_path
            not in matched_candidate_paths
            and not _is_implicit_container(
                observed,
                resources,
                all_observed,
            )
        )
    )

    return ProjectObservation(
        resources=tuple(
            final_observations
        ),
        untracked=untracked,
    )