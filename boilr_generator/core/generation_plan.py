"""Generation planning models."""

from dataclasses import dataclass, field
from pathlib import Path

from boilr_generator.core.project import ResolvedProject

@dataclass(slots=True)
class PlannedFile:
    source_path: Path | None 
    destination_path: Path
    relative_destination_path: str
    operation: str # "copy" | "render" | "generate"
    action: str # create | overwrite | skip
    module: str | None = None


@dataclass(slots=True)
class GenerationPlan:
    resolved_project: ResolvedProject
    output_path: Path
    files: list[PlannedFile] = field(default_factory=list)
    docker_services: list[str] = field(default_factory=list)
    env_variables: list[str] = field(default_factory=list)

    @property
    def files_to_create(self) -> list[PlannedFile]:
        return [file for file in self.files if file.action == "create"]
    
    @property
    def files_to_overwrite(self) -> list[PlannedFile]:
        return [file for file in self.files if file.action == "overwrite"]

    @property
    def files_to_skip(self) -> list[PlannedFile]:
        return [file for file in self.files if file.action == "skip"]
    
    @property
    def summary(self) -> dict[str, int]:
        return {
            "modules_count": len(self.resolved_project.modules),
            "files_count": len(self.files), 
            "files_to_create": len(self.files_to_create),
            "files_to_overwrite": len(self.files_to_overwrite),
            "files_to_skip": len(self.files_to_skip),
            "docker_services_count": len(self.docker_services),
            "env_variables_count": len(self.env_variables),
        }
