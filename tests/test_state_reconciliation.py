"""Explicit project-state reconciliation planning tests."""

import json
from pathlib import Path

import pytest

import boilr_generator.state as state_api
from boilr_generator.core.generation_plan import (
    PlannedPathState,
)
from boilr_generator.state import (
    ProjectState,
    ReconciliationMove,
    ReconciliationPlan,
    StateModule,
    StateProject,
    StateResource,
    build_reconciliation_plan,
    classify_tracked_resources,
    fingerprint_model,
)

FINGERPRINT_A = "a" * 64
FINGERPRINT_B = "b" * 64


def _resource(
    resource_id: str,
    path: str,
    *,
    fingerprint: str = FINGERPRINT_A,
) -> StateResource:
    return StateResource(
        id=resource_id,
        kind="file",
        default_path=path,
        desired_path=path,
        materialized_path=path,
        management="generated",
        scope="shared",
        owner="django",
        contributors=("django",),
        content_size=4,
        content_sha256=fingerprint,
        mode=0o644,
        link_target=None,
    )


def _state(
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
    fingerprint: str = FINGERPRINT_A,
    mode: int = 0o644,
) -> PlannedPathState:
    return PlannedPathState(
        path=Path("output") / path,
        relative_path=path,
        exists=True,
        kind="file",
        content_size=4,
        content_sha256=fingerprint,
        mode=mode,
    )


def test_builds_explicit_move_reconciliation_plan():
    resource_id = "module:django:render:settings"
    state = _state(
        _resource(
            resource_id,
            "backend/old-settings.py",
        )
    )
    observation = classify_tracked_resources(
        state,
        [
            _observed(
                "backend/custom-settings.py",
                mode=0o600,
            )
        ],
    )

    plan = build_reconciliation_plan(
        state,
        observation,
        {
            resource_id: (
                "backend/custom-settings.py"
            ),
        },
    )

    assert isinstance(
        plan,
        ReconciliationPlan,
    )
    assert plan.current_state == state
    assert plan.current_state.resources[
        0
    ].materialized_path == (
        "backend/old-settings.py"
    )

    desired_resource = (
        plan.desired_state.resources[0]
    )

    assert desired_resource.default_path == (
        "backend/old-settings.py"
    )
    assert desired_resource.desired_path == (
        "backend/old-settings.py"
    )
    assert desired_resource.materialized_path == (
        "backend/custom-settings.py"
    )
    assert desired_resource.mode == 0o644

    assert plan.moves == (
        ReconciliationMove(
            resource_id=resource_id,
            from_path="backend/old-settings.py",
            to_path="backend/custom-settings.py",
            detected_as="move_candidate",
        ),
    )
    assert plan.has_changes is True
    assert plan.summary == {
        "moves_count": 1,
    }
    assert plan.base_state_sha256 == (
        fingerprint_model(state)
    )
    assert plan.desired_state_sha256 == (
        fingerprint_model(
            plan.desired_state
        )
    )
    assert (
        plan.base_state_sha256
        != plan.desired_state_sha256
    )

    serialized = plan.to_dict()

    assert json.loads(
        json.dumps(serialized)
    ) == serialized
    assert serialized["has_changes"] is True
    assert serialized["moves"] == [
        {
            "resource_id": resource_id,
            "from_path": "backend/old-settings.py",
            "to_path": "backend/custom-settings.py",
            "detected_as": "move_candidate",
        }
    ]
    assert serialized["desired_state"][
        "resources"
    ][0]["materialized_path"] == (
        "backend/custom-settings.py"
    )


def test_accepts_one_explicit_ambiguous_candidate():
    resource_id = "module:django:render:settings"
    state = _state(
        _resource(
            resource_id,
            "backend/settings.py",
        )
    )
    observation = classify_tracked_resources(
        state,
        [
            _observed("renamed-a.py"),
            _observed("renamed-b.py"),
        ],
    )

    plan = build_reconciliation_plan(
        state,
        observation,
        {
            resource_id: "renamed-b.py",
        },
    )

    assert observation.resources[
        0
    ].status == "ambiguous_move"
    assert plan.moves[0].detected_as == (
        "ambiguous_move"
    )
    assert plan.desired_state.resources[
        0
    ].materialized_path == "renamed-b.py"


