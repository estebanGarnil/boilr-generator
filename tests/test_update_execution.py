import stat
from pathlib import Path

import pytest

from boilr_generator.exceptions import (
    FileConflictError,
    StaleGenerationPlanError,
    StateTransactionError,
)
from boilr_generator.generation import (
    ProjectGenerator,
    build_project_update_plan,
    observe_project,
)
from boilr_generator.state import ProjectStateStorage


def _snapshot_output(
    output_path: Path,
) -> tuple[tuple[object, ...], ...]:
    """Capture the complete output including internal state."""
    if not output_path.exists():
        return ()

    entries: list[tuple[object, ...]] = []

    for path in sorted(
        output_path.rglob("*"),
        key=lambda item: item.as_posix(),
    ):
        relative_path = path.relative_to(
            output_path
        ).as_posix()

        if path.is_symlink():
            entries.append(
                (
                    relative_path,
                    "symlink",
                    str(path.readlink()),
                )
            )
        elif path.is_dir():
            entries.append(
                (
                    relative_path,
                    "directory",
                )
            )
        else:
            entries.append(
                (
                    relative_path,
                    "file",
                    path.read_bytes(),
                    stat.S_IMODE(
                        path.stat().st_mode
                    ),
                )
            )

    return tuple(entries)


def _generated_project(
    registry,
    manifest,
    output_path,
):
    generator = ProjectGenerator(registry)
    initial_plan = generator.plan(
        manifest=manifest,
        output_path=output_path,
    )
    generator.execute(initial_plan)

    storage = ProjectStateStorage(output_path)
    current_state = storage.read()

    assert current_state is not None

    return generator, storage, current_state


def _candidate_context(
    generator,
    manifest,
    output_path,
):
    candidate_plan = generator.plan(
        manifest=manifest,
        output_path=output_path,
    )
    observation = observe_project(output_path)

    assert observation is not None

    return candidate_plan, observation


def _planned_file(
    candidate_plan,
    relative_path: str,
):
    return next(
        planned_file
        for planned_file in candidate_plan.files
        if planned_file.relative_destination_path
        == relative_path
    )


def test_execute_update_replaces_file_and_commits_state(
    registry,
    manifest,
    tmp_path,
):
    output_path = tmp_path / "output"
    generator, storage, current_state = (
        _generated_project(
            registry,
            manifest,
            output_path,
        )
    )
    candidate_plan, observation = (
        _candidate_context(
            generator,
            manifest,
            output_path,
        )
    )
    env_file = _planned_file(
        candidate_plan,
        ".env",
    )
    env_file.content = b"UPDATED=value\n"

    update_plan = build_project_update_plan(
        candidate_plan,
        current_state,
        observation,
    )
    previous_state_bytes = (
        storage.state_path.read_bytes()
    )

    generator.execute_update(update_plan)

    assert (output_path / ".env").read_bytes() == (
        b"UPDATED=value\n"
    )
    assert storage.read() == update_plan.desired_state
    assert (
        storage.state_path.read_bytes()
        != previous_state_bytes
    )
    assert not storage.pending_state_path.exists()


def test_execute_update_removes_obsolete_resource(
    registry,
    manifest,
    tmp_path,
):
    output_path = tmp_path / "output"
    generator, storage, current_state = (
        _generated_project(
            registry,
            manifest,
            output_path,
        )
    )
    candidate_plan, observation = (
        _candidate_context(
            generator,
            manifest,
            output_path,
        )
    )
    env_file = _planned_file(
        candidate_plan,
        ".env",
    )
    candidate_plan.files = [
        planned_file
        for planned_file in candidate_plan.files
        if planned_file.resource_id
        != env_file.resource_id
    ]

    update_plan = build_project_update_plan(
        candidate_plan,
        current_state,
        observation,
    )

    generator.execute_update(update_plan)

    updated_state = storage.read()

    assert updated_state is not None
    assert not (output_path / ".env").exists()
    assert env_file.resource_id not in {
        resource.id
        for resource in updated_state.resources
    }
    assert updated_state == update_plan.desired_state
    assert not storage.pending_state_path.exists()


