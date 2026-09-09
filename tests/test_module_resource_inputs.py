from copy import deepcopy
from re import escape

import pytest
from pydantic import ValidationError

from boilr_generator.modules.registry import ModuleRegistry
from boilr_generator.modules.schemas import (
    ModuleManifest,
    ResourceInputs,
)
from boilr_generator.paths import get_builtin_modules_path


def _manifest_payload():
    return {
        "meta": {
            "name": "Example",
            "key": "example",
            "type": "backend",
            "version": "1.0.0",
        },
        "role": {
            "group": "backend",
        },
        "requires": [
            {
                "capability": "database.connection",
                "binding": "primary_database",
            }
        ],
        "extension_points": {
            "python.dependencies": {
                "type": "list",
                "merge": "append_unique",
                "default": [],
            }
        },
        "assembly": {
            "destination_root": ".",
        },
        "sources": {
            "render": [
                {
                    "id": "generated",
                    "from": "generated.txt.j2",
                    "to": "generated.txt",
                }
            ]
        },
    }


def _payload_with_uses(location, uses):
    payload = deepcopy(_manifest_payload())

    if location == "sources.render[generated]":
        payload["sources"]["render"][0]["uses"] = uses
    elif location == "docker":
        payload["docker"] = {
            "uses": uses,
        }
    elif location == "exports":
        payload["exports"] = {
            "uses": uses,
        }
    else:
        raise AssertionError(f"Unknown test location: {location}")

    return payload


def test_resource_inputs_default_to_empty_lists():
    inputs = ResourceInputs()

    assert inputs.bindings == []
    assert inputs.extension_points == []


def test_resource_inputs_are_sorted_deterministically():
    inputs = ResourceInputs.model_validate(
        {
            "bindings": [
                "secondary_database",
                "primary_database",
            ],
            "extension_points": [
                "python.dependencies",
                "django.settings",
            ],
        }
    )

    assert inputs.bindings == [
        "primary_database",
        "secondary_database",
    ]
    assert inputs.extension_points == [
        "django.settings",
        "python.dependencies",
    ]


@pytest.mark.parametrize(
    "field_name",
    [
        "bindings",
        "extension_points",
    ],
)
def test_resource_inputs_reject_duplicate_keys(field_name):
    with pytest.raises(
        ValidationError,
        match=(
            "Duplicate generated resource inputs "
            "are not allowed"
        ),
    ):
        ResourceInputs.model_validate(
            {
                field_name: [
                    "duplicate",
                    "duplicate",
                ]
            }
        )


@pytest.mark.parametrize(
    "location",
    [
        "sources.render[generated]",
        "docker",
        "exports",
    ],
)
def test_module_manifest_rejects_unknown_resource_binding(
    location,
):
    payload = _payload_with_uses(
        location,
        {
            "bindings": ["missing_binding"],
        },
    )

    with pytest.raises(
        ValidationError,
        match=escape(f"{location}:missing_binding"),
    ):
        ModuleManifest.model_validate(payload)


@pytest.mark.parametrize(
    "location",
    [
        "sources.render[generated]",
        "docker",
        "exports",
    ],
)
def test_module_manifest_rejects_unknown_resource_extension_point(
    location,
):
    payload = _payload_with_uses(
        location,
        {
            "extension_points": ["missing.extension"],
        },
    )

    with pytest.raises(
        ValidationError,
        match=escape(f"{location}:missing.extension"),
    ):
        ModuleManifest.model_validate(payload)


def test_builtin_django_declares_exact_generated_resource_inputs():
    registry = ModuleRegistry(get_builtin_modules_path())
    django = registry.get("django")
    render_sources = {
        source.id: source
        for source in django.sources.render
    }

    assert render_sources["manage"].uses == ResourceInputs()
    assert render_sources["dockerfile"].uses == ResourceInputs()
    assert render_sources["requirements"].uses == ResourceInputs(
        extension_points=["python.dependencies"]
    )
    assert render_sources["settings-base"].uses == ResourceInputs(
        bindings=["primary_database"],
        extension_points=[
            "database.backend",
            "django.settings",
        ],
    )

    assert django.docker is not None
    assert django.docker.uses == ResourceInputs(
        bindings=["primary_database"]
    )

    assert django.exports is not None
    assert django.exports.uses == ResourceInputs(
        bindings=["primary_database"]
    )
