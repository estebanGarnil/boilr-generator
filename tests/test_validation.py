from boilr_generator.core.validation import (
    ValidationIssue,
    ValidationResult,
)

from boilr_generator.manifest.loader import load_project_manifest_from_dict
from boilr_generator.validation.project import validate_project

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

def test_validate_project_detects_invalid_variable_type(
    registry,
    valid_manifest_data,
):
    for module in valid_manifest_data["modules"]:
        if module["key"] == "django":
            module["variables"]["debug"] = "true"

    manifest = load_project_manifest_from_dict(valid_manifest_data)

    result = validate_project(manifest, registry)

    assert result.valid is False
    assert len(result.errors) == 1
    assert result.errors[0].code == "invalid_variable_type"
    assert result.errors[0].module == "django"
    assert result.errors[0].field == "debug"

