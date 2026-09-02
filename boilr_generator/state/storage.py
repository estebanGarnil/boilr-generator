"""Transactional storage for generated project state."""

import os
from dataclasses import dataclass
from pathlib import Path

from boilr_generator.state.schemas import ProjectState
from boilr_generator.state.serialization import (
    deserialize_project_state,
    serialize_project_state,
)

STATE_DIRECTORY_NAME = ".boilr"
STATE_FILE_NAME = "state.json"
PENDING_STATE_FILE_NAME = "state.pending.json"


@dataclass(frozen=True, slots=True)
class ProjectStateStorage:
    """Read and transactionally persist one generated project state."""

    output_path: Path

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "output_path",
            Path(self.output_path),
        )

    @property
    def directory_path(self) -> Path:
        """Return the reserved Boilr metadata directory."""
        return self.output_path / STATE_DIRECTORY_NAME

    @property
    def state_path(self) -> Path:
        """Return the committed state path."""
        return self.directory_path / STATE_FILE_NAME

    @property
    def pending_state_path(self) -> Path:
        """Return the pending transaction path."""
        return (
            self.directory_path
            / PENDING_STATE_FILE_NAME
        )

    def read(self) -> ProjectState | None:
        """Read the committed state when it exists."""
        if not self.state_path.exists():
            return None

        return deserialize_project_state(
            self.state_path.read_bytes()
        )

    def read_pending(self) -> ProjectState | None:
        """Read the pending state when it exists."""
        if not self.pending_state_path.exists():
            return None

        return deserialize_project_state(
            self.pending_state_path.read_bytes()
        )

    def begin(self, state: ProjectState) -> Path:
        """Create the pending state without replacing an existing one."""
        self.directory_path.mkdir(
            parents=True,
            exist_ok=True,
        )

        payload = serialize_project_state(state)

        try:
            with self.pending_state_path.open("xb") as stream:
                stream.write(payload)
                stream.flush()
                os.fsync(stream.fileno())
        except FileExistsError as error:
            raise FileExistsError(
                "A project state transaction is already pending: "
                f"{self.pending_state_path}"
            ) from error

        return self.pending_state_path

    def commit(self, state: ProjectState) -> Path:
        """Atomically promote the matching pending state."""
        expected_payload = serialize_project_state(state)

        try:
            pending_payload = (
                self.pending_state_path.read_bytes()
            )
        except FileNotFoundError as error:
            raise FileNotFoundError(
                "No pending project state transaction exists: "
                f"{self.pending_state_path}"
            ) from error

        if pending_payload != expected_payload:
            raise ValueError(
                "The pending project state does not match "
                "the state being committed."
            )

        os.replace(
            self.pending_state_path,
            self.state_path,
        )

        return self.state_path