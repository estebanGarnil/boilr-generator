import pytest
import yaml
from boilr_generator.exceptions import (
    ManifestNotFoundError,
    ManifestParseError,
    ManifestSchemaError,
    ModuleLoadError,
    ModuleSchemaError,
)
from boilr_generator.manifest import (
    load_project_manifest_from_dict,
    load_project_manifest_from_yaml,
)
from boilr_generator.modules import (
    load_module_from_dict,
    load_module_from_yaml,
)
from pydantic import ValidationError


def test_missing_manifest_raises_contextual_error(tmp_path):
    path = tmp_path / "missing.yml"

    with pytest.raises(ManifestNotFoundError) as captured:
        load_project_manifest_from_yaml(path)

    error = captured.value

    assert error.code == "manifest_not_found"
    assert str(path) in str(error)
    assert error.context["path"] == str(path)
    assert error.suggestion is not None


def test_invalid_manifest_yaml_raises_parse_error(tmp_path):
    path = tmp_path / "project.yml"
    path.write_text("project: [", encoding="utf-8")

    with pytest.raises(ManifestParseError) as captured:
        load_project_manifest_from_yaml(path)

    assert isinstance(captured.value.__cause__, yaml.YAMLError)
    assert captured.value.context["path"] == str(path)


def test_empty_manifest_raises_parse_error(tmp_path):
    path = tmp_path / "project.yml"
    path.write_text("", encoding="utf-8")

    with pytest.raises(ManifestParseError):
        load_project_manifest_from_yaml(path)


def test_manifest_root_must_be_an_object(tmp_path):
    path = tmp_path / "project.yml"
    path.write_text("- django\n- postgres\n", encoding="utf-8")

    with pytest.raises(ManifestParseError) as captured:
        load_project_manifest_from_yaml(path)

    assert captured.value.field_path == "<root>"
    assert captured.value.context["actual_type"] == "list"


def test_invalid_manifest_schema_is_wrapped():
    with pytest.raises(ManifestSchemaError) as captured:
        load_project_manifest_from_dict({})

    error = captured.value

    assert isinstance(error.__cause__, ValidationError)
    assert error.code == "manifest_schema_error"
    assert error.context["errors"]


def test_duplicate_project_modules_are_schema_error():
    data = {
        "project": {
            "name": "example",
            "type": "web",
        },
        "modules": [
            {"key": "django"},
            {"key": "django"},
        ],
    }

    with pytest.raises(ManifestSchemaError) as captured:
        load_project_manifest_from_dict(data)

    assert isinstance(captured.value.__cause__, ValidationError)


def test_missing_module_file_raises_load_error(tmp_path):
    path = tmp_path / "module.yml"

    with pytest.raises(ModuleLoadError) as captured:
        load_module_from_yaml(path)

    assert captured.value.context["path"] == str(path)
    assert captured.value.suggestion is not None


def test_invalid_module_yaml_raises_load_error(tmp_path):
    path = tmp_path / "module.yml"
    path.write_text("meta: [", encoding="utf-8")

    with pytest.raises(ModuleLoadError) as captured:
        load_module_from_yaml(path)

    assert isinstance(captured.value.__cause__, yaml.YAMLError)


def test_empty_module_file_raises_load_error(tmp_path):
    path = tmp_path / "module.yml"
    path.write_text("", encoding="utf-8")

    with pytest.raises(ModuleLoadError):
        load_module_from_yaml(path)


def test_module_root_must_be_an_object(tmp_path):
    path = tmp_path / "module.yml"
    path.write_text("- django\n- postgres\n", encoding="utf-8")

    with pytest.raises(ModuleLoadError) as captured:
        load_module_from_yaml(path)

    assert captured.value.field_path == "<root>"
    assert captured.value.context["actual_type"] == "list"


def test_invalid_module_schema_is_wrapped():
    with pytest.raises(ModuleSchemaError) as captured:
        load_module_from_dict({})

    error = captured.value

    assert isinstance(error.__cause__, ValidationError)
    assert error.code == "module_schema_error"
    assert error.context["errors"]