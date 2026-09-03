from pathlib import Path

import pytest

import boilr_generator.generation as generation_api
from boilr_generator.exceptions import (
    StaleGenerationPlanError,
    StateTransactionError,
)
from boilr_generator.generation import (
    ProjectGenerator,
    apply_reconciliation_plan,
    observe_project,
)
from boilr_generator.generation.filesystem import (
    capture_output_state,
)
from boilr_generator.state import (
    ProjectStateStorage,
    build_reconciliation_plan,
)


def _moved_environment_plan(
    registry,
    manifest,
    output_path: Path,
):
    generator = ProjectGenerator(registry)
    generation_plan = generator.plan(
        manifest=manifest,
        output_path=output_path,
    )
    generator.execute(generation_plan)

    storage = ProjectStateStorage(output_path)
    current_state = storage.read()

    assert current_state is not None

    resource = next(
        resource
        for resource in current_state.resources
        if resource.materialized_path == ".env"
    )
    source_path = (
        output_path / resource.materialized_path
    )
    moved_path = output_path / ".env.local"
    content = source_path.read_bytes()

    source_path.rename(moved_path)

    observation = observe_project(output_path)

    assert observation is not None

    resource_observation = next(
        item
        for item in observation.resources
        if item.resource_id == resource.id
    )

    assert resource_observation.status == (
        "move_candidate"
    )
    assert resource_observation.candidate_paths == (
        ".env.local",
    )

    reconciliation_plan = build_reconciliation_plan(
        current_state,
        observation,
        {
            resource.id: ".env.local",
        },
    )

    return (
        storage,
        current_state,
        reconciliation_plan,
        content,
    )


def test_apply_reconciliation_plan_commits_only_state(
    registry,
    manifest,
    tmp_path,
):
    output_path = tmp_path / "output"
    (
        storage,
        current_state,
        reconciliation_plan,
        content,
    ) = _moved_environment_plan(
        registry,
        manifest,
        output_path,
    )

    state_bytes_before = (
        storage.state_path.read_bytes()
    )
    filesystem_before = capture_output_state(
        output_path
    )

    state_path = apply_reconciliation_plan(
        output_path,
        reconciliation_plan,
    )

    assert state_path == storage.state_path
    assert storage.read() == (
        reconciliation_plan.desired_state
    )
    assert storage.read() != current_state
    assert not storage.pending_state_path.exists()
    assert storage.state_path.read_bytes() != (
        state_bytes_before
    )
    assert capture_output_state(output_path) == (
        filesystem_before
    )
    assert not (output_path / ".env").exists()
    assert (
        output_path / ".env.local"
    ).read_bytes() == content

    observation = observe_project(output_path)

    assert observation is not None

    resource_observation = next(
        item
        for item in observation.resources
        if item.resource_id
        == reconciliation_plan.moves[0].resource_id
    )

    assert resource_observation.status == "unchanged"
    assert resource_observation.materialized_path == (
        ".env.local"
    )


def test_apply_reconciliation_plan_rejects_changed_state(
    registry,
    manifest,
    tmp_path,
):
    output_path = tmp_path / "output"
    (
        storage,
        current_state,
        reconciliation_plan,
        _,
    ) = _moved_environment_plan(
        registry,
        manifest,
        output_path,
    )

    changed_state = current_state.model_copy(
        update={
            "generator_version": "changed-version",
        }
    )
    storage.begin(changed_state)
    storage.commit(changed_state)

    state_bytes_before = (
        storage.state_path.read_bytes()
    )
    filesystem_before = capture_output_state(
        output_path
    )

    with pytest.raises(
        StaleGenerationPlanError,
        match="no longer matches",
    ):
        apply_reconciliation_plan(
            output_path,
            reconciliation_plan,
        )

    assert storage.state_path.read_bytes() == (
        state_bytes_before
    )
    assert storage.read() == changed_state
    assert not storage.pending_state_path.exists()
    assert capture_output_state(output_path) == (
        filesystem_before
    )


def test_apply_reconciliation_plan_rejects_changed_candidate(
    registry,
    manifest,
    tmp_path,
):
    output_path = tmp_path / "output"
    (
        storage,
        current_state,
        reconciliation_plan,
        _,
    ) = _moved_environment_plan(
        registry,
        manifest,
        output_path,
    )

    (output_path / ".env.local").write_bytes(
        b"changed after reconciliation planning"
    )

    state_bytes_before = (
        storage.state_path.read_bytes()
    )
    filesystem_before = capture_output_state(
        output_path
    )

    with pytest.raises(
        StaleGenerationPlanError,
        match="no longer matches",
    ):
        apply_reconciliation_plan(
            output_path,
            reconciliation_plan,
        )

    assert storage.state_path.read_bytes() == (
        state_bytes_before
    )
    assert storage.read() == current_state
    assert not storage.pending_state_path.exists()
    assert capture_output_state(output_path) == (
        filesystem_before
    )


