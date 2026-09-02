from copy import deepcopy

import pytest

from boilr_generator.core.generation_plan import PlannedFile
from boilr_generator.state import (
    build_initial_project_state,
    fingerprint_model,
    serialize_project_state,
)


def _planned_file(
    tmp_path,
    *,
    resource_id="module:django:render:requirements",
    relative_path="backend/requirements.txt",
    action="create",
    module="django",
    contributors=None,
    content=b"Django>=5.0,<6.0\n",
    mode=0o644,
):
    if contributors is None:
        contributors = ["django"]

    return PlannedFile(
        source_path=None,
        destination_path=tmp_path / relative_path,
        relative_destination_path=relative_path,
        resource_id=resource_id,
        default_relative_path=relative_path,
        operation="render",
        action=action,
        content=content,
        module=module,
        contributors=contributors,
        mode=mode,
    )


def test_build_initial_state_records_project_modules_and_bindings(
    manifest,
    resolved_project,
):
    state = build_initial_project_state(
        manifest=manifest,
        resolved_project=resolved_project,
        files=(),
        generator_version="0.1.0",
    )

    assert state.schema_version == 1
    assert state.generator_version == "0.1.0"
    assert state.project.name == manifest.project.name
    assert state.project.type == manifest.project.type
    assert state.project.version == manifest.project.version
    assert state.project.manifest_sha256 == fingerprint_model(
        manifest
    )

    assert [module.key for module in state.modules] == sorted(
        resolved_project.list_module_keys()
    )

    state_modules = {
        module.key: module
        for module in state.modules
    }

    for resolved_module in resolved_project.modules:
        state_module = state_modules[resolved_module.key]

        assert state_module.version == (
            resolved_module.manifest.meta.version
        )
        assert state_module.origin == "builtin"
        assert state_module.manifest_sha256 == fingerprint_model(
            resolved_module.manifest
        )
        assert state_module.destination == (
            resolved_module.manifest.assembly.destination_root
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
        for binding in resolved_project.bindings
    )


def test_build_initial_state_records_managed_file_resources(
    manifest,
    resolved_project,
    tmp_path,
):
    planned_file = _planned_file(
        tmp_path,
        contributors=[
            "django-postgres",
            "django",
        ],
    )

    state = build_initial_project_state(
        manifest=manifest,
        resolved_project=resolved_project,
        files=(planned_file,),
        generator_version="0.1.0",
    )

    assert len(state.resources) == 1

    resource = state.resources[0]

    assert resource.id == planned_file.resource_id
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
    assert resource.owner == "django"
    assert resource.contributors == (
        "django",
        "django-postgres",
    )
    assert resource.content_size == planned_file.content_size
    assert resource.content_sha256 == (
        planned_file.content_sha256
    )
    assert resource.mode == 0o644
    assert resource.link_target is None


def test_build_initial_state_does_not_adopt_skipped_files(
    manifest,
    resolved_project,
    tmp_path,
):
    created_file = _planned_file(tmp_path)
    skipped_file = _planned_file(
        tmp_path,
        resource_id="module:django:copy:apps:user.py",
        relative_path="backend/apps/user.py",
        action="skip",
        content=b"user content\n",
    )

    state = build_initial_project_state(
        manifest=manifest,
        resolved_project=resolved_project,
        files=(skipped_file, created_file),
        generator_version="0.1.0",
    )

    assert [resource.id for resource in state.resources] == [
        created_file.resource_id,
    ]

def test_build_initial_state_is_deterministic(
    manifest,
    resolved_project,
    tmp_path,
):
    first_file = _planned_file(tmp_path)
    second_file = _planned_file(
        tmp_path,
        resource_id="core:environment",
        relative_path=".env",
        module=None,
        contributors=[
            "postgres",
            "django",
        ],
        content=b"DB_HOST=db\n",
        mode=None,
    )

    first_state = build_initial_project_state(
        manifest=manifest,
        resolved_project=resolved_project,
        files=(first_file, second_file),
        generator_version="0.1.0",
    )

    reordered_project = resolved_project.model_copy(
        update={
            "modules": list(
                reversed(resolved_project.modules)
            ),
            "bindings": list(
                reversed(resolved_project.bindings)
            ),
        }
    )

    second_state = build_initial_project_state(
        manifest=manifest,
        resolved_project=reordered_project,
        files=(second_file, first_file),
        generator_version="0.1.0",
    )

    assert first_state == second_state
    assert serialize_project_state(first_state) == (
        serialize_project_state(second_state)
    )


def test_build_initial_state_does_not_store_manifest_values(
    manifest,
    resolved_project,
):
    manifest_with_secrets = manifest.model_copy(deep=True)
    manifest_with_secrets.modules[0].variables[
        "private_value"
    ] = "must-not-be-stored"

    state = build_initial_project_state(
        manifest=manifest_with_secrets,
        resolved_project=resolved_project,
        files=(),
        generator_version="0.1.0",
    )

    serialized = serialize_project_state(state)

    assert b"must-not-be-stored" not in serialized
    assert b"dev-secret" not in serialized
    assert b"password" not in serialized


def test_build_initial_state_rejects_mismatched_project(
    manifest,
    resolved_project,
):
    mismatched_manifest = manifest.model_copy(deep=True)
    mismatched_manifest.project.name = "another-project"

    with pytest.raises(
        ValueError,
        match=(
            "project manifest and resolved project do not match"
        ),
    ):
        build_initial_project_state(
            manifest=mismatched_manifest,
            resolved_project=resolved_project,
            files=(),
            generator_version="0.1.0",
        )


def test_build_initial_state_rejects_unknown_file_action(
    manifest,
    resolved_project,
    tmp_path,
):
    planned_file = _planned_file(tmp_path)
    invalid_file = deepcopy(planned_file)
    invalid_file.action = "merge"

    with pytest.raises(
        ValueError,
        match="Unsupported planned file actions: merge",
    ):
        build_initial_project_state(
            manifest=manifest,
            resolved_project=resolved_project,
            files=(invalid_file,),
            generator_version="0.1.0",
        )