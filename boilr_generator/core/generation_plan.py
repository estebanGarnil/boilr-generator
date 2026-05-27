from dataclasses import dataclass, field
from pathlib import Path

from boilr_generator.core.project import ResolvedProject

@dataclass(slots=True)
class PlannedFile:
    path: Path 
    action: str # create | overwrite

@dataclass(slots=True)
class GenerationPlan:
    resolved_project: ResolvedProject
    output_path: Path
    files: list[PlannedFile] = field(default_factory=list)
    docker_services: list[str] = field(default_factory=list)
    env_variables: list[str] = field(default_factory=list)
