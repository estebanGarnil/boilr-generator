"""Tracked project-resource observation tests."""

import json
from pathlib import Path

import pytest

import boilr_generator.state as state_api
from boilr_generator.core.generation_plan import (
    PathKind,
    PlannedPathState,
)
from boilr_generator.state import (
    ProjectObservation,
    ProjectState,
    StateModule,
    StateProject,
    StateResource,
    TrackedResourceObservation,
    classify_tracked_resources,
)

FINGERPRINT_A = "a" * 64
FINGERPRINT_B = "b" * 64


def _resource(
    resource_id: str,
    path: str,
    *,
    kind: PathKind = "file",
    fingerprint: str = FINGERPRINT_A,
    mode: int | None = 0o644,
    link_target: str | None = None,
) -> StateResource:
    return StateResource(
        id=resource_id,
        kind=kind,
        default_path=path,
        desired_path=path,
        materialized_path=path,
        management="generated",
        scope="shared",
        owner="django",
        contributors=("django",),
        content_size=(
            4
            if kind == "file"
            else None
        ),
        content_sha256=(
            fingerprint
            if kind == "file"
            else None
        ),
        mode=mode,
        link_target=(
            link_target
            if kind == "symlink"
            else None
        ),
    )


def _project_state(
    *resources: StateResource,
) -> ProjectState:
    return ProjectState(
        schema_version=1,
        generator_version="0.1.0",
        project=StateProject(
            name="my_app",
            type="fullstack_web",
            version="1.0.0",
            manifest_sha256=FINGERPRINT_A,
        ),
        modules=(
            StateModule(
                key="django",
                version="1.0.0",
                origin="builtin",
                manifest_sha256=FINGERPRINT_A,
                destination="backend",
            ),
        ),
        bindings=(),
        resources=resources,
    )


def _observed(
    path: str,
    *,
    kind: PathKind = "file",
    fingerprint: str = FINGERPRINT_A,
    mode: int | None = 0o644,
    link_target: str | None = None,
) -> PlannedPathState:
    return PlannedPathState(
        path=Path("output") / path,
        relative_path=path,
        exists=True,
        kind=kind,
        content_size=(
            4
            if kind == "file"
            else None
        ),
        content_sha256=(
            fingerprint
            if kind == "file"
            else None
        ),
        mode=mode,
        link_target=(
            link_target
            if kind == "symlink"
            else None
        ),
    )


def test_classifies_direct_tracked_resource_drift():
    state = _project_state(
        _resource(
            "module:django:render:unchanged",
            "backend/unchanged.py",
        ),
        _resource(
            "module:django:render:modified",
            "backend/modified.py",
        ),
        _resource(
            "module:django:render:missing",
            "backend/missing.py",
        ),
        _resource(
            "module:django:render:type-changed",
            "backend/type-changed.py",
        ),
        _resource(
            "module:django:render:mode-changed",
            "backend/mode-changed.py",
        ),
        _resource(
            "module:django:render:link",
            "backend/current-link",
            kind="symlink",
            mode=None,
            link_target="first-target",
        ),
    )

    observation = classify_tracked_resources(
        state,
        [
            _observed(
                "backend/unchanged.py"
            ),
            _observed(
                "backend/modified.py",
                fingerprint=FINGERPRINT_B,
            ),
            _observed(
                "backend/type-changed.py",
                kind="directory",
                mode=0o755,
            ),
            _observed(
                "backend/mode-changed.py",
                mode=0o600,
            ),
            _observed(
                "backend/current-link",
                kind="symlink",
                mode=None,
                link_target="second-target",
            ),
            _observed(
                "user-created.txt"
            ),
        ],
    )

    statuses = {
        resource.resource_id: resource.status
        for resource in observation.resources
    }

    assert statuses == {
        "module:django:render:link": (
            "modified"
        ),
        "module:django:render:missing": (
            "missing"
        ),
        "module:django:render:mode-changed": (
            "mode_changed"
        ),
        "module:django:render:modified": (
            "modified"
        ),
        "module:django:render:type-changed": (
            "type_changed"
        ),
        "module:django:render:unchanged": (
            "unchanged"
        ),
    }

    assert observation.summary == {
        "unchanged": 1,
        "modified": 2,
        "missing": 1,
        "type_changed": 1,
        "mode_changed": 1,
    }
    assert observation.has_drift is True

    missing = next(
        resource
        for resource in observation.resources
        if resource.status == "missing"
    )

    assert missing.observed_path is None
    assert missing.observed_kind is None

    assert all(
        resource.observed_path
        != "user-created.txt"
        for resource in observation.resources
    )


def test_unspecified_mode_is_not_considered_drift():
    state = _project_state(
        _resource(
            "module:django:render:settings",
            "backend/settings.py",
            mode=None,
        )
    )

    observation = classify_tracked_resources(
        state,
        [
            _observed(
                "backend/settings.py",
                mode=0o600,
            )
        ],
    )

    resource = observation.resources[0]

    assert resource.status == "unchanged"
    assert resource.expected_mode is None
    assert resource.observed_mode == 0o600
    assert observation.has_drift is False


def test_content_change_takes_priority_over_mode_change():
    state = _project_state(
        _resource(
            "module:django:render:settings",
            "backend/settings.py",
        )
    )

    observation = classify_tracked_resources(
        state,
        [
            _observed(
                "backend/settings.py",
                fingerprint=FINGERPRINT_B,
                mode=0o600,
            )
        ],
    )

    resource = observation.resources[0]

    assert resource.status == "modified"
    assert (
        resource.expected_content_sha256
        == FINGERPRINT_A
    )
    assert (
        resource.observed_content_sha256
        == FINGERPRINT_B
    )
    assert resource.expected_mode == 0o644
    assert resource.observed_mode == 0o600


def test_duplicate_observed_paths_are_rejected():
    state = _project_state(
        _resource(
            "module:django:render:settings",
            "backend/settings.py",
        )
    )
    observed = _observed(
        "backend/settings.py"
    )

    with pytest.raises(
        ValueError,
        match="Duplicate observed filesystem path",
    ):
        classify_tracked_resources(
            state,
            [
                observed,
                observed,
            ],
        )


def test_observation_is_deterministic_and_json_compatible():
    state = _project_state(
        _resource(
            "module:django:render:settings",
            "backend/settings.py",
        )
    )

    first = classify_tracked_resources(
        state,
        [
            _observed(
                "backend/settings.py"
            )
        ],
    )
    second = classify_tracked_resources(
        state,
        [
            _observed(
                "backend/settings.py"
            )
        ],
    )

    assert first == second
    assert isinstance(
        first,
        ProjectObservation,
    )
    assert isinstance(
        first.resources[0],
        TrackedResourceObservation,
    )
    assert first.summary == {
        "unchanged": 1,
        "modified": 0,
        "missing": 0,
        "type_changed": 0,
        "mode_changed": 0,
    }
    assert first.has_drift is False

    serialized = first.to_dict()

    assert (
        json.loads(
            json.dumps(serialized)
        )
        == serialized
    )

    assert (
        state_api.ProjectObservation.__module__
        == "boilr_generator.state.observation"
    )
    assert (
        state_api.TrackedResourceObservation.__module__
        == "boilr_generator.state.observation"
    )
    assert (
        state_api.classify_tracked_resources.__module__
        == "boilr_generator.state.observation"
    )