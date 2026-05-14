import pytest
from boilr_generator.manifest.exceptions import ManifestValidationError
from boilr_generator.manifest import load_project_manifest_from_dict


def test_load_valid_manifest(valid_manifest_data):
    manifest = load_project_manifest_from_dict(valid_manifest_data)

    assert manifest.project.name == "my_app"
    assert manifest.project.type == "fullstack_web"
    assert manifest.list_module_keys() == ["postgres", "django"]


def test_manifest_has_module(manifest):
    assert manifest.has_module("django") is True
    assert manifest.has_module("postgres") is True
    assert manifest.has_module("vue") is False


def test_manifest_get_module(manifest):
    django_module = manifest.get_module("django")

    assert django_module is not None
    assert django_module.key == "django"
    assert django_module.options["cors"] is True


def test_manifest_rejects_duplicate_modules(valid_manifest_data):
    valid_manifest_data["modules"].append(
        {
            "key": "django",
            "variables": {},
            "options": {},
        }
    )

    with pytest.raises(ManifestValidationError):
        load_project_manifest_from_dict(valid_manifest_data)