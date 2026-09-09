from boilr_generator.generation.project import ProjectGenerator


def _resource_metadata(plan):
    return sorted(
        (
            planned_file.relative_destination_path,
            planned_file.resource_id,
            planned_file.default_relative_path,
        )
        for planned_file in plan.files
    )


def test_generation_plan_resource_identities_are_stable_across_outputs(
    registry,
    manifest,
    tmp_path,
):
    generator = ProjectGenerator(registry)
    first_output = tmp_path / "first-output"
    second_output = tmp_path / "second-output"

    first_plan = generator.plan(
        manifest=manifest,
        output_path=first_output,
    )
    second_plan = generator.plan(
        manifest=manifest,
        output_path=second_output,
    )

    assert first_plan.output_path != second_plan.output_path
    assert {
        planned_file.destination_path
        for planned_file in first_plan.files
    }.isdisjoint(
        planned_file.destination_path
        for planned_file in second_plan.files
    )
    assert _resource_metadata(first_plan) == (
        _resource_metadata(second_plan)
    )

    resource_ids = [
        planned_file.resource_id
        for planned_file in first_plan.files
    ]

    assert len(resource_ids) == len(set(resource_ids))
    assert all(
        planned_file.default_relative_path
        == planned_file.relative_destination_path
        for planned_file in first_plan.files
    )


def test_generation_plan_uses_stable_source_declaration_ids(
    registry,
    manifest,
    tmp_path,
):
    plan = ProjectGenerator(registry).plan(
        manifest=manifest,
        output_path=tmp_path / "output",
    )

    resource_ids = {
        planned_file.resource_id
        for planned_file in plan.files
    }

    assert {
        "core:docker-compose",
        "core:environment",
        "module:django:render:manage",
        "module:django:render:dockerfile",
        "module:django:render:requirements",
        "module:django:render:settings-base",
    } <= resource_ids
    assert any(
        resource_id.startswith(
            "module:django:copy:apps:"
        )
        for resource_id in resource_ids
    )
    assert any(
        resource_id.startswith(
            "module:django:copy:config:"
        )
        for resource_id in resource_ids
    )
