"""Structured diagnostics produced by Boilr validation."""

from collections.abc import Mapping
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any


class DiagnosticSeverity(StrEnum):
    """Severity level of a diagnostic."""

    ERROR = "error"
    WARNING = "warning"
    INFO = "info"


@dataclass(frozen=True, slots=True)
class Diagnostic:
    """Represents one structured validation diagnostic."""

    code: str
    severity: DiagnosticSeverity
    message: str
    module_key: str | None = None
    field_path: str | None = None
    context: dict[str, Any] = field(default_factory=dict)
    suggestion: str | None = None

    @property
    def module(self) -> str | None:
        """Temporary compatibility alias for the old API."""

        return self.module_key

    @property
    def field(self) -> str | None:
        """Temporary compatibility alias for the old API."""

        return self.field_path

    def to_dict(self) -> dict[str, Any]:
        """Serialize the diagnostic into JSON-compatible values."""

        return {
            "code": self.code,
            "severity": self.severity.value,
            "message": self.message,
            "module_key": self.module_key,
            "field_path": self.field_path,
            "context": dict(self.context),
            "suggestion": self.suggestion,
        }


@dataclass(slots=True)
class ValidationResult:
    """Collects all diagnostics produced during validation."""

    diagnostics: list[Diagnostic] = field(default_factory=list)

    @property
    def errors(self) -> list[Diagnostic]:
        return [
            diagnostic
            for diagnostic in self.diagnostics
            if diagnostic.severity is DiagnosticSeverity.ERROR
        ]

    @property
    def warnings(self) -> list[Diagnostic]:
        return [
            diagnostic
            for diagnostic in self.diagnostics
            if diagnostic.severity is DiagnosticSeverity.WARNING
        ]

    @property
    def infos(self) -> list[Diagnostic]:
        return [
            diagnostic
            for diagnostic in self.diagnostics
            if diagnostic.severity is DiagnosticSeverity.INFO
        ]

    @property
    def is_valid(self) -> bool:
        return not self.errors

    @property
    def valid(self) -> bool:
        """Temporary compatibility alias for the old API."""

        return self.is_valid

    def add(
        self,
        *,
        code: str,
        severity: DiagnosticSeverity,
        message: str,
        module_key: str | None = None,
        field_path: str | None = None,
        context: Mapping[str, Any] | None = None,
        suggestion: str | None = None,
        module: str | None = None,
        field: str | None = None,
    ) -> Diagnostic:
        """Add a diagnostic to the result.

        The ``module`` and ``field`` parameters are temporary aliases for
        compatibility with the previous validation API.
        """

        resolved_module_key = self._resolve_alias(
            canonical_name="module_key",
            canonical_value=module_key,
            legacy_name="module",
            legacy_value=module,
        )

        resolved_field_path = self._resolve_alias(
            canonical_name="field_path",
            canonical_value=field_path,
            legacy_name="field",
            legacy_value=field,
        )

        diagnostic = Diagnostic(
            code=code,
            severity=severity,
            message=message,
            module_key=resolved_module_key,
            field_path=resolved_field_path,
            context=dict(context or {}),
            suggestion=suggestion,
        )

        self.diagnostics.append(diagnostic)

        return diagnostic

    def add_error(
        self,
        *,
        code: str,
        message: str,
        module_key: str | None = None,
        field_path: str | None = None,
        context: Mapping[str, Any] | None = None,
        suggestion: str | None = None,
        module: str | None = None,
        field: str | None = None,
    ) -> Diagnostic:
        return self.add(
            code=code,
            severity=DiagnosticSeverity.ERROR,
            message=message,
            module_key=module_key,
            field_path=field_path,
            context=context,
            suggestion=suggestion,
            module=module,
            field=field,
        )

    def add_warning(
        self,
        *,
        code: str,
        message: str,
        module_key: str | None = None,
        field_path: str | None = None,
        context: Mapping[str, Any] | None = None,
        suggestion: str | None = None,
    ) -> Diagnostic:
        return self.add(
            code=code,
            severity=DiagnosticSeverity.WARNING,
            message=message,
            module_key=module_key,
            field_path=field_path,
            context=context,
            suggestion=suggestion,
        )

    def add_info(
        self,
        *,
        code: str,
        message: str,
        module_key: str | None = None,
        field_path: str | None = None,
        context: Mapping[str, Any] | None = None,
        suggestion: str | None = None,
    ) -> Diagnostic:
        return self.add(
            code=code,
            severity=DiagnosticSeverity.INFO,
            message=message,
            module_key=module_key,
            field_path=field_path,
            context=context,
            suggestion=suggestion,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "is_valid": self.is_valid,
            "diagnostics": [
                diagnostic.to_dict()
                for diagnostic in self.diagnostics
            ],
            "errors": [
                diagnostic.to_dict()
                for diagnostic in self.errors
            ],
            "warnings": [
                diagnostic.to_dict()
                for diagnostic in self.warnings
            ],
            "infos": [
                diagnostic.to_dict()
                for diagnostic in self.infos
            ],
        }

    @staticmethod
    def _resolve_alias(
        *,
        canonical_name: str,
        canonical_value: str | None,
        legacy_name: str,
        legacy_value: str | None,
    ) -> str | None:
        if (
            canonical_value is not None
            and legacy_value is not None
            and canonical_value != legacy_value
        ):
            raise ValueError(
                f'Conflicting values for "{canonical_name}" '
                f'and legacy alias "{legacy_name}".'
            )

        if canonical_value is not None:
            return canonical_value

        return legacy_value