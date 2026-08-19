"""Plan and execution filesystem parity tests."""

from pathlib import Path, PurePosixPath

from boilr_generator.core.generation_plan import (
    GenerationPlan,
)
from boilr_generator.core.project import ResolvedProject
from boilr_generator.generation import ProjectGenerator

FilesystemEntry = tuple[
    str,
    bytes | str | None,
]
FilesystemSnapshot = dict[
    str,
    FilesystemEntry,
]


def snapshot_filesystem(
    root: Path,
) -> FilesystemSnapshot:
    """Capture filesystem structure and exact file contents."""
    if not root.exists():
        return {}

    paths = [
        root,
        *sorted(root.rglob("*")),
    ]
    snapshot: FilesystemSnapshot = {}

    for path in paths:
        relative_path = (
            "."
            if path == root
            else path.relative_to(root).as_posix()
        )

        if path.is_symlink():
            snapshot[relative_path] = (
                "symlink",
                str(path.readlink()),
            )
        elif path.is_dir():
            snapshot[relative_path] = (
                "directory",
                None,
            )
        else:
            snapshot[relative_path] = (
                "file",
                path.read_bytes(),
            )

    return snapshot


def parent_relative_path(
    relative_path: str,
) -> str:
    """Return the parent path used by a snapshot."""
    path = PurePosixPath(relative_path)

    if len(path.parts) == 1:
        return "."

    return path.parent.as_posix()


def simulate_plan(
    initial_state: FilesystemSnapshot,
    plan: GenerationPlan,
) -> FilesystemSnapshot:
    """Apply the declarative plan to an in-memory snapshot."""
    expected_state = dict(initial_state)

    for removal in plan.removals:
        relative_path = removal.relative_path

        assert relative_path in expected_state
        assert (
            expected_state[relative_path][0]
            == removal.kind
        )

        if removal.kind == "directory":
            if relative_path == ".":
                assert set(expected_state) == {"."}
            else:
                descendant_prefix = (
                    f"{relative_path}/"
                )
                assert not any(
                    path.startswith(
                        descendant_prefix
                    )
                    for path in expected_state
                )

        del expected_state[relative_path]

    for directory in plan.directories:
        relative_path = directory.relative_path

        assert relative_path not in expected_state

        if relative_path != ".":
            parent_path = parent_relative_path(
                relative_path
            )

            assert parent_path in expected_state
            assert (
                expected_state[parent_path][0]
                == "directory"
            )

        expected_state[relative_path] = (
            "directory",
            None,
        )

    for planned_file in plan.files:
        relative_path = (
            planned_file.relative_destination_path
        )

        if planned_file.action == "skip":
            continue

        parent_path = parent_relative_path(
            relative_path
        )

        assert parent_path in expected_state
        assert (
            expected_state[parent_path][0]
            == "directory"
        )

        if planned_file.action == "create":
            assert relative_path not in expected_state
        else:
            assert planned_file.action == "overwrite"
            assert relative_path in expected_state
            assert (
                expected_state[relative_path][0]
                == "file"
            )

        expected_state[relative_path] = (
            "file",
            planned_file.content,
        )

    return expected_state


def project_with_copy_strategy(
    resolved_project: ResolvedProject,
    strategy: str,
) -> ResolvedProject:
    """Return a project with one selected copy strategy."""
    project = resolved_project.model_copy(deep=True)
    django = project.get_module("django")

    assert django is not None
    assert django.manifest.sources.copy_sources

    copy_source = (
        django.manifest.sources.copy_sources[0]
    )
    django.manifest.sources.copy_sources[0] = (
        copy_source.model_copy(
            update={"strategy": strategy},
        )
    )

    return project


def test_missing_output_matches_create_plan(
    registry,
    manifest,
    tmp_path,
):
    output_path = tmp_path / "output"
    initial_state = snapshot_filesystem(
        output_path
    )
    generator = ProjectGenerator(registry)

    plan = generator.plan(
        manifest=manifest,
        output_path=output_path,
    )

    planned_files = {
        file.relative_destination_path: file
        for file in plan.files
    }

    assert initial_state == {}
    assert plan.directories
    assert plan.directories[0].relative_path == "."
    assert planned_files[".env"].action == "create"
    assert (
        planned_files["docker-compose.yml"].action
        == "create"
    )
    assert snapshot_filesystem(
        output_path
    ) == initial_state

    expected_state = simulate_plan(
        initial_state,
        plan,
    )

    generator.execute(plan)

    assert snapshot_filesystem(
        output_path
    ) == expected_state
    assert (
        output_path / ".env"
    ).read_bytes() == planned_files[".env"].content
    assert (
        output_path / "docker-compose.yml"
    ).read_bytes() == planned_files[
        "docker-compose.yml"
    ].content


