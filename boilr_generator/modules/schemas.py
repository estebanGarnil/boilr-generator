from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, RootModel, model_validator

# --- META / ROLE ---

class ModuleMeta(BaseModel):
    name: str
    key: str
    type: str  # backend, frontend, database, proxy, etc.
    version: str
    description: str | None = None
    tags: list[str] = Field(default_factory=list)


class ModuleRole(BaseModel):
    group: str


# --- COMPATIBILITY ---

ALLOWED_TYPES = {"string", "int", "boolean", "list"}

# --- CAPABILITIES ---


class ProvidedCapability(BaseModel):
    """Capability exposed by a module."""

    capability: str = Field(min_length=1)
    values: dict[str, Any] = Field(default_factory=dict)


class RequiredCapability(BaseModel):
    """Capability consumed by a module."""

    model_config = ConfigDict(populate_by_name=True)

    capability: str = Field(min_length=1)
    binding_key: str = Field(
        alias="binding",
        min_length=1,
    )
    optional: bool = False
    unique: bool = True
    contract: dict[str, str] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_contract_types(self) -> "RequiredCapability":
        """Validate the declared capability value types."""
        invalid_types = sorted(
            set(self.contract.values()) - ALLOWED_TYPES
        )

        if invalid_types:
            raise ValueError(
                "Invalid capability contract types: "
                f"{', '.join(invalid_types)}"
            )

        return self

# --- EXTENSION POINTS / CONTRIBUTIONS ---

EXTENSION_POINT_TYPES = {
    "string",
    "int",
    "boolean",
    "list",
    "dict",
}

MERGE_STRATEGIES_BY_TYPE = {
    "string": {"replace"},
    "int": {"replace"},
    "boolean": {"replace"},
    "list": {
        "replace",
        "append",
        "append_unique",
    },
    "dict": {
        "replace",
        "deep_merge",
    },
}


class ExtensionPointDefinition(BaseModel):
    """Typed location accepting module contributions."""

    type: str
    merge: str = "replace"
    default: Any = None
    required: bool = False

    @model_validator(mode="after")
    def validate_definition(
        self,
    ) -> "ExtensionPointDefinition":
        """Validate type, merge strategy, and default value."""
        allowed_strategies = MERGE_STRATEGIES_BY_TYPE.get(
            self.type
        )

        if allowed_strategies is None:
            raise ValueError(
                f"Invalid extension point type: {self.type}"
            )

        if self.merge not in allowed_strategies:
            raise ValueError(

                    f"Merge strategy '{self.merge}' is not valid "
                    f"for extension point type '{self.type}'."

            )

        if (
            self.default is not None
            and not self._matches_type(self.default)
        ):
            raise ValueError(

                    "Invalid extension point default type: "
                    f"expected '{self.type}', got "
                    f"'{type(self.default).__name__}'."

            )

        return self

    def _matches_type(self, value: Any) -> bool:
        """Check the declared extension point type."""
        type_mapping: dict[str, type] = {
            "string": str,
            "int": int,
            "boolean": bool,
            "list": list,
            "dict": dict,
        }

        expected_type = type_mapping[self.type]

        if expected_type is int:
            return (
                isinstance(value, int)
                and not isinstance(value, bool)
            )

        return isinstance(value, expected_type)


class ContributionDeclaration(BaseModel):
    """Contribution targeting a module through a binding."""

    model_config = ConfigDict(populate_by_name=True)

    target_binding: str = Field(
        alias="target",
        min_length=1,
    )
    extension_point: str = Field(min_length=1)
    value: Any

# --- VARIABLES / OPTIONS ---

class VariableDefinition(BaseModel):
    type: str
    required: bool = False
    default: Any = None
    description: str | None = None

    @model_validator(mode="after")
    def validate_type(self) -> "VariableDefinition":
        if self.type not in ALLOWED_TYPES:
            raise ValueError(f"Invalid variable type: {self.type}")
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
    description: str | None = None

    @model_validator(mode="after")
    def validate_type(self) -> "OptionDefinition":
        if self.type not in ALLOWED_TYPES:
            raise ValueError(f"Invalid option type: {self.type}")
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


SOURCE_ID_PATTERN = r"^[a-z][a-z0-9-]*$"


ResourceInputKey = Annotated[
    str,
    Field(
        min_length=1,
        strict=True,
    ),
]


class ResourceInputs(BaseModel):
    """Resolved-project inputs consumed by one generated resource."""

    bindings: list[ResourceInputKey] = Field(
        default_factory=list
    )
    extension_points: list[ResourceInputKey] = Field(
        default_factory=list
    )

    @model_validator(mode="after")
    def validate_inputs(self) -> "ResourceInputs":
        """Reject duplicates and normalize deterministic ordering."""
        for field_name in (
            "bindings",
            "extension_points",
        ):
            values = getattr(self, field_name)

            if len(values) != len(set(values)):
                duplicates = sorted(
                    {
                        value
                        for value in values
                        if values.count(value) > 1
                    }
                )
                raise ValueError(
                    "Duplicate generated resource inputs are not "
                    f"allowed for '{field_name}': "
                    f"{', '.join(duplicates)}"
                )

            setattr(self, field_name, sorted(values))

        return self


