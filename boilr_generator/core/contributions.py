"""Domain models for extension points and contributions."""

from typing import Any

from pydantic import BaseModel, Field


class ExtensionPoint(BaseModel):
    """Resolved extension point exposed by one module."""

    module_key: str = Field(min_length=1)
    key: str = Field(min_length=1)
    value_type: str = Field(min_length=1)
    merge_strategy: str = Field(min_length=1)
    default: Any = None
    required: bool = False


class Contribution(BaseModel):
    """Resolved contribution targeting an extension point."""

    contributor_module_key: str = Field(min_length=1)
    target_module_key: str = Field(min_length=1)
    target_binding: str = Field(min_length=1)
    extension_point: str = Field(min_length=1)
    value: Any

class ExtensionPointValue(BaseModel):
    """Final value produced for one extension point."""

    module_key: str = Field(min_length=1)
    extension_point: str = Field(min_length=1)
    value: Any
    contributor_module_keys: list[str] = Field(
        default_factory=list
    )