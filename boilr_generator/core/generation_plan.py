"""Generation planning models."""

from __future__ import annotations
from collections import Counter
from dataclasses import asdict, dataclass, field
from hashlib import sha256
from pathlib import Path
from typing import TYPE_CHECKING, Any, Literal

from boilr_generator.core.project import ResolvedProject
from boilr_generator.state.schemas import ProjectState
if TYPE_CHECKING:
    from boilr_generator.state.observation import (
        ProjectObservation,
    )

PathKind = Literal[
    "file",
    "directory",
    "symlink",
]
DirectoryReason = Literal[
    "output",
    "parent",
]
RemovalReason = Literal[
    "clean",
    "replace",
]


@dataclass(slots=True)
class PlannedPathState:
    """Expected state of one filesystem path before execution."""

    path: Path
    relative_path: str
    exists: bool
    kind: PathKind | None = None
    content_size: int | None = None
    content_sha256: str | None = None
    mode: int | None = None
    link_target: str | None = None


@dataclass(slots=True)
class PlannedFile:
    """One complete file operation prepared by the plan."""

    source_path: Path | None
    destination_path: Path
    relative_destination_path: str
    resource_id: str
    default_relative_path: str
    operation: str
    action: str
    content: bytes = field(repr=False)
    module: str | None = None
    contributors: list[str] = field(default_factory=list)
    mode: int | None = None

    def __post_init__(self) -> None:
        """Normalize deterministic ownership provenance."""
        contributors = set(self.contributors)

        if self.module is not None:
            contributors.add(self.module)

        self.contributors = sorted(contributors)

    @property
    def owner(self) -> str | None:
        """Return the module that declares this resource."""
        return self.module

    @property
    def content_size(self) -> int:
        """Return the prepared content size in bytes."""
        return len(self.content)

    @property
    def content_sha256(self) -> str:
        """Return a stable fingerprint of prepared content."""
        return sha256(self.content).hexdigest()


@dataclass(slots=True)
class PlannedDirectory:
    """One directory that execution must create."""

    path: Path
    relative_path: str
    reason: DirectoryReason
    module: str | None = None


@dataclass(slots=True)
class PlannedRemoval:
    """One exact path that execution must remove."""

    path: Path
    relative_path: str
    kind: PathKind
    module: str | None = None
    reason: RemovalReason = "replace"


@dataclass(slots=True)
class GenerationPlan:
    """Complete and inspectable project generation contract."""

    resolved_project: ResolvedProject
    output_path: Path
    initial_output_state: list[PlannedPathState] = field(
        default_factory=list
    )
    directories: list[PlannedDirectory] = field(
        default_factory=list
    )
    files: list[PlannedFile] = field(default_factory=list)
    removals: list[PlannedRemoval] = field(
        default_factory=list
    )
    docker_services: list[str] = field(
        default_factory=list
    )
    env_variables: list[str] = field(
        default_factory=list
    )
    clean_output: bool = False
    desired_state: ProjectState | None = None

    @property
    def files_to_create(self) -> list[PlannedFile]:
        return [
            file
            for file in self.files
            if file.action == "create"
        ]

    @property
    def files_to_overwrite(self) -> list[PlannedFile]:
        return [
            file
            for file in self.files
            if file.action == "overwrite"
        ]

    @property
    def files_to_skip(self) -> list[PlannedFile]:
        return [
            file
            for file in self.files
            if file.action == "skip"
        ]

    @property
    def summary(self) -> dict[str, int]:
        return {
            "modules_count": len(
                self.resolved_project.modules
            ),
            "initial_paths_count": len(
                self.initial_output_state
            ),
            "directories_to_create": len(
                self.directories
            ),
            "files_count": len(self.files),
            "files_to_create": len(
                self.files_to_create
            ),
            "files_to_overwrite": len(
                self.files_to_overwrite
            ),
            "files_to_skip": len(
                self.files_to_skip
            ),
            "removals_count": len(self.removals),
            "clean_removals_count": sum(
                removal.reason == "clean"
                for removal in self.removals
            ),
            "replace_removals_count": sum(
                removal.reason == "replace"
                for removal in self.removals
            ),
            "docker_services_count": len(
                self.docker_services
            ),
            "env_variables_count": len(
                self.env_variables
            ),
            "content_bytes": sum(
                file.content_size
                for file in self.files
            ),
            "content_bytes_to_write": sum(
                file.content_size
                for file in self.files
                if file.action != "skip"
            ),
        }

    def to_dict(self) -> dict[str, Any]:
        """Serialize contract metadata without file contents."""
        data = asdict(self)

        data["output_path"] = str(self.output_path)
        data["resolved_project"] = {
            "name": self.resolved_project.project.name,
            "type": self.resolved_project.project.type,
            "version": self.resolved_project.project.version,
            "modules": (
                self.resolved_project.list_module_keys()
            ),
        }
        data["desired_state"] = (
            self.desired_state.model_dump(mode="json")
            if self.desired_state is not None
            else None
        )

        for path_state in data["initial_output_state"]:
            path_state["path"] = str(
                path_state["path"]
            )

        for directory in data["directories"]:
            directory["path"] = str(
                directory["path"]
            )

        for serialized_file, planned_file in zip(
            data["files"],
            self.files,
            strict=True,
        ):
            serialized_file.pop("content", None)

            serialized_file["source_path"] = (
                str(serialized_file["source_path"])
                if serialized_file["source_path"]
                is not None
                else None
            )
            serialized_file["destination_path"] = str(
                serialized_file["destination_path"]
            )
            serialized_file["content_size"] = (
                planned_file.content_size
            )
            serialized_file["content_sha256"] = (
                planned_file.content_sha256
            )

        for removal in data["removals"]:
            removal["path"] = str(removal["path"])

        data["summary"] = self.summary

        return data

