"""Manifest exception compatibility exports."""

from boilr_generator.exceptions import (
    ManifestError,
    ManifestLoadError,
    ManifestNotFoundError,
    ManifestParseError,
    ManifestSchemaError,
)

# Legacy alias.
ManifestValidationError = ManifestSchemaError

__all__ = [
    "ManifestError",
    "ManifestLoadError",
    "ManifestNotFoundError",
    "ManifestParseError",
    "ManifestSchemaError",
    "ManifestValidationError",
]