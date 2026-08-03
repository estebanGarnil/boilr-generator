import pytest
from boilr_generator.core.validation import ValidationIssue
from boilr_generator.diagnostics import (
    Diagnostic,
    DiagnosticSeverity,
    ValidationResult,
)


def test_validation_result_is_valid_by_default():
    result = ValidationResult()

    assert result.is_valid is True
    assert result.valid is True
    assert result.diagnostics == []
    assert result.errors == []
    assert result.warnings == []
    assert result.infos == []


def test_error_makes_result_invalid():
    result = ValidationResult()

    diagnostic = result.add_error(
        code="missing_variable",
        message="db_password is required.",
        module_key="postgres",
        field_path="variables.db_password",
    )

    assert result.is_valid is False
    assert result.errors == [diagnostic]
    assert result.warnings == []
    assert result.infos == []


def test_warning_does_not_make_result_invalid():
    result = ValidationResult()

    diagnostic = result.add_warning(
        code="unused_module",
        message="The module is selected but unused.",
        module_key="redis",
    )

    assert result.is_valid is True
    assert result.errors == []
    assert result.warnings == [diagnostic]


def test_info_does_not_make_result_invalid():
    result = ValidationResult()

    diagnostic = result.add_info(
        code="automatic_binding",
        message="A provider was selected automatically.",
        module_key="django",
    )

    assert result.is_valid is True
    assert result.infos == [diagnostic]


def test_diagnostics_are_filtered_by_severity():
    result = ValidationResult()

    error = result.add_error(
        code="error_code",
        message="Error.",
    )

    warning = result.add_warning(
        code="warning_code",
        message="Warning.",
    )

    info = result.add_info(
        code="info_code",
        message="Information.",
    )

    assert result.errors == [error]
    assert result.warnings == [warning]
    assert result.infos == [info]


def test_diagnostic_can_be_serialized():
    diagnostic = Diagnostic(
        code="missing_requirement",
        severity=DiagnosticSeverity.ERROR,
        message="A database module is required.",
        module_key="django",
        field_path="requirements.database",
        context={"required_type": "database"},
        suggestion="Select a database module.",
    )

    data = diagnostic.to_dict()

    assert data == {
        "code": "missing_requirement",
        "severity": "error",
        "message": "A database module is required.",
        "module_key": "django",
        "field_path": "requirements.database",
        "context": {"required_type": "database"},
        "suggestion": "Select a database module.",
    }


def test_validation_result_can_be_serialized():
    result = ValidationResult()

    result.add_error(
        code="missing_requirement",
        message="A database module is required.",
    )

    result.add_warning(
        code="unused_module",
        message="A module is unused.",
    )

    data = result.to_dict()

    assert data["is_valid"] is False
    assert len(data["diagnostics"]) == 2
    assert len(data["errors"]) == 1
    assert len(data["warnings"]) == 1
    assert data["errors"][0]["severity"] == "error"
    assert data["warnings"][0]["severity"] == "warning"


def test_context_is_not_shared_between_diagnostics():
    first = Diagnostic(
        code="first",
        severity=DiagnosticSeverity.ERROR,
        message="First.",
    )

    second = Diagnostic(
        code="second",
        severity=DiagnosticSeverity.ERROR,
        message="Second.",
    )

    first.context["value"] = 1

    assert second.context == {}


def test_legacy_validation_issue_is_diagnostic():
    assert ValidationIssue is Diagnostic


def test_legacy_module_and_field_arguments_are_supported():
    result = ValidationResult()

    diagnostic = result.add_error(
        code="legacy_error",
        message="Legacy error.",
        module="django",
        field="debug",
    )

    assert diagnostic.module_key == "django"
    assert diagnostic.field_path == "debug"
    assert diagnostic.module == "django"
    assert diagnostic.field == "debug"


def test_conflicting_legacy_and_canonical_values_are_rejected():
    result = ValidationResult()

    with pytest.raises(ValueError):
        result.add_error(
            code="conflict",
            message="Conflict.",
            module_key="django",
            module="postgres",
        )