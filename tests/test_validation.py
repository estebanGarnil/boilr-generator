from boilr_generator.diagnostics import Diagnostic, ValidationResult
from boilr_generator.manifest.loader import load_project_manifest_from_dict
from boilr_generator.validation.project import validate_project


def test_validation_result_is_valid_by_default():
    result = ValidationResult()

    assert result.is_valid is True
    assert result.errors == []


def test_validation_result_becomes_invalid_after_error():
    result = ValidationResult()

    result.add_error(
        code="missing_variable",
        message="db_password is required",
        module_key="postgres",
        field_path="modules.postgres.variables.db_password",
    )

    assert result.is_valid is False
    assert len(result.errors) == 1

    error = result.errors[0]

    assert isinstance(error, Diagnostic)
    assert error.code == "missing_variable"
    assert error.module_key == "postgres"
    assert error.field_path == "modules.postgres.variables.db_password"


def test_validate_project_detects_invalid_variable_type(
    registry,
    valid_manifest_data,
):
    for module in valid_manifest_data["modules"]:
        if module["key"] == "django":
            module["variables"]["debug"] = "true"

    manifest = load_project_manifest_from_dict(valid_manifest_data)

    result = validate_project(manifest, registry)

    assert result.is_valid is False
    assert len(result.errors) == 1

    error = result.errors[0]

    assert error.code == "invalid_variable_type"
    assert error.module_key == "django"
    assert error.field_path == "modules.django.variables.debug"
    assert error.context["expected_type"] == "boolean"
    assert error.context["actual_type"] == "str"


def test_validate_project_rejects_boolean_for_integer_variable(
    registry,
    valid_manifest_data,
):
    for module in valid_manifest_data["modules"]:
        if module["key"] == "postgres":
            module["variables"]["db_port"] = True

    manifest = load_project_manifest_from_dict(valid_manifest_data)

    result = validate_project(manifest, registry)

    assert result.is_valid is False
    assert len(result.errors) == 1

    error = result.errors[0]

    assert error.code == "invalid_variable_type"
    assert error.module_key == "postgres"
    assert error.field_path == "modules.postgres.variables.db_port"
    assert error.context["expected_type"] == "int"
    assert error.context["actual_type"] == "bool"


def test_validate_project_detects_unknown_variable(
    registry,
    valid_manifest_data,
):
    for module in valid_manifest_data["modules"]:
        if module["key"] == "django":
            module["variables"]["secrte_key"] = "typo"

    manifest = load_project_manifest_from_dict(valid_manifest_data)

    result = validate_project(manifest, registry)

    assert result.is_valid is False
    assert len(result.errors) == 1

    error = result.errors[0]

    assert error.code == "unknown_variable"
    assert error.module_key == "django"
    assert error.field_path == "modules.django.variables.secrte_key"
    assert error.context["field"] == "secrte_key"


def test_validate_project_detects_unknown_option(
    registry,
    valid_manifest_data,
):
    for module in valid_manifest_data["modules"]:
        if module["key"] == "django":
            module["options"]["rest_framwork"] = True

    manifest = load_project_manifest_from_dict(valid_manifest_data)

    result = validate_project(manifest, registry)

    assert result.is_valid is False

    error = result.errors[0]

    assert error.code == "unknown_option"
    assert error.module_key == "django"
    assert error.field_path == "modules.django.options.rest_framwork"


def test_validate_project_detects_invalid_option_type(
    registry,
    valid_manifest_data,
):
    for module in valid_manifest_data["modules"]:
        if module["key"] == "django":
            module["options"]["cors"] = "yes"

    manifest = load_project_manifest_from_dict(valid_manifest_data)

    result = validate_project(manifest, registry)

    assert result.is_valid is False

    error = result.errors[0]

    assert error.code == "invalid_option_type"
    assert error.module_key == "django"
    assert error.field_path == "modules.django.options.cors"


def test_validate_project_detects_missing_requirement(
    registry,
    valid_manifest_data,
):
    valid_manifest_data["modules"] = [
        module
        for module in valid_manifest_data["modules"]
        if module["key"] != "postgres"
    ]

    manifest = load_project_manifest_from_dict(valid_manifest_data)

    result = validate_project(manifest, registry)

    assert result.is_valid is False

    error = result.errors[0]

    assert error.code == "missing_requirement"
    assert error.module_key == "django"
    assert error.field_path == "modules.django.requirements.database"
    assert error.context["required_type"] == "database"
