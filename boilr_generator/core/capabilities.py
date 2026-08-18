"""Domain models for capability resolution."""

from typing import Any

from pydantic import BaseModel, Field


class CapabilityProvider(BaseModel):
    """Represents one module providing a capability."""

    module_key: str = Field(min_length=1)
    capability: str = Field(min_length=1)
    version: str = Field(min_length=1)
    tags: list[str] = Field(default_factory=list)
    values: dict[str, Any] = Field(default_factory=dict)


class CapabilityProviderSelection(BaseModel):
    """Normalized explicit provider selection."""

    provider_module_key: str | None = Field(
        default=None,
        min_length=1,
    )
    version_specifier: str | None = Field(
        default=None,
        min_length=1,
    )
    required_tags: list[str] = Field(
        default_factory=list
    )


class CapabilityRequirement(BaseModel):
    """Represents one capability required by a module."""

    module_key: str = Field(min_length=1)
    binding_key: str = Field(min_length=1)
    capability: str = Field(min_length=1)
    optional: bool = False
    unique: bool = True
    contract: dict[str, str] = Field(default_factory=dict)


class CapabilityBinding(BaseModel):
    """Connects one consumer requirement to one provider."""

    binding_key: str = Field(min_length=1)
    capability: str = Field(min_length=1)
    consumer_module_key: str = Field(min_length=1)
    provider_module_key: str = Field(min_length=1)
    values: dict[str, Any] = Field(default_factory=dict)