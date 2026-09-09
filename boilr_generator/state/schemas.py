"""Persistent generated-project state models."""

from pathlib import PurePosixPath, PureWindowsPath
from typing import Annotated, Literal, Self

from pydantic import (
    AfterValidator,
    BaseModel,
    ConfigDict,
    Field,
    StrictInt,
    StringConstraints,
    field_validator,
    model_validator,
)

NonEmptyString = Annotated[
    str,
    StringConstraints(
        strip_whitespace=True,
        min_length=1,
        strict=True,
    ),
]
Sha256 = Annotated[
    str,
    StringConstraints(
        pattern=r"^[0-9a-f]{64}$",
        strict=True,
    ),
]
NonNegativeInt = Annotated[
    StrictInt,
    Field(ge=0),
]
FileMode = Annotated[
    StrictInt,
    Field(ge=0, le=0o7777),
]


def _validate_canonical_relative_posix_path(
    value: str,
    *,
    allow_root: bool,
    allow_internal: bool,
) -> str:
    """Validate one canonical relative POSIX path."""
    if "\\" in value:
        raise ValueError("Backslashes are not allowed in state paths.")

    posix_path = PurePosixPath(value)
    windows_path = PureWindowsPath(value)

    if (
        posix_path.is_absolute()
        or windows_path.is_absolute()
        or windows_path.drive
    ):
        raise ValueError("Absolute paths are not allowed in state.")

    if ".." in posix_path.parts:
        raise ValueError("Parent traversal is not allowed in state paths.")

    normalized = posix_path.as_posix()

    if normalized != value:
        raise ValueError("State paths must be canonical POSIX paths.")

    if normalized == "." and not allow_root:
        raise ValueError("The output root cannot be a managed resource.")

    if (
        not allow_internal
        and posix_path.parts
        and posix_path.parts[0] == ".boilr"
    ):
        raise ValueError("The .boilr directory is reserved for internal state.")

    return value


def _validate_resource_path(value: str) -> str:
    return _validate_canonical_relative_posix_path(
        value,
        allow_root=False,
        allow_internal=False,
    )


def _validate_module_destination(value: str) -> str:
    return _validate_canonical_relative_posix_path(
        value,
        allow_root=True,
        allow_internal=False,
    )


ResourcePath = Annotated[
    NonEmptyString,
    AfterValidator(_validate_resource_path),
]
ModuleDestination = Annotated[
    NonEmptyString,
    AfterValidator(_validate_module_destination),
]
ResourceKind = Literal[
    "file",
    "directory",
    "symlink",
]
ResourceManagement = Literal["generated"]
ResourceScope = Literal[
    "shared",
    "development",
    "production",
]
ModuleOrigin = Literal["builtin"]


class StateModel(BaseModel):
    """Strict immutable base for persisted state values."""

    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        str_strip_whitespace=True,
    )


class StateProject(StateModel):
    """Project metadata stored without user manifest values."""

    name: NonEmptyString
    type: NonEmptyString
    version: NonEmptyString
    manifest_sha256: Sha256


class StateModule(StateModel):
    """One resolved module recorded in generated-project state."""

    key: NonEmptyString
    version: NonEmptyString
    origin: ModuleOrigin
    manifest_sha256: Sha256
    destination: ModuleDestination

    @field_validator("key")
    @classmethod
    def validate_normalized_key(cls, value: str) -> str:
        if value != value.lower():
            raise ValueError("State module keys must be lowercase.")

        return value


class StateBinding(StateModel):
    """One resolved capability binding between two modules."""

    consumer_module: NonEmptyString
    binding: NonEmptyString
    capability: NonEmptyString
    provider_module: NonEmptyString

    @property
    def identity(self) -> tuple[str, str]:
        """Return the binding identity unique within one project."""
        return self.consumer_module, self.binding


