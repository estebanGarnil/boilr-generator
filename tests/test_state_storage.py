import os

import pytest

from boilr_generator.state.schemas import (
    ProjectState,
    StateModule,
    StateProject,
)
from boilr_generator.state.serialization import (
    serialize_project_state,
)
from boilr_generator.state.storage import (
    ProjectStateStorage,
)

FINGERPRINT = "a" * 64


def make_state(
    *,
    project_name: str = "my_app",
) -> ProjectState:
    return ProjectState(
        schema_version=1,
        generator_version="0.1.0",
        project=StateProject(
            name=project_name,
            type="fullstack_web",
            version="1.0.0",
            manifest_sha256=FINGERPRINT,
        ),
        modules=(
            StateModule(
                key="django",
                version="1.0.0",
                origin="builtin",
                manifest_sha256=FINGERPRINT,
                destination="backend",
            ),
        ),
        bindings=(),
        resources=(),
    )


def test_storage_uses_reserved_project_paths(
    tmp_path,
):
    output_path = tmp_path / "project"
    storage = ProjectStateStorage(output_path)

    assert storage.output_path == output_path
    assert storage.directory_path == (
        output_path / ".boilr"
    )
    assert storage.state_path == (
        output_path / ".boilr" / "state.json"
    )
    assert storage.pending_state_path == (
        output_path
        / ".boilr"
        / "state.pending.json"
    )
    assert storage.read() is None
    assert storage.read_pending() is None


def test_begin_writes_complete_pending_state(
    tmp_path,
):
    storage = ProjectStateStorage(
        tmp_path / "project"
    )
    state = make_state()

    pending_path = storage.begin(state)

    assert pending_path == storage.pending_state_path
    assert pending_path.is_file()
    assert not storage.state_path.exists()
    assert pending_path.read_bytes() == (
        serialize_project_state(state)
    )
    assert storage.read_pending() == state


def test_begin_refuses_existing_pending_state(
    tmp_path,
):
    storage = ProjectStateStorage(
        tmp_path / "project"
    )
    state = make_state()

    storage.begin(state)

    with pytest.raises(
        FileExistsError,
        match="already pending",
    ):
        storage.begin(state)

    assert storage.read_pending() == state
    assert not storage.state_path.exists()


def test_commit_promotes_pending_state(
    tmp_path,
):
    storage = ProjectStateStorage(
        tmp_path / "project"
    )
    state = make_state()

    storage.begin(state)
    state_path = storage.commit(state)

    assert state_path == storage.state_path
    assert state_path.is_file()
    assert not storage.pending_state_path.exists()
    assert storage.read() == state


def test_commit_requires_pending_state(
    tmp_path,
):
    storage = ProjectStateStorage(
        tmp_path / "project"
    )

    with pytest.raises(
        FileNotFoundError,
        match="No pending project state",
    ):
        storage.commit(make_state())

    assert storage.read() is None


def test_commit_rejects_different_state(
    tmp_path,
):
    storage = ProjectStateStorage(
        tmp_path / "project"
    )
    pending_state = make_state(
        project_name="first_project",
    )
    different_state = make_state(
        project_name="second_project",
    )

    storage.begin(pending_state)

    with pytest.raises(
        ValueError,
        match="does not match",
    ):
        storage.commit(different_state)

    assert storage.read() is None
    assert storage.read_pending() == pending_state


def test_commit_can_replace_existing_state(
    tmp_path,
):
    storage = ProjectStateStorage(
        tmp_path / "project"
    )
    previous_state = make_state(
        project_name="previous_project",
    )
    next_state = make_state(
        project_name="next_project",
    )

    storage.begin(previous_state)
    storage.commit(previous_state)

    storage.begin(next_state)
    storage.commit(next_state)

    assert storage.read() == next_state
    assert storage.read_pending() is None


def test_failed_commit_preserves_previous_and_pending_states(
    tmp_path,
    monkeypatch,
):
    storage = ProjectStateStorage(
        tmp_path / "project"
    )
    previous_state = make_state(
        project_name="previous_project",
    )
    next_state = make_state(
        project_name="next_project",
    )

    storage.begin(previous_state)
    storage.commit(previous_state)
    storage.begin(next_state)

    def fail_replace(
        source: os.PathLike[str] | str,
        destination: os.PathLike[str] | str,
    ) -> None:
        raise OSError("simulated replacement failure")

    monkeypatch.setattr(
        "boilr_generator.state.storage.os.replace",
        fail_replace,
    )

    with pytest.raises(
        OSError,
        match="simulated replacement failure",
    ):
        storage.commit(next_state)

    assert storage.read() == previous_state
    assert storage.read_pending() == next_state