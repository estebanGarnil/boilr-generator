from boilr_generator.core.validation import (
    ValidationIssue,
    ValidationResult,
)


def test_validation_result_is_valid_by_default():
    result = ValidationResult()

    assert result.valid is True
    assert result.errors == []


def test_validation_result_becomes_invalid_after_error():
    result = ValidationResult()

    result.add_error(
        code="missing_variable",
        message="db_password is required",
        module="postgres",
        field="db_password",
    )

    assert result.valid is False
    assert len(result.errors) == 1

    error = result.errors[0]

    assert isinstance(error, ValidationIssue)
    assert error.code == "missing_variable"
    assert error.module == "postgres"
    assert error.field == "db_password"