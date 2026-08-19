from hashlib import sha256
from pathlib import Path

import pytest
from boilr_generator.generation.filesystem import (
    capture_output_state,
    capture_path_state,
    find_changed_output_paths,
)


def test_capture_output_state_reports_missing_output(
    tmp_path,
):
    output_path = tmp_path / "missing"

    states = capture_output_state(output_path)

    assert len(states) == 1

    state = states[0]

    assert state.path == output_path
    assert state.relative_path == "."
    assert state.exists is False
    assert state.kind is None
    assert state.content_size is None
    assert state.content_sha256 is None
    assert state.mode is None
    assert state.link_target is None
    assert output_path.exists() is False


def test_capture_output_state_captures_complete_tree(
    tmp_path,
):
    output_path = tmp_path / "output"
    empty_directory = output_path / "empty"
    nested_directory = output_path / "nested"
    binary_file = nested_directory / "data.bin"
    content = b"\x00boilr\xffcontent"

    empty_directory.mkdir(parents=True)
    nested_directory.mkdir()
    binary_file.write_bytes(content)

    before_paths = {
        path.relative_to(output_path).as_posix()
        for path in output_path.rglob("*")
    }
    before_content = binary_file.read_bytes()
    before_mode = binary_file.lstat().st_mode & 0o777

    states = capture_output_state(output_path)

    after_paths = {
        path.relative_to(output_path).as_posix()
        for path in output_path.rglob("*")
    }

    assert [
        state.relative_path
        for state in states
    ] == [
        ".",
        "empty",
        "nested",
        "nested/data.bin",
    ]

    state_by_path = {
        state.relative_path: state
        for state in states
    }

    root_state = state_by_path["."]
    empty_state = state_by_path["empty"]
    file_state = state_by_path["nested/data.bin"]

    assert root_state.kind == "directory"
    assert empty_state.kind == "directory"
    assert empty_state.content_size is None
    assert empty_state.content_sha256 is None

    assert file_state.exists is True
    assert file_state.kind == "file"
    assert file_state.content_size == len(content)
    assert file_state.content_sha256 == sha256(
        content
    ).hexdigest()
    assert file_state.mode == before_mode

    assert after_paths == before_paths
    assert binary_file.read_bytes() == before_content
    assert empty_directory.exists() is True


def test_capture_path_state_captures_file_output(
    tmp_path,
):
    output_path = tmp_path / "output.bin"
    content = b"file used as output"
    output_path.write_bytes(content)

    state = capture_path_state(
        output_path,
        output_path,
    )

    assert state.path == output_path
    assert state.relative_path == "."
    assert state.exists is True
    assert state.kind == "file"
    assert state.content_size == len(content)
    assert state.content_sha256 == sha256(
        content
    ).hexdigest()


def test_capture_output_state_does_not_follow_symbolic_links(
    tmp_path,
):
    output_path = tmp_path / "output"
    outside_directory = tmp_path / "outside"
    linked_directory = output_path / "linked"

    output_path.mkdir()
    outside_directory.mkdir()
    outside_file = outside_directory / "protected.txt"
    outside_file.write_text(
        "protected",
        encoding="utf-8",
    )

    try:
        linked_directory.symlink_to(
            outside_directory,
            target_is_directory=True,
        )
    except (NotImplementedError, OSError):
        pytest.skip(
            "Symbolic links are not available on this system."
        )

    states = capture_output_state(output_path)

    assert [
        state.relative_path
        for state in states
    ] == [
        ".",
        "linked",
    ]

    link_state = states[1]

    assert link_state.kind == "symlink"
    assert link_state.link_target is not None
    assert Path(link_state.link_target) == (
        outside_directory
    )
    assert outside_file.read_text(
        encoding="utf-8"
    ) == "protected"

def test_find_changed_output_paths_returns_empty_for_same_state(
    tmp_path,
):
    output_path = tmp_path / "output"
    output_path.mkdir()
    (output_path / "file.txt").write_text(
        "content",
        encoding="utf-8",
    )

    expected_state = capture_output_state(
        output_path
    )
    actual_state = capture_output_state(
        output_path
    )

    assert find_changed_output_paths(
        expected_state,
        actual_state,
    ) == []


def test_find_changed_output_paths_reports_all_changes(
    tmp_path,
):
    output_path = tmp_path / "output"
    output_path.mkdir()

    changed_path = output_path / "changed.txt"
    removed_path = output_path / "removed.txt"
    type_path = output_path / "type-change"

    changed_path.write_text(
        "before",
        encoding="utf-8",
    )
    removed_path.write_text(
        "removed",
        encoding="utf-8",
    )
    type_path.write_text(
        "file",
        encoding="utf-8",
    )

    expected_state = capture_output_state(
        output_path
    )

    changed_path.write_text(
        "after",
        encoding="utf-8",
    )
    removed_path.unlink()
    type_path.unlink()
    type_path.mkdir()
    (output_path / "added.txt").write_text(
        "added",
        encoding="utf-8",
    )

    actual_state = capture_output_state(
        output_path
    )

    assert find_changed_output_paths(
        expected_state,
        actual_state,
    ) == [
        "added.txt",
        "changed.txt",
        "removed.txt",
        "type-change",
    ]