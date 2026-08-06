import pytest
from boilr_generator.modules.schemas import (
    ModuleManifest,
)
from pydantic import ValidationError


def get_manifest_data(
    resolved_project,
    module_key,
):
    module = resolved_project.get_module(module_key)

    assert module is not None

    return module.manifest.model_dump(by_alias=True)


def test_manifest_loads_extension_points_and_contributions(
    resolved_project,
):
    data = get_manifest_data(
        resolved_project,
        "django",
    )

    data["extension_points"] = {
        "python.dependencies": {
            "type": "list",
            "merge": "append_unique",
            "default": [],
        }
    }

    data["contributions"] = [
        {
            "target": "primary_database",
            "extension_point": "database.options",
            "value": {
                "pool_size": 10,
            },
        }
    ]

    manifest = ModuleManifest.model_validate(data)

    extension_point = manifest.extension_points[
        "python.dependencies"
    ]

    assert extension_point.type == "list"
    assert extension_point.merge == "append_unique"
    assert extension_point.default == []

    contribution = manifest.contributions[0]

    assert contribution.target_binding == (
        "primary_database"
    )
    assert contribution.extension_point == (
        "database.options"
    )
    assert contribution.value == {
        "pool_size": 10,
    }

    serialized = manifest.model_dump(by_alias=True)

    assert serialized["contributions"][0]["target"] == (
        "primary_database"
    )


def test_manifest_rejects_unknown_extension_point_type(
    resolved_project,
):
    data = get_manifest_data(
        resolved_project,
        "django",
    )

    data["extension_points"] = {
        "invalid": {
            "type": "unknown",
        }
    }

    with pytest.raises(
        ValidationError,
        match="Invalid extension point type",
    ):
        ModuleManifest.model_validate(data)


def test_manifest_rejects_incompatible_merge_strategy(
    resolved_project,
):
    data = get_manifest_data(
        resolved_project,
        "django",
    )

    data["extension_points"] = {
        "python.dependencies": {
            "type": "list",
            "merge": "deep_merge",
        }
    }

    with pytest.raises(
        ValidationError,
        match="Merge strategy 'deep_merge' is not valid",
    ):
        ModuleManifest.model_validate(data)


def test_manifest_rejects_invalid_extension_point_default(
    resolved_project,
):
    data = get_manifest_data(
        resolved_project,
        "django",
    )

    data["extension_points"] = {
        "python.dependencies": {
            "type": "list",
            "merge": "append_unique",
            "default": {},
        }
    }

    with pytest.raises(
        ValidationError,
        match="Invalid extension point default type",
    ):
        ModuleManifest.model_validate(data)


def test_manifest_rejects_undeclared_contribution_target(
    resolved_project,
):
    data = get_manifest_data(
        resolved_project,
        "django",
    )

    data["contributions"] = [
        {
            "target": "missing_binding",
            "extension_point": "python.dependencies",
            "value": [],
        }
    ]

    with pytest.raises(
        ValidationError,
        match=(
            "Contribution targets must reference declared "
            "capability bindings"
        ),
    ):
        ModuleManifest.model_validate(data)