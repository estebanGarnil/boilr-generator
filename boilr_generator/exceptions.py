"""Canonical exception hierarchy for the Boilr generator."""

from collections.abc import Mapping
from typing import Any, ClassVar


class BoilrError(Exception):
    """Base exception for every expected Boilr error."""

    code: ClassVar[str] = "boilr_error"

    def __init__(
        self,
        message: str,
        *,
        module_key: str | None = None,
        field_path: str | None = None,
        context: Mapping[str, Any] | None = None,
        suggestion: str | None = None,
    ) -> None:
        super().__init__(message)

        self.message = message
        self.module_key = module_key
        self.field_path = field_path
        self.context = dict(context or {})
        self.suggestion = suggestion


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------


class ConfigurationError(BoilrError):
    """Base exception for invalid Boilr configuration."""

    code = "configuration_error"


# ---------------------------------------------------------------------------
# Project manifests
# ---------------------------------------------------------------------------


class ManifestError(BoilrError):
    """Base exception for project manifest errors."""

    code = "manifest_error"


class ManifestNotFoundError(ManifestError):
    """Raised when a requested project manifest does not exist."""

    code = "manifest_not_found"


class ManifestLoadError(ManifestError):
    """Raised when a project manifest cannot be read."""

    code = "manifest_load_error"


class ManifestParseError(ManifestError):
    """Raised when a project manifest cannot be parsed."""

    code = "manifest_parse_error"


class ManifestSchemaError(ManifestError):
    """Raised when a project manifest does not match its schema."""

    code = "manifest_schema_error"


# ---------------------------------------------------------------------------
# Modules
# ---------------------------------------------------------------------------


class ModuleError(BoilrError):
    """Base exception for module-related errors."""

    code = "module_error"


class ModuleNotFoundError(ModuleError):
    """Raised when a requested module cannot be found."""

    code = "module_not_found"


class DuplicateModuleError(ModuleError):
    """Raised when multiple modules use the same unique key."""

    code = "duplicate_module"


class ModuleLoadError(ModuleError):
    """Raised when a module manifest cannot be loaded."""

    code = "module_load_error"


class ModuleSchemaError(ModuleError):
    """Raised when a module manifest does not match its schema."""

    code = "module_schema_error"


# ---------------------------------------------------------------------------
# Resolution
# ---------------------------------------------------------------------------


class ResolutionError(BoilrError):
    """Base exception for project resolution errors."""

    code = "resolution_error"


class MissingRequirementError(ResolutionError):
    """Raised when a mandatory legacy module requirement is missing."""

    code = "missing_requirement"


class AmbiguousRequirementError(ResolutionError):
    """Raised when a unique requirement has multiple candidates."""

    code = "ambiguous_requirement"


class IncompatibleModuleError(ResolutionError):
    """Raised when selected modules are incompatible."""

    code = "incompatible_module"


class MissingVariableError(ResolutionError):
    """Raised when a required module variable is missing."""

    code = "missing_variable"

class UnknownVariableError(ResolutionError):
    """Raised when a project provides an undeclared variable."""

    code = "unknown_variable"


class UnknownOptionError(ResolutionError):
    """Raised when a project provides an undeclared option."""

    code = "unknown_option"


class InvalidOptionTypeError(ResolutionError):
    """Raised when a module option has an invalid type."""

    code = "invalid_option_type"

class InvalidVariableTypeError(ResolutionError):
    """Raised when a module variable has an invalid type."""

    code = "invalid_variable_type"


class MissingCapabilityError(ResolutionError):
    """Raised when no provider satisfies a required capability."""

    code = "missing_capability"


class AmbiguousProviderError(ResolutionError):
    """Raised when multiple providers satisfy a unique capability."""

    code = "ambiguous_provider"


class BindingError(ResolutionError):
    """Raised when a capability binding cannot be created."""

    code = "binding_error"


class DependencyCycleError(ResolutionError):
    """Raised when an invalid dependency cycle is detected."""

    code = "dependency_cycle"


# ---------------------------------------------------------------------------
# Contributions
# ---------------------------------------------------------------------------


class ContributionError(BoilrError):
    """Base exception for contribution-related errors."""

    code = "contribution_error"


class UnknownExtensionPointError(ContributionError):
    """Raised when a contribution targets an unknown extension point."""

    code = "unknown_extension_point"


class InvalidContributionError(ContributionError):
    """Raised when a contribution does not match its declared contract."""

    code = "invalid_contribution"


class ContributionConflictError(ContributionError):
    """Raised when multiple contributions cannot be merged."""

    code = "contribution_conflict"


# ---------------------------------------------------------------------------
# Generation
# ---------------------------------------------------------------------------


class GenerationError(BoilrError):
    """Base exception for generation planning and rendering errors."""

    code = "generation_error"


class SourceNotFoundError(GenerationError):
    """Raised when a module source file or directory cannot be found."""

    code = "source_not_found"

class UnsafePathError(GenerationError):
    """Raised when a path escapes its allowed directory."""

    code = "unsafe_path"

class FileConflictError(GenerationError):
    """Raised when multiple operations conflict over the same file."""

    code = "file_conflict"


class DockerConflictError(GenerationError):
    """Raised when Docker contributions contain conflicting definitions."""

    code = "docker_conflict"


class EnvironmentConflictError(GenerationError):
    """Raised when environment variables contain conflicting definitions."""

    code = "environment_conflict"


class TemplateRenderError(GenerationError):
    """Raised when a template cannot be rendered."""

    code = "template_render_error"


# ---------------------------------------------------------------------------
# Execution
# ---------------------------------------------------------------------------


class ExecutionError(BoilrError):
    """Base exception for failures while executing a generation plan."""

    code = "execution_error"


class OutputDirectoryError(ExecutionError):
    """Raised when the output directory cannot be prepared or written."""

    code = "output_directory_error"


__all__ = [
    "AmbiguousProviderError",
    "AmbiguousRequirementError",
    "BindingError",
    "BoilrError",
    "ConfigurationError",
    "ContributionConflictError",
    "ContributionError",
    "DependencyCycleError",
    "DockerConflictError",
    "DuplicateModuleError",
    "EnvironmentConflictError",
    "ExecutionError",
    "FileConflictError",
    "GenerationError",
    "IncompatibleModuleError",
    "InvalidContributionError",
    "InvalidOptionTypeError",
    "InvalidVariableTypeError",
    "ManifestError",
    "ManifestLoadError",
    "ManifestNotFoundError",
    "ManifestParseError",
    "ManifestSchemaError",
    "MissingCapabilityError",
    "MissingRequirementError",
    "MissingVariableError",
    "ModuleError",
    "ModuleLoadError",
    "ModuleNotFoundError",
    "ModuleSchemaError",
    "OutputDirectoryError",
    "ResolutionError",
    "SourceNotFoundError",
    "UnsafePathError",
    "TemplateRenderError",
    "UnknownExtensionPointError",
    "UnknownOptionError",
    "UnknownVariableError",
]
