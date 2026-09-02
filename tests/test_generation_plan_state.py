from importlib.metadata import version

from boilr_generator.generation.project import ProjectGenerator
from boilr_generator.state import (
    fingerprint_model,
    serialize_project_state,
)


def test_project_generator_plan_builds_desired_state(
    registry,
    manifest,
    tmp_path,
):
    output_path = tmp_path / "generated"

    plan = ProjectGenerator(registry).plan(
        manifest,
        output_path,
    )

    state = plan.desired_state

    assert state is not None
    assert state.schema_version == 1
    assert state.generator_version == version("boilr")
    assert state.project.name == manifest.project.name
    assert state.project.type == manifest.project.type
    assert state.project.version == manifest.project.version
    assert state.project.manifest_sha256 == fingerprint_model(
        manifest
    )

    assert [module.key for module in state.modules] == sorted(
        plan.resolved_project.list_module_keys()
    )

    assert [
        (
            binding.consumer_module,
            binding.binding,
            binding.capability,
            binding.provider_module,
        )
        for binding in state.bindings
    ] == sorted(
        (
            binding.consumer_module_key,
            binding.binding_key,
            binding.capability,
            binding.provider_module_key,
        )
        for binding in plan.resolved_project.bindings
    )

    managed_files = {
        planned_file.resource_id: planned_file
        for planned_file in plan.files
        if planned_file.action != "skip"
    }

    state_resources = {
        resource.id: resource
        for resource in state.resources
    }

    assert set(state_resources) == set(managed_files)

    for resource_id, planned_file in managed_files.items():
        resource = state_resources[resource_id]

        assert resource.kind == "file"
        assert resource.default_path == (
            planned_file.default_relative_path
        )
        assert resource.desired_path == (
            planned_file.relative_destination_path
        )
        assert resource.materialized_path == (
            planned_file.relative_destination_path
        )
        assert resource.management == "generated"
        assert resource.scope == "shared"
        assert resource.owner == planned_file.owner
        assert resource.contributors == tuple(
            planned_file.contributors
        )
        assert resource.content_size == (
            planned_file.content_size
        )
        assert resource.content_sha256 == (
            planned_file.content_sha256
        )
        assert resource.mode == planned_file.mode
        assert resource.link_target is None

    assert plan.to_dict()["desired_state"] == (
        state.model_dump(mode="json")
    )


def test_project_generator_plan_state_contains_no_secrets(
    registry,
    manifest,
    tmp_path,
):
    plan = ProjectGenerator(registry).plan(
        manifest,
        tmp_path / "generated",
    )

    assert plan.desired_state is not None

    serialized_state = serialize_project_state(
        plan.desired_state
    )

    assert b"dev-secret" not in serialized_state
    assert b"password" not in serialized_state
    assert b"DJANGO_SECRET_KEY" not in serialized_state
    assert b"DB_PASSWORD" not in serialized_state


def test_project_generator_plan_does_not_write_state_files(
    registry,
    manifest,
    tmp_path,
):
    output_path = tmp_path / "generated"

    plan = ProjectGenerator(registry).plan(
        manifest,
        output_path,
    )

    assert plan.desired_state is not None
    assert output_path.exists() is False
    assert (output_path / ".boilr").exists() is False
    assert (
        output_path / ".boilr" / "state.json"
    ).exists() is False
    assert (
        output_path / ".boilr" / "state.pending.json"
    ).exists() is False