def test_apply_reconciliation_plan_rejects_existing_pending(
    registry,
    manifest,
    tmp_path,
):
    output_path = tmp_path / "output"
    (
        storage,
        current_state,
        reconciliation_plan,
        _,
    ) = _moved_environment_plan(
        registry,
        manifest,
        output_path,
    )

    storage.begin(
        reconciliation_plan.desired_state
    )

    state_bytes_before = (
        storage.state_path.read_bytes()
    )
    pending_bytes_before = (
        storage.pending_state_path.read_bytes()
    )
    filesystem_before = capture_output_state(
        output_path
    )

    with pytest.raises(
        StateTransactionError,
        match="Unable to apply",
    ):
        apply_reconciliation_plan(
            output_path,
            reconciliation_plan,
        )

    assert storage.state_path.read_bytes() == (
        state_bytes_before
    )
    assert storage.read() == current_state
    assert (
        storage.pending_state_path.read_bytes()
        == pending_bytes_before
    )
    assert capture_output_state(output_path) == (
        filesystem_before
    )


def test_apply_reconciliation_plan_preserves_pending_on_commit_failure(
    registry,
    manifest,
    tmp_path,
    monkeypatch,
):
    output_path = tmp_path / "output"
    (
        storage,
        current_state,
        reconciliation_plan,
        _,
    ) = _moved_environment_plan(
        registry,
        manifest,
        output_path,
    )

    state_bytes_before = (
        storage.state_path.read_bytes()
    )
    filesystem_before = capture_output_state(
        output_path
    )

    def fail_replace(
        source: Path,
        destination: Path,
    ) -> None:
        assert Path(source) == (
            storage.pending_state_path
        )
        assert Path(destination) == (
            storage.state_path
        )

        raise PermissionError(
            13,
            "Access denied",
        )

    monkeypatch.setattr(
        "boilr_generator.state.storage.os.replace",
        fail_replace,
    )

    with pytest.raises(
        StateTransactionError,
        match="Unable to apply",
    ):
        apply_reconciliation_plan(
            output_path,
            reconciliation_plan,
        )

    assert storage.state_path.read_bytes() == (
        state_bytes_before
    )
    assert storage.read() == current_state
    assert storage.read_pending() == (
        reconciliation_plan.desired_state
    )
    assert capture_output_state(output_path) == (
        filesystem_before
    )


def test_apply_noop_reconciliation_does_not_start_transaction(
    registry,
    manifest,
    tmp_path,
    monkeypatch,
):
    output_path = tmp_path / "output"
    generator = ProjectGenerator(registry)
    generation_plan = generator.plan(
        manifest=manifest,
        output_path=output_path,
    )
    generator.execute(generation_plan)

    storage = ProjectStateStorage(output_path)
    current_state = storage.read()
    observation = observe_project(output_path)

    assert current_state is not None
    assert observation is not None

    reconciliation_plan = build_reconciliation_plan(
        current_state,
        observation,
        {},
    )
    state_bytes_before = (
        storage.state_path.read_bytes()
    )
    filesystem_before = capture_output_state(
        output_path
    )

    def fail_transaction(
        *_args,
        **_kwargs,
    ):
        raise AssertionError(
            "A no-op plan must not start a transaction."
        )

    monkeypatch.setattr(
        ProjectStateStorage,
        "begin",
        fail_transaction,
    )
    monkeypatch.setattr(
        ProjectStateStorage,
        "commit",
        fail_transaction,
    )

    state_path = apply_reconciliation_plan(
        output_path,
        reconciliation_plan,
    )

    assert state_path == storage.state_path
    assert storage.state_path.read_bytes() == (
        state_bytes_before
    )
    assert not storage.pending_state_path.exists()
    assert capture_output_state(output_path) == (
        filesystem_before
    )


def test_apply_reconciliation_plan_requires_committed_state(
    registry,
    manifest,
    tmp_path,
):
    source_output_path = (
        tmp_path / "source-output"
    )
    (
        _,
        _,
        reconciliation_plan,
        _,
    ) = _moved_environment_plan(
        registry,
        manifest,
        source_output_path,
    )
    missing_output_path = (
        tmp_path / "missing-output"
    )

    with pytest.raises(
        StateTransactionError,
        match="Unable to apply",
    ):
        apply_reconciliation_plan(
            missing_output_path,
            reconciliation_plan,
        )

    assert not missing_output_path.exists()


def test_generation_public_api_exports_reconciliation_application():
    assert (
        generation_api.apply_reconciliation_plan
        is apply_reconciliation_plan
    )
    assert (
        apply_reconciliation_plan.__module__
        == "boilr_generator.generation.reconciliation"
    )