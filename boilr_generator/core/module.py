from typing import Any 
from pathlib import Path

from pydantic import BaseModel, Field

from boilr_generator.modules.schemas import ModuleManifest



class ResolvedModule(BaseModel):
    manifest: ModuleManifest
    module_path: Path
    variables: dict[str, Any] = Field(default_factory=dict)
    options: dict[str, Any] = Field(default_factory=dict)

    @property
    def key(self) -> str:
        return self.manifest.meta.key
    
    @property
    def type(self) -> str:
        return self.manifest.meta.type

    @property
    def priority(self) -> int: 
        return self.manifest.assembly.priority
    
    def resolve_source_path(self, relative_path: str) -> Path: 
        return self.module_path / relative_path
    