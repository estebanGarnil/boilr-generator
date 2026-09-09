import json

import pytest
import yaml
from pydantic import ValidationError

import boilr_generator.state as state_api
from boilr_generator.manifest.schemas import (
    ProjectManifest,
)
from boilr_generator.state import (
    ProjectState,
    deserialize_project_state,
    fingerprint_model,
    serialize_project_state,
)

FINGERPRINT = "a" * 64


def _project_state() -> ProjectState:
    return ProjectState.model_validate(
        {
            "schema_version": 1,
            "generator_version": "0.1.0",
            "project": {
                "name": "café",
                "type": "fullstack_web",
                "version": "1.0.0",
                "manifest_sha256": FINGERPRINT,
            },
            "modules": [
                {
                    "key": "django",
                    "version": "1.0.0",
                    "origin": "builtin",
                    "manifest_sha256": FINGERPRINT,
                    "destination": "backend",
                }
            ],
            "bindings": [],
            "resources": [
                {
                    "id": "resource:z",
                    "kind": "directory",
                    "default_path": "backend/z",
                    "desired_path": "backend/z",
                    "materialized_path": "backend/z",
                    "management": "generated",
                    "scope": "shared",
                    "owner": "django",
                    "contributors": ["django"],
                    "content_size": None,
                    "content_sha256": None,
                    "mode": None,
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
    )


def _manifest(content: str) -> ProjectManifest:
    return ProjectManifest.model_validate(
        yaml.safe_load(content)
    )


def test_state_public_api_exports_serialization_helpers():
    assert state_api.__all__ == [
        "ProjectObservation",
        "ProjectState",
        "ProjectStateStorage",
        "ReconciliationMove",
        "ReconciliationPlan",
        "StateBinding",
        "StateModule",
        "StateProject",
        "StateResource",
        "TrackedResourceObservation",
        "UntrackedResourceObservation",
        "build_initial_project_state",
        "build_reconciliation_plan",
        "classify_tracked_resources",
        "deserialize_project_state",
        "fingerprint_model",
        "serialize_project_state",
    ]



def test_serialize_project_state_is_deterministic():
    state = _project_state()

    first = serialize_project_state(state)
    second = serialize_project_state(state)

    assert first == second
    assert first.endswith(b"\n")
    assert b"\r" not in first



def test_serialize_project_state_uses_readable_utf8():
    serialized = serialize_project_state(
        _project_state()
    )

    assert "café".encode() in serialized
    assert b"\\u00e9" not in serialized


def test_serialize_project_state_preserves_canonical_order():
    serialized = serialize_project_state(
        _project_state()
    )
    document = json.loads(serialized)

    assert [
        resource["id"]
        for resource in document["resources"]
    ] == [
        "resource:a",
        "resource:z",
    ]


@pytest.mark.parametrize(
    "as_text",
    [
        False,
        True,
    ],
)
def test_deserialize_project_state_round_trip(
    as_text,
):
    state = _project_state()
    serialized = serialize_project_state(state)

    content = (
        serialized.decode("utf-8")
        if as_text
        else serialized
    )

    assert deserialize_project_state(content) == state


def test_deserialize_project_state_rejects_unknown_version():
    serialized = serialize_project_state(
        _project_state()
    )
    document = json.loads(serialized)
    document["schema_version"] = 2

    invalid_content = json.dumps(
        document
    ).encode("utf-8")

    with pytest.raises(ValidationError):
        deserialize_project_state(
            invalid_content
        )


def test_deserialize_project_state_rejects_invalid_json():
    with pytest.raises(ValidationError):
        deserialize_project_state(b"{")


def test_fingerprint_model_normalizes_manifest_format():
    manifest_a = _manifest(
        """
project:
  name: my_app
  type: fullstack_web
modules:
  - key: django
"""
    )

    manifest_b = _manifest(
        """
modules: [{key: django}]
project:
  type: fullstack_web
  version: "1.0.0"
  name: my_app
"""
    )

    assert fingerprint_model(
        manifest_a
    ) == fingerprint_model(
        manifest_b
    )


def test_fingerprint_model_returns_sha256():
    fingerprint = fingerprint_model(
        _manifest(
            """
project:
  name: my_app
  type: fullstack_web
modules:
  - key: django
"""
        )
    )

    assert len(fingerprint) == 64
    assert set(fingerprint) <= set(
        "0123456789abcdef"
    )


def test_fingerprint_model_detects_manifest_change():
    manifest_a = _manifest(
        """
project:
  name: first_app
  type: fullstack_web
modules:
  - key: django
"""
    )

    manifest_b = _manifest(
        """
project:
  name: second_app
  type: fullstack_web
modules:
  - key: django
"""
    )

    assert fingerprint_model(
        manifest_a
    ) != fingerprint_model(
        manifest_b
    )

def test_state_public_api_exports_storage():
    import boilr_generator.state as state_package
    from boilr_generator.state.storage import (
        ProjectStateStorage,
    )

    assert (
        state_package.ProjectStateStorage
        is ProjectStateStorage
    )