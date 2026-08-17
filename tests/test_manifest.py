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

def test_manifest_loads_explicit_provider_selection(
    valid_manifest_data,
):
    valid_manifest_data["modules"][1]["bindings"] = {
        "primary_database": {
            "provider": "postgres",
        }
    }

    manifest = load_project_manifest_from_dict(
        valid_manifest_data
    )

    django = manifest.get_module("django")

    assert django is not None
    assert (
        django.bindings["primary_database"].provider
        == "postgres"
    )


@pytest.mark.parametrize(
    ("bindings", "expected_path"),
    [
        (
            [],
            "modules.1.bindings",
        ),
        (
            {
                "primary_database": "postgres",
            },
            "modules.1.bindings.primary_database",
        ),
        (
            {
                "primary_database": {
                    "provider": "   ",
                },
            },
            (
                "modules.1.bindings."
                "primary_database.provider"
            ),
        ),
        (
            {
                "primary_database": {
                    "provider": "postgres",
                    "unexpected": True,
                },
            },
            (
                "modules.1.bindings."
                "primary_database.unexpected"
            ),
        ),
    ],
)
def test_manifest_rejects_invalid_provider_selection(
    valid_manifest_data,
    bindings,
    expected_path,
):
    valid_manifest_data["modules"][1][
        "bindings"
    ] = bindings

    with pytest.raises(ManifestSchemaError) as error_info:
        load_project_manifest_from_dict(
            valid_manifest_data
        )

    assert error_info.value.field_path == expected_path


def test_manifest_rejects_blank_binding_key(
    valid_manifest_data,
):
    valid_manifest_data["modules"][1]["bindings"] = {
        "   ": {
            "provider": "postgres",
        }
    }

    with pytest.raises(ManifestSchemaError) as error_info:
        load_project_manifest_from_dict(
            valid_manifest_data
        )

    error = error_info.value

    assert error.field_path is not None
    assert error.field_path.startswith(
        "modules.1.bindings"
    )
    assert error.context["errors"][0]["type"] == (
        "string_too_short"
    )

def test_manifest_loads_provider_version_constraint(
    valid_manifest_data,
):
    valid_manifest_data["modules"][1]["bindings"] = {
        "primary_database": {
            "provider": "postgres",
            "version": ">=16,<18",
        }
    }

    manifest = load_project_manifest_from_dict(
        valid_manifest_data
    )

    django = manifest.get_module("django")

    assert django is not None
    assert (
        django.bindings["primary_database"].version
        == ">=16,<18"
    )


@pytest.mark.parametrize(
    ("version", "expected_error_type"),
    [
        ("16", "value_error"),
        ("latest", "value_error"),
        ("   ", "string_too_short"),
    ],
)
def test_manifest_rejects_invalid_provider_version_constraint(
    valid_manifest_data,
    version,
    expected_error_type,
):
    valid_manifest_data["modules"][1]["bindings"] = {
        "primary_database": {
            "provider": "postgres",
            "version": version,
        }
    }

    with pytest.raises(ManifestSchemaError) as error_info:
        load_project_manifest_from_dict(
            valid_manifest_data
        )

    error = error_info.value

    assert error.field_path == (
        "modules.1.bindings."
        "primary_database.version"
    )
    assert error.context["errors"][0]["type"] == (
        expected_error_type
    )

def test_manifest_loads_provider_tags(
    valid_manifest_data,
):
    valid_manifest_data["modules"][1]["bindings"] = {
        "primary_database": {
            "provider": "postgres",
            "tags": [
                "sql",
                " relational ",
            ],
        }
    }

    manifest = load_project_manifest_from_dict(
        valid_manifest_data
    )

    django = manifest.get_module("django")

    assert django is not None
    assert django.bindings["primary_database"].tags == [
        "sql",
        "relational",
    ]


@pytest.mark.parametrize(
    ("tags", "expected_error_type"),
    [
        (["sql", "   "], "string_too_short"),
        (["sql", 17], "string_type"),
        (["sql", "sql"], "value_error"),
    ],
)
def test_manifest_rejects_invalid_provider_tags(
    valid_manifest_data,
    tags,
    expected_error_type,
):
    valid_manifest_data["modules"][1]["bindings"] = {
        "primary_database": {
            "provider": "postgres",
            "tags": tags,
        }
    }

    with pytest.raises(ManifestSchemaError) as error_info:
        load_project_manifest_from_dict(
            valid_manifest_data
        )

    error = error_info.value

    assert error.field_path.startswith(
        "modules.1.bindings."
        "primary_database.tags"
    )
    assert error.context["errors"][0]["type"] == (
        expected_error_type
    )