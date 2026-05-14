class ManifestError(Exception):
    """Base exception for manifest-related errors."""


class ManifestLoadError(ManifestError):
    """Raised when a manifest cannot be loaded."""


class ManifestValidationError(ManifestError):
    """Raised when a manifest is invalid."""