def test_execute_update_relocates_resource(
    registry,
    manifest,
    tmp_path,
):
    output_path = tmp_path / "output"
    generator, storage, current_state = (
        _generated_project(
            registry,
            manifest,
            output_path,
        )
    )
    previous_content = (
        output_path / ".env"
    ).read_bytes()
    candidate_plan, observation = (
        _candidate_context(
            generator,
            manifest,
            output_path,
        )
    )
    env_file = _planned_file(
        candidate_plan,
        ".env",
    )
    env_file.destination_path = (
        output_path / ".env.production"
    )
    env_file.relative_destination_path = (
        ".env.production"
    )

    update_plan = build_project_update_plan(
        candidate_plan,
        current_state,
        observation,
    )

    generator.execute_update(update_plan)

    updated_state = storage.read()

    assert updated_state is not None
    assert not (output_path / ".env").exists()
    assert (
        output_path / ".env.production"
    ).read_bytes() == previous_content

    updated_resource = next(
        resource
        for resource in updated_state.resources
        if resource.id == env_file.resource_id
    )

    assert updated_resource.materialized_path == (
        ".env.production"
    )
    assert updated_state == update_plan.desired_state
    assert not storage.pending_state_path.exists()


def test_execute_update_rejects_conflicts_without_mutation(
    registry,
    manifest,
    tmp_path,
):
    output_path = tmp_path / "output"
    generator, storage, current_state = (
        _generated_project(
            registry,
            manifest,
            output_path,
        )
    )
    (output_path / ".env").write_bytes(
        b"LOCAL=value\n"
    )
    candidate_plan, observation = (
        _candidate_context(
            generator,
            manifest,
            output_path,
        )
    )
    env_file = _planned_file(
        candidate_plan,
        ".env",
    )
    env_file.content = b"DESIRED=value\n"

    update_plan = build_project_update_plan(
        candidate_plan,
        current_state,
        observation,
    )
    before = _snapshot_output(output_path)

    with pytest.raises(
        FileConflictError,
        match="conflicts remain",
    ) as error_info:
        generator.execute_update(update_plan)

    assert error_info.value.context["reason"] == (
        "update_conflicts"
    )
    assert _snapshot_output(output_path) == before
    assert not storage.pending_state_path.exists()


def test_execute_update_rejects_changed_committed_state(
    registry,
    manifest,
    tmp_path,
):
    output_path = tmp_path / "output"
    generator, storage, current_state = (
        _generated_project(
            registry,
            manifest,
            output_path,
        )
    )
    candidate_plan, observation = (
        _candidate_context(
            generator,
            manifest,
            output_path,
        )
    )
    env_file = _planned_file(
        candidate_plan,
        ".env",
    )
    env_file.content = b"UPDATED=value\n"

    update_plan = build_project_update_plan(
        candidate_plan,
        current_state,
        observation,
    )
    external_state = current_state.model_copy(
        update={
            "generator_version": "9.9.9",
        }
    )
    storage.begin(external_state)
    storage.commit(external_state)

    before = _snapshot_output(output_path)

    with pytest.raises(
        StaleGenerationPlanError,
        match="committed project state changed",
    ) as error_info:
        generator.execute_update(update_plan)

    assert error_info.value.context["reason"] == (
        "project_state_changed"
    )
    assert storage.read() == external_state
    assert _snapshot_output(output_path) == before
    assert not storage.pending_state_path.exists()


def test_execute_update_rejects_changed_filesystem(
    registry,
    manifest,
    tmp_path,
):
    output_path = tmp_path / "output"
    generator, storage, current_state = (
        _generated_project(
            registry,
            manifest,
            output_path,
        )
    )
    candidate_plan, observation = (
        _candidate_context(
            generator,
            manifest,
            output_path,
        )
    )
    env_file = _planned_file(
        candidate_plan,
        ".env",
    )
    env_file.content = b"UPDATED=value\n"

    update_plan = build_project_update_plan(
        candidate_plan,
        current_state,
        observation,
    )
    unexpected_path = (
        output_path / "created-after-plan.txt"
    )
    unexpected_path.write_bytes(b"user content")
    state_bytes = storage.state_path.read_bytes()
    before = _snapshot_output(output_path)

    with pytest.raises(
        StaleGenerationPlanError,
        match="filesystem changed",
    ) as error_info:
        generator.execute_update(update_plan)

    assert error_info.value.context["reason"] == (
        "output_state_changed"
    )
    assert storage.state_path.read_bytes() == (
        state_bytes
    )
    assert _snapshot_output(output_path) == before
    assert not storage.pending_state_path.exists()


