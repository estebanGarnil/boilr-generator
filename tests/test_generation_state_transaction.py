"""Transactional project-state generation tests."""

from pathlib import Path

import pytest

from boilr_generator.exceptions import (
    StateTransactionError,
    UnsafePathError,
)
from boilr_generator.generation import (
    ProjectGenerator,
)
from boilr_generator.state import (
    ProjectStateStorage,
    serialize_project_state,
)


def test_execute_persists_canonical_project_state(
    registry,
    manifest,
    tmp_path,
):
    output_path = tmp_path / "output"
    generator = ProjectGenerator(registry)

    plan = generator.plan(
        manifest=manifest,
        output_path=output_path,
    )

    assert plan.desired_state is not None

    generator.execute(plan)

    storage = ProjectStateStorage(output_path)

    assert storage.read() == plan.desired_state
    assert storage.read_pending() is None
    assert storage.state_path.read_bytes() == (
        serialize_project_state(
            plan.desired_state
        )
    )


def test_existing_pending_blocks_before_clean_mutation(
    registry,
    manifest,
    tmp_path,
):
    output_path = tmp_path / "output"
    protected_path = output_path / "protected.txt"

    output_path.mkdir()
    protected_path.write_bytes(b"keep")

    generator = ProjectGenerator(registry)
    plan = generator.plan(
        manifest=manifest,
        output_path=output_path,
        clean=True,
    )

    assert plan.desired_state is not None

    storage = ProjectStateStorage(output_path)
    storage.begin(plan.desired_state)

    with pytest.raises(
        StateTransactionError
    ) as error_info:
        generator.execute(plan)

    error = error_info.value

    assert error.code == "state_transaction_error"
    assert error.context["reason"] == (
        "pending_state_exists"
    )
    assert error.context["pending_state_path"] == str(
        storage.pending_state_path
    )
    assert protected_path.read_bytes() == b"keep"
    assert storage.read() is None
    assert storage.read_pending() == (
        plan.desired_state
    )


def test_execution_failure_preserves_pending_state(
    registry,
    manifest,
    tmp_path,
    monkeypatch,
):
    output_path = tmp_path / "output"
    generator = ProjectGenerator(registry)

    plan = generator.plan(
        manifest=manifest,
        output_path=output_path,
    )

    assert plan.desired_state is not None
    assert plan.files

    def fail_write(_planned_file):
        raise RuntimeError(
            "Simulated generation failure."
        )

    monkeypatch.setattr(
        generator,
        "_write_planned_file",
        fail_write,
    )

    with pytest.raises(
        RuntimeError,
        match="Simulated generation failure",
    ):
        generator.execute(plan)

    storage = ProjectStateStorage(output_path)

    assert storage.read() is None
    assert storage.read_pending() == (
        plan.desired_state
    )


def test_preflight_failure_does_not_start_transaction(
    registry,
    manifest,
    tmp_path,
):
    output_path = tmp_path / "output"
    generator = ProjectGenerator(registry)

    plan = generator.plan(
        manifest=manifest,
        output_path=output_path,
    )

    assert plan.desired_state is not None
    assert plan.files

    plan.files[0].destination_path = (
        tmp_path / "outside.txt"
    )

    with pytest.raises(UnsafePathError):
        generator.execute(plan)

    storage = ProjectStateStorage(output_path)

    assert output_path.exists() is False
    assert storage.state_path.exists() is False
    assert storage.pending_state_path.exists() is False


def test_failed_atomic_commit_preserves_previous_state(
    registry,
    manifest,
    tmp_path,
    monkeypatch,
):
    output_path = tmp_path / "output"
    generator = ProjectGenerator(registry)

    baseline_plan = generator.plan(
        manifest=manifest,
        output_path=output_path,
    )

    assert baseline_plan.desired_state is not None

    storage = ProjectStateStorage(output_path)
    storage.begin(baseline_plan.desired_state)
    storage.commit(baseline_plan.desired_state)

    previous_state = storage.read()
    previous_bytes = storage.state_path.read_bytes()

    updated_manifest = manifest.model_copy(
        update={
            "project": manifest.project.model_copy(
                update={
                    "version": "2.0.0",
                }
            ),
        },
        deep=True,
    )

    updated_plan = generator.plan(
        manifest=updated_manifest,
        output_path=output_path,
    )

    assert updated_plan.desired_state is not None
    assert (
        updated_plan.desired_state
        != baseline_plan.desired_state
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
        StateTransactionError
    ) as error_info:
        generator.execute(updated_plan)

    error = error_info.value

    assert isinstance(
        error.__cause__,
        PermissionError,
    )
    assert error.context["reason"] == (
        "state_commit_failed"
    )
    assert storage.state_path.read_bytes() == (
        previous_bytes
    )
    assert storage.read() == previous_state
    assert storage.read_pending() == (
        updated_plan.desired_state
    )