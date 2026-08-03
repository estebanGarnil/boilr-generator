"""Module exception compatibility exports."""

from boilr_generator.exceptions import (
    DuplicateModuleError,
    ModuleError,
    ModuleLoadError,
    ModuleNotFoundError,
    ModuleSchemaError,
)

# Legacy alias.
ModuleValidationError = ModuleSchemaError

__all__ = [
    "DuplicateModuleError",
    "ModuleError",
    "ModuleLoadError",
    "ModuleNotFoundError",
    "ModuleSchemaError",
    "ModuleValidationError",
]