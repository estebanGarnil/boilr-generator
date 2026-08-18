"""Generation planning models."""

from dataclasses import asdict, dataclass, field
from hashlib import sha256
from pathlib import Path
from typing import Any, Literal

from boilr_generator.core.project import ResolvedProject

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
    operation: str
    action: str
    content: bytes = field(repr=False)
    module: str | None = None
    mode: int | None = None

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
    module: str | None = None
    reason: RemovalReason = "replace"
    kind: PathKind | None = None


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