"""Filesystem state capture for generation plans."""

import stat
from hashlib import sha256
from pathlib import Path

from boilr_generator.core.generation_plan import (
    PlannedPathState,
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

    raise ValueError(
        f"Unsupported filesystem path type: '{path}'."
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