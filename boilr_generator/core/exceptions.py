"""Custom exceptions for the Boilr generator engine."""


class BoilrError(Exception):
    """Base exception for all Boilr engine errors."""


class ManifestError(BoilrError):
    """Raised when the project manifest is invalid."""


class ManifestParsingError(ManifestError):
    """Raised when the manifest cannot be parsed."""


class DuplicateModuleError(ManifestError):
    """Raised when the manifest contains duplicate modules."""


class RegistryError(BoilrError):
    """Raised when the module registry is invalid."""


class ModuleNotFoundError(RegistryError):
    """Raised when a requested module does not exist."""


class InvalidModuleDefinitionError(RegistryError):
    """Raised when a module.yml definition is invalid."""


class ResolverError(BoilrError):
    """Raised when project resolution fails."""


class ModuleRequirementError(ResolverError):
    """Raised when a module requirement is not satisfied."""


class ModuleCompatibilityError(ResolverError):
    """Raised when selected modules are incompatible."""


class ModuleVariableError(ResolverError):
    """Raised when module variables are missing or invalid."""


class GenerationError(BoilrError):
    """Raised when project generation fails."""


class TemplateRenderError(GenerationError):
    """Raised when a template cannot be rendered."""


class OutputDirectoryError(GenerationError):
    """Raised when the output directory cannot be prepared."""