import boilr_generator.generation as generation_api
from boilr_generator.generation import (
    ProjectGenerator,
    observe_project,
)
from boilr_generator.generation.filesystem import (
    capture_output_state,
)
from boilr_generator.state import (
    ProjectStateStorage,
    classify_tracked_resources,
)


def _generate_project(
    registry,
    manifest,
    output_path,
):
    generator = ProjectGenerator(registry)
    plan = generator.plan(
        manifest=manifest,
        output_path=output_path,
    )

    assert plan.desired_state is not None

    generator.execute(plan)

    return plan


def test_generation_api_exports_project_observer():
    assert generation_api.observe_project is observe_project
    assert (
        observe_project.__module__
        == "boilr_generator.generation.observation"
    )


def test_observe_project_is_read_only_without_state(
    tmp_path,
):
    output_path = tmp_path / "output"
    user_file = output_path / "user.txt"

    output_path.mkdir()
    user_file.write_bytes(b"user content")

    before = capture_output_state(output_path)

    observation = observe_project(output_path)

    after = capture_output_state(output_path)

    assert observation is None
    assert after == before
    assert user_file.read_bytes() == b"user content"
    assert not (output_path / ".boilr").exists()


def test_observe_project_uses_committed_state(
    registry,
    manifest,
    tmp_path,
):
    output_path = tmp_path / "output"

    plan = _generate_project(
        registry,
        manifest,
        output_path,
    )

    storage = ProjectStateStorage(output_path)
    stored_state = storage.read()

    assert stored_state is not None
    assert stored_state == plan.desired_state

    state_bytes_before = storage.state_path.read_bytes()

    expected = classify_tracked_resources(
        stored_state,
        capture_output_state(output_path),
    )
    actual = observe_project(output_path)

    assert actual == expected
    assert storage.state_path.read_bytes() == (
        state_bytes_before
    )
    assert not storage.pending_state_path.exists()


def test_observe_project_keeps_committed_baseline_when_pending(
    registry,
    manifest,
    tmp_path,
):
    output_path = tmp_path / "output"

    _generate_project(
        registry,
        manifest,
        output_path,
    )

    storage = ProjectStateStorage(output_path)
    committed_state = storage.read()

    assert committed_state is not None
    assert committed_state.resources

    first_resource = committed_state.resources[0]
    pending_resource = first_resource.model_copy(
        update={
            "materialized_path": "pending-only.txt",
        }
    )
    pending_state = committed_state.model_copy(
        update={
            "resources": (
                pending_resource,
                *committed_state.resources[1:],
            ),
        }
    )

    storage.begin(pending_state)

    observed_state = capture_output_state(output_path)

    committed_observation = classify_tracked_resources(
        committed_state,
        observed_state,
    )
    pending_observation = classify_tracked_resources(
        pending_state,
        observed_state,
    )

    actual = observe_project(output_path)

    assert committed_observation != pending_observation
    assert actual == committed_observation
    assert storage.read_pending() == pending_state
    assert storage.pending_state_path.is_file()