def test_execute_update_rejects_existing_pending_state(
    registry,
    manifest,
    tmp_path,
):
    output_path = tmp_path / "output"
    generator, storage, current_state = (
        _generated_project(
            registry,
            manifest,
            output_path,
        )
    )
    candidate_plan, observation = (
        _candidate_context(
            generator,
            manifest,
            output_path,
        )
    )
    env_file = _planned_file(
        candidate_plan,
        ".env",
    )
    env_file.content = b"UPDATED=value\n"

    update_plan = build_project_update_plan(
        candidate_plan,
        current_state,
        observation,
    )
    storage.begin(current_state)
    before = _snapshot_output(output_path)

    with pytest.raises(
        StateTransactionError,
        match="pending project state",
    ) as error_info:
        generator.execute_update(update_plan)

    assert error_info.value.context["reason"] == (
        "pending_state_exists"
    )
    assert storage.read() == current_state
    assert storage.read_pending() == current_state
    assert _snapshot_output(output_path) == before


def test_execute_update_failure_preserves_pending_state(
    registry,
    manifest,
    tmp_path,
    monkeypatch,
):
    output_path = tmp_path / "output"
    generator, storage, current_state = (
        _generated_project(
            registry,
            manifest,
            output_path,
        )
    )
    candidate_plan, observation = (
        _candidate_context(
            generator,
            manifest,
            output_path,
        )
    )
    env_file = _planned_file(
        candidate_plan,
        ".env",
    )
    env_file.content = b"UPDATED=value\n"
    update_plan = build_project_update_plan(
        candidate_plan,
        current_state,
        observation,
    )
    previous_state_bytes = (
        storage.state_path.read_bytes()
    )
    previous_env_bytes = (
        output_path / ".env"
    ).read_bytes()

    def fail_write(_planned_file):
        raise RuntimeError(
            "Simulated update failure."
        )

    monkeypatch.setattr(
        generator,
        "_write_planned_file",
        fail_write,
    )

    with pytest.raises(
        RuntimeError,
        match="Simulated update failure",
    ):
        generator.execute_update(update_plan)

    assert storage.read() == current_state
    assert storage.state_path.read_bytes() == (
        previous_state_bytes
    )
    assert storage.read_pending() == (
        update_plan.desired_state
    )
    assert (output_path / ".env").read_bytes() == (
        previous_env_bytes
    )


def test_noop_update_does_not_start_transaction(
    registry,
    manifest,
    tmp_path,
    monkeypatch,
):
    output_path = tmp_path / "output"
    generator, storage, current_state = (
        _generated_project(
            registry,
            manifest,
            output_path,
        )
    )
    candidate_plan, observation = (
        _candidate_context(
            generator,
            manifest,
            output_path,
        )
    )
    update_plan = build_project_update_plan(
        candidate_plan,
        current_state,
        observation,
    )
    before = _snapshot_output(output_path)

    def fail_begin(self, state):
        raise AssertionError(
            "A no-op update must not start a transaction."
        )

    monkeypatch.setattr(
        ProjectStateStorage,
        "begin",
        fail_begin,
    )

    generator.execute_update(update_plan)

    assert _snapshot_output(output_path) == before
    assert storage.read() == current_state
    assert not storage.pending_state_path.exists()


def test_execute_update_rejects_altered_file_content(
    registry,
    manifest,
    tmp_path,
):
    output_path = tmp_path / "output"
    generator, storage, current_state = (
        _generated_project(
            registry,
            manifest,
            output_path,
        )
    )
    candidate_plan, observation = (
        _candidate_context(
            generator,
            manifest,
            output_path,
        )
    )
    env_file = _planned_file(
        candidate_plan,
        ".env",
    )
    env_file.content = b"UPDATED=value\n"

    update_plan = build_project_update_plan(
        candidate_plan,
        current_state,
        observation,
    )
    execution_plan = update_plan.execution_plan

    assert execution_plan is not None
    assert execution_plan.files

    execution_plan.files[0].content = (
        b"TAMPERED=value\n"
    )
    before = _snapshot_output(output_path)

    with pytest.raises(
        StaleGenerationPlanError,
        match="materialized contract is invalid",
    ) as error_info:
        generator.execute_update(update_plan)

    assert error_info.value.context["reason"] == (
        "invalid_update_execution_plan"
    )
    assert any(
        error.startswith(
            "file_metadata_mismatch:"
        )
        for error in error_info.value.context[
            "errors"
        ]
    )
    assert _snapshot_output(output_path) == before
    assert storage.read() == current_state
    assert not storage.pending_state_path.exists()