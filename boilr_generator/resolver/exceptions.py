class ResolverError(Exception):
    """Base exception for resolver-related errors."""

class ModuleResolutionError(ResolverError):
    """Raised when a requested module cannot be resolved."""