def test_empty_selection_produces_noop_plan():
    resource_id = "module:django:render:settings"
    state = _state(
        _resource(
            resource_id,
            "backend/settings.py",
        )
    )
    observation = classify_tracked_resources(
        state,
        [
            _observed(
                "backend/settings.py"
            )
        ],
    )

    plan = build_reconciliation_plan(
        state,
        observation,
        {},
    )

    assert plan.moves == ()
    assert plan.has_changes is False
    assert plan.summary == {
        "moves_count": 0,
    }
    assert plan.desired_state == state
    assert (
        plan.desired_state_sha256
        == plan.base_state_sha256
    )


@pytest.mark.parametrize(
    ("accepted_moves", "error_message"),
    [
        (
            {"unknown-resource": "renamed.py"},
            "Unknown reconciliation resource identifiers",
        ),
        (
            {
                "module:django:render:settings": (
                    "not-a-candidate.py"
                )
            },
            "Path is not a candidate",
        ),
    ],
)
def test_rejects_unknown_resources_and_paths(
    accepted_moves,
    error_message,
):
    resource_id = "module:django:render:settings"
    state = _state(
        _resource(
            resource_id,
            "backend/settings.py",
        )
    )
    observation = classify_tracked_resources(
        state,
        [
            _observed("renamed.py")
        ],
    )

    with pytest.raises(
        ValueError,
        match=error_message,
    ):
        build_reconciliation_plan(
            state,
            observation,
            accepted_moves,
        )


def test_rejects_resource_without_move_candidate():
    resource_id = "module:django:render:settings"
    state = _state(
        _resource(
            resource_id,
            "backend/settings.py",
        )
    )
    observation = classify_tracked_resources(
        state,
        [
            _observed(
                "backend/settings.py"
            )
        ],
    )

    with pytest.raises(
        ValueError,
        match=(
            "Resource is not awaiting move reconciliation"
        ),
    ):
        build_reconciliation_plan(
            state,
            observation,
            {
                resource_id: (
                    "backend/settings.py"
                )
            },
        )


def test_rejects_stale_project_observation():
    resource_id = "module:django:render:settings"
    original_state = _state(
        _resource(
            resource_id,
            "backend/original.py",
        )
    )
    observation = classify_tracked_resources(
        original_state,
        [
            _observed("backend/renamed.py")
        ],
    )
    different_state = _state(
        _resource(
            resource_id,
            "backend/different.py",
        )
    )

    with pytest.raises(
        ValueError,
        match="stale materialized paths",
    ):
        build_reconciliation_plan(
            different_state,
            observation,
            {},
        )


def test_rejects_shared_candidate_selected_twice():
    first_id = "module:django:render:first"
    second_id = "module:django:render:second"
    state = _state(
        _resource(
            first_id,
            "backend/first.py",
        ),
        _resource(
            second_id,
            "backend/second.py",
        ),
    )
    observation = classify_tracked_resources(
        state,
        [
            _observed("backend/shared.py")
        ],
    )

    with pytest.raises(
        ValueError,
        match=(
            "cannot be accepted for multiple resources"
        ),
    ):
        build_reconciliation_plan(
            state,
            observation,
            {
                first_id: "backend/shared.py",
                second_id: "backend/shared.py",
            },
        )


def test_plan_is_independent_of_selection_order():
    first_id = "module:django:render:first"
    second_id = "module:django:render:second"
    state = _state(
        _resource(
            first_id,
            "backend/first.py",
            fingerprint=FINGERPRINT_A,
        ),
        _resource(
            second_id,
            "backend/second.py",
            fingerprint=FINGERPRINT_B,
        ),
    )
    observation = classify_tracked_resources(
        state,
        [
            _observed(
                "backend/new-second.py",
                fingerprint=FINGERPRINT_B,
            ),
            _observed(
                "backend/new-first.py",
                fingerprint=FINGERPRINT_A,
            ),
        ],
    )

    first = build_reconciliation_plan(
        state,
        observation,
        {
            second_id: "backend/new-second.py",
            first_id: "backend/new-first.py",
        },
    )
    second = build_reconciliation_plan(
        state,
        observation,
        {
            first_id: "backend/new-first.py",
            second_id: "backend/new-second.py",
        },
    )

    assert first == second
    assert [
        move.resource_id
        for move in first.moves
    ] == [
        first_id,
        second_id,
    ]

    assert (
        state_api.ReconciliationMove.__module__
        == "boilr_generator.state.reconciliation"
    )
    assert (
        state_api.ReconciliationPlan.__module__
        == "boilr_generator.state.reconciliation"
    )
    assert (
        state_api.build_reconciliation_plan.__module__
        == "boilr_generator.state.reconciliation"
    )