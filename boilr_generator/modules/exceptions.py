class ModuleError(Exception):
    """Base exception for module-related errors."""


class ModuleLoadError(ModuleError):
    """Raised when a module cannot be loaded."""


class ModuleValidationError(ModuleError):
    """Raised when a module manifest is invalid."""