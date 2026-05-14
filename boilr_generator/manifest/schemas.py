from typing import Any

from pydantic import BaseModel, Field, model_validator


class ProjectInfo(BaseModel):
    name: str 
    type: str
    version: str = "1.0.0"

class ProjectModule(BaseModel):
    key: str
    variables: dict[str, Any] = Field(default_factory=dict)
    options: dict[str, Any] = Field(default_factory=dict)

class ProjectManifest(BaseModel):
    project: ProjectInfo
    modules: list[ProjectModule]

    @model_validator(mode="after")
    def validate_unique_modules(self) -> "ProjectManifest":
        keys = [module.key for module in self.modules]

        if len(keys) != len(set(keys)):
            raise ValueError("Duplicate modules are not allowed.")
        
        return self
    
    def get_module(self, key: str) -> ProjectModule | None:
        return next((module for module in self.modules if module.key == key), None)

    def has_module(self, key: str) -> bool:
        return self.get_module(key) is not None
    
    def list_module_keys(self) -> list[str]:
        return [module.key for module in self.modules]
    
    