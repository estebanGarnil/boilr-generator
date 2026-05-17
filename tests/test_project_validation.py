from boilr_generator.manifest import load_project_manifest_from_dict
from boilr_generator.validation import validate_project


def test_validate_project_returns_valid_result_for_valid_manifest(
    registry,
    valid_manifest_data,
):
    manifest = load_project_manifest_from_dict(valid_manifest_data)

    result = validate_project(manifest, registry)

    assert result.valid is True
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

    assert result.valid is False
    assert len(result.errors) == 1
    assert result.errors[0].code == "module_not_found"

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

    assert result.valid is False
    assert len(result.errors) == 2
    assert result.errors[0].code == "module_not_found"
    assert result.errors[0].module == "unknown_backend"
    assert result.errors[1].code == "module_not_found"
    assert result.errors[1].module == "unknown_database"