import pytest
from boilr_generator.exceptions import ManifestSchemaError
from boilr_generator.manifest import load_project_manifest_from_dict


def test_load_valid_manifest(valid_manifest_data):
    manifest = load_project_manifest_from_dict(valid_manifest_data)

    assert manifest.project.name == "my_app"
    assert manifest.project.type == "fullstack_web"
    assert manifest.list_module_keys() == [
        "postgres",
        "django",
        "django-postgres",
    ]

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

    with pytest.raises(ManifestSchemaError):
        load_project_manifest_from_dict(valid_manifest_data)

@pytest.mark.parametrize(
    ("scope", "expected_path"),
    [
        ("root", "unexpected"),
        ("project", "project.unexpected"),
        ("module", "modules.0.unexpected"),
    ],
)
def test_manifest_rejects_unknown_fields(
    valid_manifest_data,
    scope,
    expected_path,
):
    if scope == "root":
        valid_manifest_data["unexpected"] = True
    elif scope == "project":
        valid_manifest_data["project"]["unexpected"] = True
    else:
        valid_manifest_data["modules"][0]["unexpected"] = True

    with pytest.raises(ManifestSchemaError) as error_info:
        load_project_manifest_from_dict(
            valid_manifest_data
        )

    error = error_info.value

    assert error.field_path == expected_path
    assert error.context["errors"][0]["type"] == (
        "extra_forbidden"
    )


@pytest.mark.parametrize(
    "field",
    [
        "name",
        "type",
        "version",
    ],
)
def test_manifest_rejects_blank_project_fields(
    valid_manifest_data,
    field,
):
    valid_manifest_data["project"][field] = "   "

    with pytest.raises(ManifestSchemaError) as error_info:
        load_project_manifest_from_dict(
            valid_manifest_data
        )

    assert error_info.value.field_path == f"project.{field}"


def test_manifest_rejects_blank_module_key(
    valid_manifest_data,
):
    valid_manifest_data["modules"][0]["key"] = "   "

    with pytest.raises(ManifestSchemaError) as error_info:
        load_project_manifest_from_dict(
            valid_manifest_data
        )

    assert error_info.value.field_path == "modules.0.key"


def test_manifest_rejects_empty_module_list(
    valid_manifest_data,
):
    valid_manifest_data["modules"] = []

    with pytest.raises(ManifestSchemaError) as error_info:
        load_project_manifest_from_dict(
            valid_manifest_data
        )

    assert error_info.value.field_path == "modules"


def test_manifest_rejects_non_string_version(
    valid_manifest_data,
):
    valid_manifest_data["project"]["version"] = 1.0

    with pytest.raises(ManifestSchemaError) as error_info:
        load_project_manifest_from_dict(
            valid_manifest_data
        )

    assert error_info.value.field_path == "project.version"


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("variables", []),
        ("options", []),
    ],
)
def test_manifest_rejects_invalid_module_configuration_shape(
    valid_manifest_data,
    field,
    value,
):
    valid_manifest_data["modules"][0][field] = value

    with pytest.raises(ManifestSchemaError) as error_info:
        load_project_manifest_from_dict(
            valid_manifest_data
        )

    assert (
        error_info.value.field_path
        == f"modules.0.{field}"
    )


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("project", []),
        ("modules", {}),
    ],
)
def test_manifest_rejects_invalid_root_sections(
    valid_manifest_data,
    field,
    value,
):
    valid_manifest_data[field] = value

    with pytest.raises(ManifestSchemaError) as error_info:
        load_project_manifest_from_dict(
            valid_manifest_data
        )

    assert error_info.value.field_path == field