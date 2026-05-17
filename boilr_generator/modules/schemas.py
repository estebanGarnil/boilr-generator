from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field, RootModel, model_validator

from boilr_generator.core import ModuleVariableError

# --- META / ROLE ---

class ModuleMeta(BaseModel):
    name: str
    key: str
    type: str  # backend, frontend, database, proxy, etc.
    version: str
    description: Optional[str] = None
    tags: List[str] = Field(default_factory=list)


class ModuleRole(BaseModel):
    group: str  # backend, frontend, database...
    unique: bool = False


# --- REQUIREMENTS ---

class RequirementItem(BaseModel):
    type: str  # database, cache, proxy...
    unique: bool = False


class ModuleRequirements(BaseModel):
    mandatory: List[RequirementItem] = Field(default_factory=list)
    optional: List[RequirementItem] = Field(default_factory=list)

    def mandatory_types(self) -> List[str]:
        return [r.type for r in self.mandatory]

    def optional_types(self) -> List[str]:
        return [r.type for r in self.optional]


# --- COMPATIBILITY ---

class ModuleCompatibility(BaseModel):
    matrix: Dict[str, List[str]] = Field(default_factory=dict)

    @model_validator(mode="before")
    def normalize(cls, data: Any) -> Any:
        # Permet d'accepter directement le dict du YAML
        # et le ranger dans "matrix"
        if isinstance(data, dict):
            return {"matrix": data}
        return data

    def is_compatible(self, other_type: str, other_key: str) -> bool:
        if other_type not in self.matrix:
            return True  # pas de contrainte
        return other_key in self.matrix[other_type]


# --- VARIABLES / OPTIONS ---

ALLOWED_TYPES = {"string", "int", "boolean", "list"}


class VariableDefinition(BaseModel):
    type: str
    required: bool = False
    default: Any = None
    description: Optional[str] = None

    @model_validator(mode="after")
    def validate_type(self) -> "VariableDefinition":
        if self.type not in ALLOWED_TYPES:
            raise ModuleVariableError(f"Invalid variable type: {self.type}")
        return self


class ModuleVariables(RootModel[dict[str, VariableDefinition]]):
    def get(self, name: str) -> VariableDefinition | None:
        return self.root.get(name)

    def keys(self) -> list[str]:
        return list(self.root.keys())

    def items(self):
        return self.root.items()



class OptionDefinition(BaseModel):
    type: str
    default: Any = None
    description: Optional[str] = None

    @model_validator(mode="after")
    def validate_type(self) -> "OptionDefinition":
        if self.type not in ALLOWED_TYPES:
            raise ModuleVariableError(f"Invalid option type: {self.type}")
        return self


class ModuleOptions(RootModel[dict[str, OptionDefinition]]):
    def get(self, name: str) -> OptionDefinition | None:
        return self.root.get(name)

    def keys(self) -> list[str]:
        return list(self.root.keys())

    def items(self):
        return self.root.items()


# --- ASSEMBLY / SOURCES ---

class AssemblyConfig(BaseModel):
    priority: int = 0
    destination_root: str


class CopySource(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    from_: str = Field(alias="from")
    to: str
    strategy: str = "merge"


class RenderSource(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    from_: str = Field(alias="from")
    to: str

class ModuleSources(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    copy_sources: list[CopySource] = Field(default_factory=list, alias="copy")
    render: list[RenderSource] = Field(default_factory=list)


# --- DOCKER / EXPORTS ---

class DockerService(RootModel[dict[str, Any]]):
    pass


class DockerConfig(BaseModel):
    services: Dict[str, DockerService] = Field(default_factory=dict)
    volumes: dict[str, Any] = Field(default_factory=dict)


class ExportEnv(RootModel[dict[str, str]]):
    pass


class ModuleExports(BaseModel):
    env: Optional[ExportEnv] = None


# --- DOCS ---

class ModuleDocs(BaseModel):
    summary: Optional[str] = None
    notes: List[str] = Field(default_factory=list)


# --- ROOT MODEL ---

class ModuleManifest(BaseModel):
    meta: ModuleMeta
    role: ModuleRole
    requirements: ModuleRequirements = Field(default_factory=ModuleRequirements)
    dependencies: dict[str, list[str]] = Field(default_factory=dict)
    compatibility: ModuleCompatibility = Field(default_factory=ModuleCompatibility)
    variables: ModuleVariables = Field(default_factory=lambda: ModuleVariables({}))
    options: ModuleOptions = Field(default_factory=lambda: ModuleOptions({}))    
    assembly: AssemblyConfig
    sources: ModuleSources = Field(default_factory=ModuleSources)
    docker: Optional[DockerConfig] = None
    exports: Optional[ModuleExports] = None
    docs: Optional[ModuleDocs] = None

    @model_validator(mode="after")
    def validate_keys(self) -> "ModuleManifest":
        # Cohérence simple
        if self.meta.key != self.meta.key.lower():
            raise ModuleVariableError("Module key must be lowercase.")
        return self

    # --- helpers utiles ---
    def is_compatible_with(self, other: "ModuleManifest") -> bool:
        return self.compatibility.is_compatible(
            other.meta.type,
            other.meta.key,
        )