class StateResource(StateModel):
    """One generated filesystem resource managed by Boilr."""

    id: NonEmptyString
    kind: ResourceKind
    default_path: ResourcePath
    desired_path: ResourcePath
    materialized_path: ResourcePath
    management: ResourceManagement
    scope: ResourceScope
    owner: NonEmptyString | None
    contributors: tuple[NonEmptyString, ...]
    content_size: NonNegativeInt | None
    content_sha256: Sha256 | None
    mode: FileMode | None
    link_target: ResourcePath | None

    @field_validator("contributors")
    @classmethod
    def normalize_contributors(
        cls,
        value: tuple[str, ...],
    ) -> tuple[str, ...]:
        if len(value) != len(set(value)):
            raise ValueError("Resource contributors must be unique.")

        return tuple(sorted(value))

    @model_validator(mode="after")
    def validate_kind_metadata(self) -> Self:
        if self.kind == "file":
            if (
                self.content_size is None
                or self.content_sha256 is None
            ):
                raise ValueError(
                    "File resources require content size and SHA-256."
                )

            if self.link_target is not None:
                raise ValueError(
                    "File resources cannot define a link target."
                )

        elif self.kind == "directory":
            if (
                self.content_size is not None
                or self.content_sha256 is not None
                or self.mode is not None
                or self.link_target is not None
            ):
                raise ValueError(
                    "Directory resources cannot define file or link metadata."
                )

        elif (
            self.content_size is not None
            or self.content_sha256 is not None
            or self.mode is not None
            or self.link_target is None
        ):
            raise ValueError(
                "Symbolic-link resources require only a link target."
            )

        return self


class ProjectState(StateModel):
    """Complete versioned state of one generated project."""

    schema_version: Literal[1]
    generator_version: NonEmptyString
    project: StateProject
    modules: tuple[StateModule, ...] = Field(min_length=1)
    bindings: tuple[StateBinding, ...]
    resources: tuple[StateResource, ...]

    @field_validator("modules")
    @classmethod
    def sort_modules(
        cls,
        value: tuple[StateModule, ...],
    ) -> tuple[StateModule, ...]:
        return tuple(sorted(value, key=lambda module: module.key))

    @field_validator("bindings")
    @classmethod
    def sort_bindings(
        cls,
        value: tuple[StateBinding, ...],
    ) -> tuple[StateBinding, ...]:
        return tuple(sorted(value, key=lambda binding: binding.identity))

    @field_validator("resources")
    @classmethod
    def sort_resources(
        cls,
        value: tuple[StateResource, ...],
    ) -> tuple[StateResource, ...]:
        return tuple(sorted(value, key=lambda resource: resource.id))

    @model_validator(mode="after")
    def validate_references_and_identities(self) -> Self:
        module_keys = [module.key for module in self.modules]

        if len(module_keys) != len(set(module_keys)):
            raise ValueError("State module keys must be unique.")

        binding_identities = [
            binding.identity
            for binding in self.bindings
        ]

        if len(binding_identities) != len(set(binding_identities)):
            raise ValueError("State binding identities must be unique.")

        resource_ids = [resource.id for resource in self.resources]

        if len(resource_ids) != len(set(resource_ids)):
            raise ValueError("State resource identifiers must be unique.")

        known_modules = set(module_keys)

        for binding in self.bindings:
            referenced_modules = {
                binding.consumer_module,
                binding.provider_module,
            }
            unknown_modules = referenced_modules - known_modules

            if unknown_modules:
                raise ValueError(
                    "State bindings reference unknown modules: "
                    f"{', '.join(sorted(unknown_modules))}."
                )

        for resource in self.resources:
            referenced_modules = set(resource.contributors)

            if resource.owner is not None:
                referenced_modules.add(resource.owner)

            unknown_modules = referenced_modules - known_modules

            if unknown_modules:
                raise ValueError(
                    f"State resource '{resource.id}' references unknown "
                    f"modules: {', '.join(sorted(unknown_modules))}."
                )

        return self
