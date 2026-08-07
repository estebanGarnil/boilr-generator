"""Compatibility exports for the canonical Boilr exception hierarchy."""

from boilr_generator.exceptions import (
    BoilrError,
    DuplicateModuleError,
    ExecutionError,
    GenerationError,
    IncompatibleModuleError,
    InvalidVariableTypeError,
    ManifestError,
    ManifestParseError,
    MissingRequirementError,
    ModuleError,
    ModuleNotFoundError,
    ModuleSchemaError,
    OutputDirectoryError,
    ResolutionError,
    TemplateRenderError,
)

# Legacy aliases kept temporarily for backward compatibility.
ManifestParsingError = ManifestParseError
RegistryError = ModuleError
InvalidModuleDefinitionError = ModuleSchemaError
ResolverError = ResolutionError
ModuleRequirementError = MissingRequirementError
ModuleCompatibilityError = IncompatibleModuleError
ModuleVariableError = InvalidVariableTypeError

__all__ = [
    "BoilrError",
    "DuplicateModuleError",
    "ExecutionError",
    "GenerationError",
    "IncompatibleModuleError",
    "InvalidModuleDefinitionError",
    "InvalidVariableTypeError",
    "ManifestError",
    "ManifestParseError",
    "ManifestParsingError",
    "MissingRequirementError",
    "ModuleCompatibilityError",
    "ModuleError",
    "ModuleNotFoundError",
    "ModuleRequirementError",
    "ModuleSchemaError",
    "ModuleVariableError",
    "OutputDirectoryError",
    "RegistryError",
    "ResolutionError",
    "ResolverError",
    "TemplateRenderError",
]