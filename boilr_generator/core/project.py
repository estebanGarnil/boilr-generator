from pydantic import BaseModel, Field

from boilr_generator.core.module import ResolvedModule
from boilr_generator.manifest.schemas import ProjectInfo


class ResolvedProject(BaseModel): 
    project: ProjectInfo
    modules: list[ResolvedModule] = Field(default_factory=list)

    def get_module(self, key: str) -> ResolvedModule | None:
        return next((module for module in self.modules if module.key == key), None)
    
    def has_module(self, key: str) -> bool: 
        return self.get_module(key) is not None
    
    def list_module_keys(self) -> list[str]:
        return [module.key for module in self.modules]
    
    def list_modules_by_type(self, module_type: str) -> list[ResolvedModule]:
        return [module for module in self.modules if module.type == module_type]
    
    def ordered_modules(self) -> list[ResolvedModule]:
        return sorted(self.modules, key=lambda module: module.priority)