UpdateResourceAction = Literal[
    "create",
    "replace",
    "remove",
    "retain",
    "relocate",
    "forget",
]
UpdateConflictReason = Literal[
    "modified_resource",
    "type_changed_resource",
    "mode_changed_resource",
    "unresolved_move",
    "untracked_destination",
    "tracked_destination",
]


@dataclass(frozen=True, slots=True)
class PlannedUpdateChange:
    """One resource transition requested by an update."""

    resource_id: str
    action: UpdateResourceAction
    current_path: str | None
    target_path: str | None
    observed_status: str | None
    changed_fields: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        """Return one JSON-compatible transition."""
        data = asdict(self)
        data["changed_fields"] = list(
            self.changed_fields
        )
        return data


@dataclass(frozen=True, slots=True)
class PlannedUpdateConflict:
    """One unsafe resource transition blocking an update."""

    resource_id: str
    reason: UpdateConflictReason
    path: str
    observed_status: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Return one JSON-compatible conflict."""
        return asdict(self)


@dataclass(slots=True)
class ProjectUpdatePlan:
    """Read-only comparison of current and desired project state."""

    candidate_plan: GenerationPlan = field(repr=False)
    current_state: ProjectState
    observation: ProjectObservation = field(repr=False)
    desired_state: ProjectState
    changes: tuple[PlannedUpdateChange, ...]
    conflicts: tuple[PlannedUpdateConflict, ...] = ()

    @property
    def can_execute(self) -> bool:
        """Return whether every transition is currently safe."""
        return not self.conflicts

    @property
    def has_filesystem_changes(self) -> bool:
        """Return whether execution would mutate project files."""
        mutating_actions = {
            "create",
            "replace",
            "remove",
            "relocate",
        }
        return any(
            change.action in mutating_actions
            for change in self.changes
        )

    @property
    def has_changes(self) -> bool:
        """Return whether filesystem or persisted state differs."""
        return (
            self.has_filesystem_changes
            or self.desired_state != self.current_state
        )

    @property
    def summary(self) -> dict[str, int]:
        """Return deterministic transition counters."""
        counts = Counter(
            change.action
            for change in self.changes
        )

        return {
            "resources_count": len(self.changes),
            "create_count": counts["create"],
            "replace_count": counts["replace"],
            "remove_count": counts["remove"],
            "retain_count": counts["retain"],
            "relocate_count": counts["relocate"],
            "forget_count": counts["forget"],
            "filesystem_changes_count": sum(
                counts[action]
                for action in (
                    "create",
                    "replace",
                    "remove",
                    "relocate",
                )
            ),
            "conflicts_count": len(self.conflicts),
        }

    def to_dict(self) -> dict[str, Any]:
        """Serialize the complete update decision contract."""
        return {
            "output_path": str(
                self.candidate_plan.output_path
            ),
            "current_state": (
                self.current_state.model_dump(
                    mode="json"
                )
            ),
            "desired_state": (
                self.desired_state.model_dump(
                    mode="json"
                )
            ),
            "observation": self.observation.to_dict(),
            "changes": [
                change.to_dict()
                for change in self.changes
            ],
            "conflicts": [
                conflict.to_dict()
                for conflict in self.conflicts
            ],
            "summary": self.summary,
            "can_execute": self.can_execute,
            "has_filesystem_changes": (
                self.has_filesystem_changes
            ),
            "has_changes": self.has_changes,
        }