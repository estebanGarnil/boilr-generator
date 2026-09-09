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
    UntrackedResourceObservation,
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
                "user-created.txt",
                fingerprint=FINGERPRINT_B,
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
        "moved": 0,
        "move_candidate": 0,
        "ambiguous_move": 0,
        "type_changed": 1,
        "mode_changed": 1,
        "untracked": 1,
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

    assert [
        resource.path
        for resource in observation.untracked
    ] == [
        "user-created.txt",
    ]

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
        "moved": 0,
        "move_candidate": 0,
        "ambiguous_move": 0,
        "type_changed": 0,
        "mode_changed": 0,
        "untracked": 0,
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
    assert (
        state_api.UntrackedResourceObservation.__module__
        == "boilr_generator.state.observation"
    )

def test_unique_fingerprint_match_is_move_candidate():
    state = _project_state(
        _resource(
            "module:django:render:settings",
            "backend/old-settings.py",
        )
    )

    observation = classify_tracked_resources(
        state,
        [
            _observed(
                "backend/new-settings.py",
                mode=0o600,
            ),
            _observed(
                "user-created.txt",
                fingerprint=FINGERPRINT_B,
            ),
        ],
    )

    resource = observation.resources[0]

    assert resource.status == "move_candidate"
    assert resource.materialized_path == (
        "backend/old-settings.py"
    )
    assert resource.observed_path == (
        "backend/new-settings.py"
    )
    assert resource.candidate_paths == (
        "backend/new-settings.py",
    )
    assert resource.expected_mode == 0o644
    assert resource.observed_mode == 0o600

    assert [
        untracked.path
        for untracked in observation.untracked
    ] == [
        "user-created.txt",
    ]

    serialized_resource = (
        observation.to_dict()["resources"][0]
    )

    assert serialized_resource[
        "candidate_paths"
    ] == [
        "backend/new-settings.py",
    ]


def test_multiple_matches_are_ambiguous_move():
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
                "renamed-z.py"
            ),
            _observed(
                "renamed-a.py"
            ),
        ],
    )

    resource = observation.resources[0]

    assert resource.status == "ambiguous_move"
    assert resource.observed_path is None
    assert resource.candidate_paths == (
        "renamed-a.py",
        "renamed-z.py",
    )
    assert observation.untracked == ()
    assert observation.summary[
        "ambiguous_move"
    ] == 1


def test_shared_candidate_is_ambiguous_for_all_resources():
    state = _project_state(
        _resource(
            "module:django:render:first",
            "backend/first.py",
        ),
        _resource(
            "module:django:render:second",
            "backend/second.py",
        ),
    )

    observation = classify_tracked_resources(
        state,
        [
            _observed(
                "backend/shared.py"
            )
        ],
    )

    assert {
        resource.status
        for resource in observation.resources
    } == {
        "ambiguous_move",
    }
    assert all(
        resource.candidate_paths
        == ("backend/shared.py",)
        for resource in observation.resources
    )
    assert observation.untracked == ()


def test_untracked_resources_exclude_container_directories():
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
                "backend",
                kind="directory",
                mode=0o755,
            ),
            _observed(
                "backend/settings.py"
            ),
            _observed(
                "backend/user.py",
                fingerprint=FINGERPRINT_B,
            ),
            _observed(
                "backend/notes",
                kind="directory",
                mode=0o755,
            ),
            _observed(
                "backend/notes/readme.txt",
                fingerprint=FINGERPRINT_B,
            ),
            _observed(
                "empty-directory",
                kind="directory",
                mode=0o755,
            ),
        ],
    )

    assert observation.resources[0].status == (
        "unchanged"
    )
    assert [
        resource.path
        for resource in observation.untracked
    ] == [
        "backend/notes/readme.txt",
        "backend/user.py",
        "empty-directory",
    ]
    assert all(
        isinstance(
            resource,
            UntrackedResourceObservation,
        )
        for resource in observation.untracked
    )
    assert observation.summary["untracked"] == 3
    assert observation.has_drift is True


def test_nonmatching_path_remains_untracked():
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
                "backend/renamed.py",
                fingerprint=FINGERPRINT_B,
            )
        ],
    )

    tracked = observation.resources[0]

    assert tracked.status == "missing"
    assert tracked.candidate_paths == ()
    assert [
        resource.path
        for resource in observation.untracked
    ] == [
        "backend/renamed.py",
    ]