class CopySource(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    id: str = Field(
        min_length=1,
        strict=True,
        pattern=SOURCE_ID_PATTERN,
    )
    from_: str = Field(alias="from")
    to: str
    strategy: Literal[
        "merge",
        "skip",
        "replace",
    ] = "merge"


class RenderSource(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    id: str = Field(
        min_length=1,
        strict=True,
        pattern=SOURCE_ID_PATTERN,
    )
    from_: str = Field(alias="from")
    to: str
    uses: ResourceInputs = Field(
        default_factory=ResourceInputs
    )

class ModuleSources(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    copy_sources: list[CopySource] = Field(
        default_factory=list,
        alias="copy",
    )
    render: list[RenderSource] = Field(
        default_factory=list
    )

    @model_validator(mode="after")
    def validate_unique_source_ids(
        self,
    ) -> "ModuleSources":
        source_ids = [
            source.id
            for source in [
                *self.copy_sources,
                *self.render,
            ]
        ]

        if len(source_ids) != len(set(source_ids)):
            raise ValueError(
                "Duplicate source identifiers are not allowed."
            )

        return self

# --- DOCKER / EXPORTS ---

class DockerService(RootModel[dict[str, Any]]):
    pass


class DockerConfig(BaseModel):
    uses: ResourceInputs = Field(
        default_factory=ResourceInputs
    )
    services: dict[str, DockerService] = Field(default_factory=dict)
    volumes: dict[str, Any] = Field(default_factory=dict)


class ExportEnv(RootModel[dict[str, str]]):
    pass


class ModuleExports(BaseModel):
    uses: ResourceInputs = Field(
        default_factory=ResourceInputs
    )
    env: ExportEnv | None = None


# --- DOCS ---

class ModuleDocs(BaseModel):
    summary: str | None = None
    notes: list[str] = Field(default_factory=list)


# --- ROOT MODEL ---

class ModuleManifest(BaseModel):
    meta: ModuleMeta
    role: ModuleRole
    dependencies: dict[str, list[str]] = Field(default_factory=dict)
    provides: list[ProvidedCapability] = Field(
        default_factory=list
    )
    requires: list[RequiredCapability] = Field(
        default_factory=list
    )
    extension_points: dict[
        str,
        ExtensionPointDefinition,
    ] = Field(default_factory=dict)

    contributions: list[
        ContributionDeclaration
    ] = Field(default_factory=list)
    variables: ModuleVariables = Field(default_factory=lambda: ModuleVariables({}))
    options: ModuleOptions = Field(default_factory=lambda: ModuleOptions({}))
    assembly: AssemblyConfig
    sources: ModuleSources = Field(default_factory=ModuleSources)
    docker: DockerConfig | None = None
    exports: ModuleExports | None = None
    docs: ModuleDocs | None = None

    @model_validator(mode="after")
    def validate_keys(self) -> "ModuleManifest":
        """Validate unique and normalized module contract keys."""
        if self.meta.key != self.meta.key.lower():
            raise ValueError("Module key must be lowercase.")

        provided_capabilities = [
            provider.capability
            for provider in self.provides
        ]

        if len(provided_capabilities) != len(
            set(provided_capabilities)
        ):
            raise ValueError(
                "Duplicate provided capabilities are not allowed."
            )

        binding_keys = [
            requirement.binding_key
            for requirement in self.requires
        ]

        if len(binding_keys) != len(set(binding_keys)):
            raise ValueError(
                "Duplicate capability binding keys are not allowed."
            )

        invalid_extension_point_keys = sorted(
            key
            for key in self.extension_points
            if not key.strip()
        )

        if invalid_extension_point_keys:
            raise ValueError(
                "Extension point keys cannot be empty."
            )

        declared_binding_keys = set(binding_keys)

        unknown_contribution_targets = sorted(
            {
                contribution.target_binding
                for contribution in self.contributions
                if contribution.target_binding
                not in declared_binding_keys
            }
        )

        if unknown_contribution_targets:
            raise ValueError(

                    "Contribution targets must reference declared "
                    "capability bindings: "
                    f"{', '.join(unknown_contribution_targets)}"

            )

        return self

    @model_validator(mode="after")
    def validate_resource_inputs(self) -> "ModuleManifest":
        """Validate inputs consumed by generated module resources."""
        declared_bindings = {
            requirement.binding_key
            for requirement in self.requires
        }
        declared_extension_points = set(
            self.extension_points
        )

        inputs_by_location = {
            f"sources.render[{source.id}]": source.uses
            for source in self.sources.render
        }

        if self.docker is not None:
            inputs_by_location["docker"] = self.docker.uses

        if self.exports is not None:
            inputs_by_location["exports"] = self.exports.uses

        unknown_bindings = sorted(
            (
                location,
                binding,
            )
            for location, inputs in inputs_by_location.items()
            for binding in inputs.bindings
            if binding not in declared_bindings
        )

        if unknown_bindings:
            references = ", ".join(
                f"{location}:{binding}"
                for location, binding in unknown_bindings
            )
            raise ValueError(
                "Generated resource inputs reference undeclared "
                f"capability bindings: {references}"
            )

        unknown_extension_points = sorted(
            (
                location,
                extension_point,
            )
            for location, inputs in inputs_by_location.items()
            for extension_point in inputs.extension_points
            if extension_point
            not in declared_extension_points
        )

        if unknown_extension_points:
            references = ", ".join(
                f"{location}:{extension_point}"
                for location, extension_point
                in unknown_extension_points
            )
            raise ValueError(
                "Generated resource inputs reference undeclared "
                f"extension points: {references}"
            )

        return self
