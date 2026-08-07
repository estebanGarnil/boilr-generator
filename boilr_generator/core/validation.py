"""Compatibility exports for structured Boilr dignostics."""

from boilr_generator.diagnostics import (
    Diagnostic,
    DiagnosticSeverity,
    ValidationResult,
)

# Legacy alias.
ValidationIssue = Diagnostic

__all__ = [
    "Diagnostic",
    "DiagnosticSeverity",
    "ValidationIssue",
    "ValidationResult",
]