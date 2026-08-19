"""Filesystem state capture for generation plans."""

import stat
from hashlib import sha256
from pathlib import Path

from boilr_generator.core.generation_plan import (
    PlannedPathState,
)
from boilr_generator.exceptions import (
    UnsupportedFilesystemEntryError,
)

_HASH_CHUNK_SIZE = 1024 * 1024


def _relative_path(
    path: Path,
    output_path: Path,
) -> str:
    """Return one portable path relative to the output."""
    if path == output_path:
        return "."

    return path.relative_to(output_path).as_posix()


def _hash_file(path: Path) -> str:
    """Calculate one file SHA-256 without loading it entirely."""
    digest = sha256()

    with path.open("rb") as file:
        while True:
            chunk = file.read(_HASH_CHUNK_SIZE)

            if not chunk:
                break

            digest.update(chunk)

    return digest.hexdigest()


def capture_path_state(
    path: Path,
    output_path: Path,
) -> PlannedPathState:
    """Capture the current state of one filesystem path."""
    relative_path = _relative_path(
        path,
        output_path,
    )

    try:
        path_stat = path.lstat()
    except FileNotFoundError:
        return PlannedPathState(
            path=path,
            relative_path=relative_path,
            exists=False,
        )

    mode = stat.S_IMODE(path_stat.st_mode)

    if stat.S_ISLNK(path_stat.st_mode):
        return PlannedPathState(
            path=path,
            relative_path=relative_path,
            exists=True,
            kind="symlink",
            mode=mode,
            link_target=str(path.readlink()),
        )

    if stat.S_ISDIR(path_stat.st_mode):
        return PlannedPathState(
            path=path,
            relative_path=relative_path,
            exists=True,
            kind="directory",
            mode=mode,
        )

    if stat.S_ISREG(path_stat.st_mode):
        return PlannedPathState(
            path=path,
            relative_path=relative_path,
            exists=True,
            kind="file",
            content_size=path_stat.st_size,
            content_sha256=_hash_file(path),
            mode=mode,
        )

    raise UnsupportedFilesystemEntryError(
        f"Unsupported filesystem path type: '{path}'.",
        field_path="generation.output_path",
        context={
            "path": str(path),
            "relative_path": relative_path,
            "st_mode": path_stat.st_mode,
        },
        suggestion=(
            "Remove the unsupported filesystem entry or "
            "replace it with a regular file, directory, "
            "or symbolic link."
        ),
    )


def _capture_directory_entries(
    directory: Path,
    output_path: Path,
) -> list[PlannedPathState]:
    """Capture directory entries without following links."""
    states: list[PlannedPathState] = []

    entries = sorted(
        directory.iterdir(),
        key=lambda entry: entry.name,
    )

    for entry in entries:
        state = capture_path_state(
            entry,
            output_path,
        )
        states.append(state)

        if state.kind == "directory":
            states.extend(
                _capture_directory_entries(
                    entry,
                    output_path,
                )
            )

    return states


def capture_output_state(
    output_path: Path,
) -> list[PlannedPathState]:
    """Capture the complete current output tree."""
    root_state = capture_path_state(
        output_path,
        output_path,
    )
    states = [root_state]

    if root_state.kind != "directory":
        return states

    states.extend(
        _capture_directory_entries(
            output_path,
            output_path,
        )
    )

    return states

def find_changed_output_paths(
    expected_state: list[PlannedPathState],
    actual_state: list[PlannedPathState],
) -> list[str]:
    """Return paths whose captured state differs."""
    expected_by_path = {
        state.relative_path: state
        for state in expected_state
    }
    actual_by_path = {
        state.relative_path: state
        for state in actual_state
    }

    all_relative_paths = (
        set(expected_by_path)
        | set(actual_by_path)
    )

    return [
        relative_path
        for relative_path in sorted(
            all_relative_paths
        )
        if expected_by_path.get(relative_path)
        != actual_by_path.get(relative_path)
    ]