"""End-to-end generated-project lifecycle tests."""

from pathlib import Path

from boilr_generator.generation import (
    ProjectGenerator,
    build_project_update_plan,
    observe_project,
)
from boilr_generator.manifest.schemas import (
    ProjectManifest,
)
from boilr_generator.state import (
    ProjectState,
    ProjectStateStorage,
)


def _manifest_with_modules(
    manifest: ProjectManifest,
    module_keys: set[str],
) -> ProjectManifest:
    data = manifest.model_dump(mode="python")
    data["modules"] = [
        module
        for module in data["modules"]
        if module["key"] in module_keys
    ]

    assert {
        module["key"]
        for module in data["modules"]
    } == module_keys

    return ProjectManifest.model_validate(data)


def _manifest_with_database_port(
    manifest: ProjectManifest,
    port: int,
) -> ProjectManifest:
    data = manifest.model_dump(mode="python")

    postgres = next(
        module
        for module in data["modules"]
        if module["key"] == "postgres"
    )
    postgres["variables"]["db_port"] = port

    return ProjectManifest.model_validate(data)


def _read_committed_state(
    storage: ProjectStateStorage,
) -> ProjectState:
    state = storage.read()

    assert state is not None
    assert storage.read_pending() is None
    assert not storage.pending_state_path.exists()

    return state


def _build_update(
    *,
    generator: ProjectGenerator,
    manifest: ProjectManifest,
    output_path: Path,
):
    storage = ProjectStateStorage(output_path)
    current_state = _read_committed_state(storage)

    candidate_plan = generator.plan(
        manifest=manifest,
        output_path=output_path,
    )

    assert candidate_plan.desired_state is not None

    observation = observe_project(output_path)

    assert observation is not None

    return build_project_update_plan(
        candidate_plan,
        current_state,
        observation,
    )


def _assert_clean_project(
    output_path: Path,
) -> None:
    observation = observe_project(output_path)

    assert observation is not None
    assert observation.has_drift is False
    assert observation.untracked == ()
    assert {
        resource.status
        for resource in observation.resources
    } == {"unchanged"}


def test_complete_module_lifecycle_round_trip(
    registry,
    manifest,
    tmp_path,
):
    output_path = tmp_path / "output"
    generator = ProjectGenerator(registry)
    storage = ProjectStateStorage(output_path)

    postgres_manifest = _manifest_with_modules(
        manifest,
        {"postgres"},
    )

    initial_plan = generator.plan(
        manifest=postgres_manifest,
        output_path=output_path,
    )
    generator.execute(initial_plan)

    initial_state = _read_committed_state(storage)

    assert tuple(
        module.key
        for module in initial_state.modules
    ) == ("postgres",)

    _assert_clean_project(output_path)

    add_plan = _build_update(
        generator=generator,
        manifest=manifest,
        output_path=output_path,
    )

    assert add_plan.can_execute is True
    assert {
        transition["module_key"]:
            transition["action"]
        for transition in add_plan.to_dict()[
            "module_transitions"
        ]["modules"]
    } == {
        "django": "add",
        "django-postgres": "add",
        "postgres": "retain",
    }

    generator.execute_update(add_plan)

    added_state = _read_committed_state(storage)

    assert added_state == add_plan.desired_state
    assert tuple(
        module.key
        for module in added_state.modules
    ) == (
        "django",
        "django-postgres",
        "postgres",
    )

    _assert_clean_project(output_path)

    updated_manifest = (
        _manifest_with_database_port(
            manifest,
            55432,
        )
    )
    content_update_plan = _build_update(
        generator=generator,
        manifest=updated_manifest,
        output_path=output_path,
    )

    assert content_update_plan.can_execute is True
    assert (
        content_update_plan
        .has_filesystem_changes
        is True
    )

    generator.execute_update(
        content_update_plan
    )

    updated_state = _read_committed_state(storage)

    assert (
        updated_state
        == content_update_plan.desired_state
    )
    assert b"DB_PORT=55432" in (
        output_path / ".env"
    ).read_bytes()

    _assert_clean_project(output_path)

    reduced_manifest = _manifest_with_modules(
        updated_manifest,
        {"postgres"},
    )
    remove_plan = _build_update(
        generator=generator,
        manifest=reduced_manifest,
        output_path=output_path,
    )

    assert remove_plan.can_execute is True
    assert {
        transition["module_key"]:
            transition["action"]
        for transition in remove_plan.to_dict()[
            "module_transitions"
        ]["modules"]
    } == {
        "django": "remove",
        "django-postgres": "remove",
        "postgres": "retain",
    }

    previous_resources = {
        resource.id: resource
        for resource in updated_state.resources
    }
    desired_resource_ids = {
        resource.id
        for resource in remove_plan.desired_state.resources
    }
    removed_resources = [
        resource
        for resource_id, resource
        in previous_resources.items()
        if resource_id not in desired_resource_ids
    ]

    generator.execute_update(remove_plan)

    reduced_state = _read_committed_state(storage)

    assert reduced_state == remove_plan.desired_state
    assert tuple(
        module.key
        for module in reduced_state.modules
    ) == ("postgres",)

    for resource in removed_resources:
        assert not (
            output_path
            / resource.materialized_path
        ).exists()

    _assert_clean_project(output_path)


def test_module_removal_preserves_untracked_files(
    registry,
    manifest,
    tmp_path,
):
    output_path = tmp_path / "output"
    generator = ProjectGenerator(registry)
    storage = ProjectStateStorage(output_path)

    initial_plan = generator.plan(
        manifest=manifest,
        output_path=output_path,
    )
    generator.execute(initial_plan)

    user_path = (
        output_path
        / "backend"
        / "apps"
        / "user_created.py"
    )
    user_content = b'print("user owned")\n'
    user_path.write_bytes(user_content)

    postgres_manifest = _manifest_with_modules(
        manifest,
        {"postgres"},
    )
    remove_plan = _build_update(
        generator=generator,
        manifest=postgres_manifest,
        output_path=output_path,
    )

    assert remove_plan.can_execute is True

    generator.execute_update(remove_plan)

    assert user_path.read_bytes() == user_content

    state = _read_committed_state(storage)

    assert tuple(
        module.key
        for module in state.modules
    ) == ("postgres",)

    observation = observe_project(output_path)

    assert observation is not None
    assert any(
        resource.path
        == "backend/apps/user_created.py"
        for resource in observation.untracked
    )
    assert all(
        resource.status == "unchanged"
        for resource in observation.resources
    )