def test_existing_output_matches_overwrite_and_skip_plan(
    registry,
    manifest,
    resolved_project,
    tmp_path,
    monkeypatch,
):
    output_path = tmp_path / "output"
    destination = output_path / "backend" / "apps"
    env_path = output_path / ".env"
    existing_path = destination / "existing.txt"

    destination.mkdir(parents=True)
    env_path.write_bytes(b"OLD=value\n")
    existing_path.write_bytes(b"keep")

    project = project_with_copy_strategy(
        resolved_project,
        "skip",
    )
    generator = ProjectGenerator(registry)

    monkeypatch.setattr(
        generator.resolver,
        "resolve",
        lambda _: project,
    )

    initial_state = snapshot_filesystem(
        output_path
    )
    plan = generator.plan(
        manifest=manifest,
        output_path=output_path,
    )

    env_file = next(
        file
        for file in plan.files
        if file.relative_destination_path == ".env"
    )
    skipped_files = [
        file
        for file in plan.files
        if file.relative_destination_path.startswith(
            "backend/apps/"
        )
    ]

    assert env_file.action == "overwrite"
    assert skipped_files
    assert all(
        file.action == "skip"
        for file in skipped_files
    )
    assert all(
        not removal.relative_path.startswith(
            "backend/apps"
        )
        for removal in plan.removals
    )
    assert snapshot_filesystem(
        output_path
    ) == initial_state

    expected_state = simulate_plan(
        initial_state,
        plan,
    )

    expected_writes = [
        (
            file.destination_path,
            file.content,
        )
        for file in plan.files
        if file.action != "skip"
    ]
    expected_chmods = [
        (
            file.destination_path,
            file.mode,
        )
        for file in plan.files
        if (
            file.action != "skip"
            and file.mode is not None
        )
    ]

    write_calls = []
    chmod_calls = []
    original_write_bytes = Path.write_bytes
    original_chmod = Path.chmod

    def track_write_bytes(
        path,
        content,
    ):
        write_calls.append(
            (path, content)
        )
        return original_write_bytes(
            path,
            content,
        )

    def track_chmod(
        path,
        mode,
        *args,
        **kwargs,
    ):
        chmod_calls.append(
            (path, mode)
        )
        return original_chmod(
            path,
            mode,
            *args,
            **kwargs,
        )

    monkeypatch.setattr(
        Path,
        "write_bytes",
        track_write_bytes,
    )
    monkeypatch.setattr(
        Path,
        "chmod",
        track_chmod,
    )

    generator.execute(plan)

    assert snapshot_filesystem(
        output_path
    ) == expected_state
    assert write_calls == expected_writes
    assert chmod_calls == expected_chmods
    assert existing_path.read_bytes() == b"keep"


def test_existing_output_matches_replace_plan(
    registry,
    manifest,
    resolved_project,
    tmp_path,
    monkeypatch,
):
    output_path = tmp_path / "output"
    destination = output_path / "backend" / "apps"
    nested_path = destination / "nested"
    root_file = destination / "old.txt"
    nested_file = nested_path / "nested.txt"

    nested_path.mkdir(parents=True)
    root_file.write_bytes(b"old")
    nested_file.write_bytes(b"nested")

    project = project_with_copy_strategy(
        resolved_project,
        "replace",
    )
    generator = ProjectGenerator(registry)

    monkeypatch.setattr(
        generator.resolver,
        "resolve",
        lambda _: project,
    )

    initial_state = snapshot_filesystem(
        output_path
    )
    plan = generator.plan(
        manifest=manifest,
        output_path=output_path,
    )

    expected_removals = {
        "backend/apps",
        "backend/apps/old.txt",
        "backend/apps/nested",
        "backend/apps/nested/nested.txt",
    }

    assert {
        removal.relative_path
        for removal in plan.removals
    } == expected_removals
    assert destination in {
        directory.path
        for directory in plan.directories
    }
    assert snapshot_filesystem(
        output_path
    ) == initial_state

    expected_state = simulate_plan(
        initial_state,
        plan,
    )

    generator.execute(plan)

    assert snapshot_filesystem(
        output_path
    ) == expected_state
    assert root_file.exists() is False
    assert nested_file.exists() is False


def test_existing_output_matches_clean_plan(
    registry,
    manifest,
    tmp_path,
):
    output_path = tmp_path / "output"
    nested_path = output_path / "old" / "nested"
    empty_path = output_path / "empty"
    old_file = nested_path / "old.bin"

    nested_path.mkdir(parents=True)
    empty_path.mkdir()
    old_file.write_bytes(b"\x00old\xff")

    initial_state = snapshot_filesystem(
        output_path
    )
    generator = ProjectGenerator(registry)

    plan = generator.plan(
        manifest=manifest,
        output_path=output_path,
        clean=True,
    )

    assert plan.clean_output is True
    assert {
        removal.relative_path
        for removal in plan.removals
    } == set(initial_state)
    assert snapshot_filesystem(
        output_path
    ) == initial_state

    expected_state = simulate_plan(
        initial_state,
        plan,
    )

    generator.execute(plan)

    assert snapshot_filesystem(
        output_path
    ) == expected_state
    assert old_file.exists() is False
    assert empty_path.exists() is False