"""Validation models for the Boilr generator engine."""

from dataclasses import dataclass, field


@dataclass(slots=True)
class ValidationIssue:
    """Represents a validation issue."""

    code: str
    message: str
    module: str | None = None
    field: str | None = None


@dataclass(slots=True)
class ValidationResult:
    """Represents a validation result."""

    errors: list[ValidationIssue] = field(default_factory=list)

    @property
    def valid(self) -> bool:
        return len(self.errors) == 0

    def add_error(
        self,
        *,
        code: str,
        message: str,
        module: str | None = None,
        field: str | None = None,
    ) -> None:
        self.errors.append(
            ValidationIssue(
                code=code,
                message=message,
                module=module,
                field=field,
            )
        )