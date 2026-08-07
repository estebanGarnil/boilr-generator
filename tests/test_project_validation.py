from boilr_generator.manifest import load_project_manifest_from_dict
from boilr_generator.validation import validate_project


def test_validate_project_returns_valid_result_for_valid_manifest(
    registry,
    valid_manifest_data,
):
    manifest = load_project_manifest_from_dict(valid_manifest_data)

    result = validate_project(manifest, registry)

    assert result.is_valid is True
    assert result.errors == []


def test_validate_project_returns_error_for_unknown_module(
    registry,
    valid_manifest_data,
):
    valid_manifest_data["modules"].append(
        {
            "key": "unknown",
            "variables": {},
            "options": {},
        }
    )
    manifest = load_project_manifest_from_dict(valid_manifest_data)

    result = validate_project(manifest, registry)

    assert result.is_valid is False
    assert len(result.errors) == 1

    error = result.errors[0]

    assert error.code == "module_not_found"
    assert error.module_key == "unknown"
    assert error.field_path == "modules.unknown"
    assert error.context["requested_module"] == "unknown"


def test_validate_project_collects_multiple_unknown_modules(
    registry,
    valid_manifest_data,
):
    valid_manifest_data["modules"].extend(
        [
            {
                "key": "unknown_backend",
                "variables": {},
                "options": {},
            },
            {
                "key": "unknown_database",
                "variables": {},
                "options": {},
            },
        ]
    )

    manifest = load_project_manifest_from_dict(valid_manifest_data)

    result = validate_project(manifest, registry)

    assert result.is_valid is False
    assert len(result.errors) == 2

    first_error = result.errors[0]
    second_error = result.errors[1]

    assert first_error.code == "module_not_found"
    assert first_error.module_key == "unknown_backend"
    assert first_error.field_path == "modules.unknown_backend"

    assert second_error.code == "module_not_found"
    assert second_error.module_key == "unknown_database"
    assert second_error.field_path == "modules.unknown_database"


def test_validate_project_collects_missing_required_variables(
    registry,
    valid_manifest_data,
):
    for module in valid_manifest_data["modules"]:
        if module["key"] == "postgres":
            module["variables"] = {}

    manifest = load_project_manifest_from_dict(valid_manifest_data)

    result = validate_project(manifest, registry)

    assert result.is_valid is False
    assert len(result.errors) >= 1

    error = result.errors[0]

    assert error.code == "missing_required_variable"
    assert error.module_key == "postgres"
    assert error.field_path.startswith("modules.postgres.variables.")
    assert error.suggestion is not None
