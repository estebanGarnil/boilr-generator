from copy import deepcopy

import pytest
from pydantic import ValidationError

from boilr_generator.state import ProjectState


FINGERPRINT = "a" * 64


def _state_payload():
    return {
        "schema_version": 1,
        "generator_version": "0.1.0",
        "project": {
            "name": "my_app",
            "type": "fullstack_web",
            "version": "1.0.0",
            "manifest_sha256": FINGERPRINT,
        },
        "modules": [
            {
                "key": "postgres",
                "version": "1.0.0",
                "origin": "builtin",
                "manifest_sha256": FINGERPRINT,
                "destination": "database",
            },
            {
                "key": "django-postgres",
                "version": "1.0.0",
                "origin": "builtin",
                "manifest_sha256": FINGERPRINT,
                "destination": ".",
            },
            {
                "key": "django",
                "version": "1.0.0",
                "origin": "builtin",
                "manifest_sha256": FINGERPRINT,
                "destination": "backend",
            },
        ],
        "bindings": [
            {
                "consumer_module": "django",
                "binding": "primary_database",
                "capability": "database.connection",
                "provider_module": "postgres",
            }
        ],
        "resources": [
            {
                "id": "resource:z",
                "kind": "file",
                "default_path": "backend/z.txt",
                "desired_path": "backend/z.txt",
                "materialized_path": "backend/z.txt",
                "management": "generated",
                "scope": "shared",
                "owner": "django",
                "contributors": [
                    "django-postgres",
                    "django",
                ],
                "content_size": 1,
                "content_sha256": FINGERPRINT,
                "mode": 420,
                "link_target": None,
            },
            {
                "id": "resource:a",
                "kind": "directory",
                "default_path": "backend/a",
                "desired_path": "backend/a",
                "materialized_path": "backend/a",
                "management": "generated",
                "scope": "shared",
                "owner": "django",
                "contributors": ["django"],
                "content_size": None,
                "content_sha256": None,
                "mode": None,
                "link_target": None,
            },
        ],
    }


def test_project_state_accepts_valid_state():
    state = ProjectState.model_validate(
        _state_payload()
    )

    assert state.schema_version == 1
    assert state.project.name == "my_app"
    assert len(state.modules) == 3
    assert len(state.bindings) == 1
    assert len(state.resources) == 2


def test_project_state_canonicalizes_collections():
    state = ProjectState.model_validate(
        _state_payload()
    )

    assert [
        module.key
        for module in state.modules
    ] == [
        "django",
        "django-postgres",
        "postgres",
    ]

    assert [
        resource.id
        for resource in state.resources
    ] == [
        "resource:a",
        "resource:z",
    ]

    assert state.resources[1].contributors == (
        "django",
        "django-postgres",
    )


def test_project_state_round_trip_preserves_state():
    state = ProjectState.model_validate(
        _state_payload()
    )

    reloaded = ProjectState.model_validate_json(
        state.model_dump_json()
    )

    assert reloaded == state


@pytest.mark.parametrize(
    "field",
    [
        "default_path",
        "desired_path",
        "materialized_path",
    ],
)
@pytest.mark.parametrize(
    "invalid_path",
    [
        "/outside.txt",
        "C:/outside.txt",
        "../outside.txt",
        ".boilr/state.json",
    ],
)
def test_project_state_rejects_unsafe_resource_paths(
    field,
    invalid_path,
):
    payload = _state_payload()
    payload["resources"][0][field] = invalid_path

    with pytest.raises(ValidationError):
        ProjectState.model_validate(payload)


def test_project_state_rejects_unknown_owner():
    payload = _state_payload()
    payload["resources"][0]["owner"] = (
        "unknown-module"
    )

    with pytest.raises(ValidationError):
        ProjectState.model_validate(payload)


def test_project_state_rejects_unknown_contributor():
    payload = _state_payload()
    payload["resources"][0]["contributors"].append(
        "unknown-module"
    )

    with pytest.raises(ValidationError):
        ProjectState.model_validate(payload)


def test_project_state_rejects_unknown_binding_provider():
    payload = _state_payload()
    payload["bindings"][0]["provider_module"] = (
        "unknown-module"
    )

    with pytest.raises(ValidationError):
        ProjectState.model_validate(payload)


def test_project_state_rejects_duplicate_module_keys():
    payload = _state_payload()
    payload["modules"].append(
        deepcopy(payload["modules"][0])
    )

    with pytest.raises(ValidationError):
        ProjectState.model_validate(payload)


def test_project_state_rejects_duplicate_resource_ids():
    payload = _state_payload()
    duplicate = deepcopy(payload["resources"][0])
    duplicate["default_path"] = "backend/copy.txt"
    duplicate["desired_path"] = "backend/copy.txt"
    duplicate["materialized_path"] = (
        "backend/copy.txt"
    )
    payload["resources"].append(duplicate)

    with pytest.raises(ValidationError):
        ProjectState.model_validate(payload)


def test_project_state_rejects_unknown_schema_version():
    payload = _state_payload()
    payload["schema_version"] = 2

    with pytest.raises(ValidationError):
        ProjectState.model_validate(payload)


def test_project_state_rejects_extra_fields():
    payload = _state_payload()
    payload["unexpected"] = True

    with pytest.raises(ValidationError):
        ProjectState.model_validate(payload)