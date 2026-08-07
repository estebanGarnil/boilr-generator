"""Resolver exception compatibility exports."""

from boilr_generator.exceptions import (
    AmbiguousProviderError,
    AmbiguousRequirementError,
    BindingError,
    DependencyCycleError,
    IncompatibleModuleError,
    InvalidVariableTypeError,
    MissingCapabilityError,
    MissingRequirementError,
    MissingVariableError,
    ResolutionError,
)

# Legacy aliases.
ResolverError = ResolutionError
ModuleResolutionError = ResolutionError

__all__ = [
    "AmbiguousProviderError",
    "AmbiguousRequirementError",
    "BindingError",
    "DependencyCycleError",
    "IncompatibleModuleError",
    "InvalidVariableTypeError",
    "MissingCapabilityError",
    "MissingRequirementError",
    "MissingVariableError",
    "ModuleResolutionError",
    "ResolutionError",
    "ResolverError",
]