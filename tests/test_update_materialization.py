import json
import stat
from pathlib import Path

import pytest

from boilr_generator.core.generation_plan import (
    PlannedFile,
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
    """Capture output data to prove planning is read-only."""
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


def _update_context(
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

    candidate_plan = generator.plan(
        manifest=manifest,
        output_path=output_path,
    )
    observation = observe_project(output_path)

    assert observation is not None

    return (
        generator,
        current_state,
        candidate_plan,
        observation,
    )


def _execution_plan(update_plan):
    execution_plan = update_plan.execution_plan

    assert execution_plan is not None

    return execution_plan


def _planned_file_for_path(
    candidate_plan,
    relative_path: str,
):
    return next(
        planned_file
        for planned_file in candidate_plan.files
        if planned_file.relative_destination_path
        == relative_path
    )


def test_noop_update_materializes_empty_execution_plan(
    registry,
    manifest,
    tmp_path,
):
    output_path = tmp_path / "output"
    (
        _,
        current_state,
        candidate_plan,
        observation,
    ) = _update_context(
        registry,
        manifest,
        output_path,
    )
    before = _snapshot_output(output_path)

    update_plan = build_project_update_plan(
        candidate_plan,
        current_state,
        observation,
    )
    execution_plan = _execution_plan(
        update_plan
    )

    assert update_plan.can_execute is True
    assert update_plan.has_changes is False
    assert execution_plan.clean_output is False
    assert execution_plan.files == []
    assert execution_plan.removals == []
    assert execution_plan.directories == []
    assert (
        execution_plan.desired_state
        == current_state
    )
    assert _snapshot_output(output_path) == before

    data = update_plan.to_dict()

    assert json.loads(json.dumps(data)) == data
    assert data["execution_plan"] is not None
    assert (
        data["execution_plan"]["clean_output"]
        is False
    )


def test_safe_replacement_materializes_one_overwrite(
    registry,
    manifest,
    tmp_path,
):
    output_path = tmp_path / "output"
    (
        _,
        current_state,
        candidate_plan,
        observation,
    ) = _update_context(
        registry,
        manifest,
        output_path,
    )
    desired_file = _planned_file_for_path(
        candidate_plan,
        ".env",
    )
    desired_file.content = b"UPDATED=value\n"

    update_plan = build_project_update_plan(
        candidate_plan,
        current_state,
        observation,
    )
    execution_plan = _execution_plan(
        update_plan
    )

    assert [
        (
            planned_file.resource_id,
            planned_file.action,
            planned_file.relative_destination_path,
            planned_file.content,
        )
        for planned_file in execution_plan.files
    ] == [
        (
            desired_file.resource_id,
            "overwrite",
            ".env",
            b"UPDATED=value\n",
        )
    ]
    assert execution_plan.removals == []
    assert execution_plan.directories == []


def test_missing_resource_materializes_one_creation(
    registry,
    manifest,
    tmp_path,
):
    output_path = tmp_path / "output"
    generator = ProjectGenerator(registry)
    initial_plan = generator.plan(
        manifest=manifest,
        output_path=output_path,
    )
    generator.execute(initial_plan)

    storage = ProjectStateStorage(output_path)
    current_state = storage.read()

    assert current_state is not None

    (output_path / ".env").unlink()

    candidate_plan = generator.plan(
        manifest=manifest,
        output_path=output_path,
    )
    observation = observe_project(output_path)

    assert observation is not None

    update_plan = build_project_update_plan(
        candidate_plan,
        current_state,
        observation,
    )
    execution_plan = _execution_plan(
        update_plan
    )

    assert [
        (
            planned_file.action,
            planned_file.relative_destination_path,
        )
        for planned_file in execution_plan.files
    ] == [
        (
            "create",
            ".env",
        )
    ]
    assert execution_plan.removals == []


def test_removed_resource_materializes_exact_removal(
    registry,
    manifest,
    tmp_path,
):
    output_path = tmp_path / "output"
    (
        _,
        current_state,
        candidate_plan,
        observation,
    ) = _update_context(
        registry,
        manifest,
        output_path,
    )
    removed_file = _planned_file_for_path(
        candidate_plan,
        ".env",
    )
    candidate_plan.files = [
        planned_file
        for planned_file in candidate_plan.files
        if planned_file.resource_id
        != removed_file.resource_id
    ]

    update_plan = build_project_update_plan(
        candidate_plan,
        current_state,
        observation,
    )
    execution_plan = _execution_plan(
        update_plan
    )

    assert execution_plan.files == []
    assert [
        (
            removal.relative_path,
            removal.kind,
            removal.reason,
        )
        for removal in execution_plan.removals
    ] == [
        (
            ".env",
            "file",
            "replace",
        )
    ]
    assert (output_path / ".env").is_file()


def test_relocation_materializes_create_then_exact_removal(
    registry,
    manifest,
    tmp_path,
):
    output_path = tmp_path / "output"
    (
        _,
        current_state,
        candidate_plan,
        observation,
    ) = _update_context(
        registry,
        manifest,
        output_path,
    )
    desired_file = _planned_file_for_path(
        candidate_plan,
        ".env",
    )
    desired_file.destination_path = (
        output_path / ".env.production"
    )
    desired_file.relative_destination_path = (
        ".env.production"
    )

    update_plan = build_project_update_plan(
        candidate_plan,
        current_state,
        observation,
    )
    execution_plan = _execution_plan(
        update_plan
    )

    assert [
        (
            planned_file.action,
            planned_file.relative_destination_path,
        )
        for planned_file in execution_plan.files
    ] == [
        (
            "create",
            ".env.production",
        )
    ]
    assert [
        removal.relative_path
        for removal in execution_plan.removals
    ] == [
        ".env",
    ]
    assert (output_path / ".env").is_file()
    assert not (
        output_path / ".env.production"
    ).exists()


def test_nested_creation_materializes_parent_directories(
    registry,
    manifest,
    tmp_path,
):
    output_path = tmp_path / "output"
    (
        _,
        current_state,
        candidate_plan,
        observation,
    ) = _update_context(
        registry,
        manifest,
        output_path,
    )
    destination_path = (
        output_path
        / "custom"
        / "nested"
        / "notes.txt"
    )
    candidate_plan.files.append(
        PlannedFile(
            source_path=None,
            destination_path=destination_path,
            relative_destination_path=(
                "custom/nested/notes.txt"
            ),
            resource_id="core:notes",
            default_relative_path=(
                "custom/nested/notes.txt"
            ),
            operation="generate",
            action="create",
            content=b"generated notes",
        )
    )
    before = _snapshot_output(output_path)

    update_plan = build_project_update_plan(
        candidate_plan,
        current_state,
        observation,
    )
    execution_plan = _execution_plan(
        update_plan
    )

    assert [
        directory.relative_path
        for directory in execution_plan.directories
    ] == [
        "custom",
        "custom/nested",
    ]
    assert [
        planned_file.relative_destination_path
        for planned_file in execution_plan.files
    ] == [
        "custom/nested/notes.txt",
    ]
    assert _snapshot_output(output_path) == before


def test_occupied_parent_blocks_materialization(
    registry,
    manifest,
    tmp_path,
):
    output_path = tmp_path / "output"
    generator = ProjectGenerator(registry)
    initial_plan = generator.plan(
        manifest=manifest,
        output_path=output_path,
    )
    generator.execute(initial_plan)

    storage = ProjectStateStorage(output_path)
    current_state = storage.read()

    assert current_state is not None

    blocked_path = output_path / "blocked"
    blocked_path.write_bytes(b"user content")

    candidate_plan = generator.plan(
        manifest=manifest,
        output_path=output_path,
    )
    observation = observe_project(output_path)

    assert observation is not None

    candidate_plan.files.append(
        PlannedFile(
            source_path=None,
            destination_path=(
                blocked_path / "notes.txt"
            ),
            relative_destination_path=(
                "blocked/notes.txt"
            ),
            resource_id="core:notes",
            default_relative_path=(
                "blocked/notes.txt"
            ),
            operation="generate",
            action="create",
            content=b"generated notes",
        )
    )
    before = _snapshot_output(output_path)

    update_plan = build_project_update_plan(
        candidate_plan,
        current_state,
        observation,
    )

    assert update_plan.can_execute is False
    assert update_plan.execution_plan is None
    assert [
        conflict.to_dict()
        for conflict in update_plan.conflicts
    ] == [
        {
            "resource_id": "core:notes",
            "reason": "untracked_destination",
            "path": "blocked",
            "observed_status": None,
        }
    ]
    assert _snapshot_output(output_path) == before


def test_update_rejects_clean_candidate_plan(
    registry,
    manifest,
    tmp_path,
):
    output_path = tmp_path / "output"
    generator = ProjectGenerator(registry)
    initial_plan = generator.plan(
        manifest=manifest,
        output_path=output_path,
    )
    generator.execute(initial_plan)

    storage = ProjectStateStorage(output_path)
    current_state = storage.read()

    assert current_state is not None

    candidate_plan = generator.plan(
        manifest=manifest,
        output_path=output_path,
        clean=True,
    )
    observation = observe_project(output_path)

    assert observation is not None

    with pytest.raises(
        ValueError,
        match="clean generation plan",
    ):
        build_project_update_plan(
            candidate_plan,
            current_state,
            observation,
        )