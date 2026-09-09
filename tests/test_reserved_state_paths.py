import pytest

from boilr_generator.exceptions import UnsafePathError
from boilr_generator.generation import ProjectGenerator
from boilr_generator.generation.filesystem import (
    capture_output_state,
)
from boilr_generator.state.serialization import (
    serialize_project_state,
)


@pytest.mark.parametrize(
    "reserved_name",
    [
        ".boilr",
        ".BOILR",
    ],
)
def test_capture_ignores_root_boilr_metadata(
    tmp_path,
    reserved_name,
):
    output_path = tmp_path / "project"
    metadata_path = output_path / reserved_name
    source_path = output_path / "src"
    nested_user_path = source_path / ".boilr"

    metadata_path.mkdir(parents=True)
    source_path.mkdir()
    nested_user_path.mkdir()

    (metadata_path / "state.json").write_text(
        "internal",
        encoding="utf-8",
    )
    (source_path / "app.py").write_text(
        "print('app')",
        encoding="utf-8",
    )
    (nested_user_path / "user.txt").write_text(
        "user content",
        encoding="utf-8",
    )

    states = capture_output_state(output_path)

    assert [
        state.relative_path
        for state in states
    ] == [
        ".",
        "src",
        "src/.boilr",
        "src/.boilr/user.txt",
        "src/app.py",
    ]


def test_clean_plan_preserves_boilr_metadata(
    registry,
    manifest,
    tmp_path,
):
    output_path = tmp_path / "project"
    generator = ProjectGenerator(registry)

    baseline_plan = generator.plan(
        manifest=manifest,
        output_path=output_path,
    )

    assert baseline_plan.desired_state is not None

    metadata_path = output_path / ".boilr"
    state_path = metadata_path / "state.json"
    obsolete_path = output_path / "obsolete.txt"

    metadata_path.mkdir(parents=True)
    state_path.write_bytes(
        serialize_project_state(
            baseline_plan.desired_state
        )
    )
    obsolete_path.write_text(
        "obsolete",
        encoding="utf-8",
    )

    plan = generator.plan(
        manifest=manifest,
        output_path=output_path,
        clean=True,
    )

    assert [
        state.relative_path
        for state in plan.initial_output_state
    ] == [
        ".",
        "obsolete.txt",
    ]

    assert [
        removal.relative_path
        for removal in plan.removals
    ] == [
        "obsolete.txt",
    ]

    assert all(
        not removal.relative_path.casefold().startswith(
            ".boilr"
        )
        for removal in plan.removals
    )

    generator.execute(plan)

    assert obsolete_path.exists() is False
    assert metadata_path.is_dir()
    assert state_path.is_file()


@pytest.mark.parametrize(
    "reserved_name",
    [
        ".boilr",
        ".BOILR",
    ],
)
def test_reserved_state_path_cannot_be_destination(
    registry,
    tmp_path,
    reserved_name,
):
    output_path = tmp_path / "project"
    destination_path = (
        output_path
        / reserved_name
        / "module-owned.txt"
    )
    generator = ProjectGenerator(registry)

    with pytest.raises(
        UnsafePathError
    ) as error_info:
        generator._validate_destination_path(
            path=destination_path,
            output_path=output_path,
            module_key="example",
            field_path="modules.example.sources",
        )

    error = error_info.value

    assert error.code == "unsafe_path"
    assert error.module_key == "example"
    assert error.context["reason"] == (
        "reserved_state_path"
    )
    assert error.context["reserved_root"] == ".boilr"


@pytest.mark.parametrize(
    "reserved_name",
    [
        ".boilr",
        ".BOILR",
    ],
)
def test_reserved_state_path_cannot_be_removed(
    registry,
    tmp_path,
    reserved_name,
):
    output_path = tmp_path / "project"
    state_path = (
        output_path
        / reserved_name
        / "state.json"
    )
    generator = ProjectGenerator(registry)

    with pytest.raises(
        UnsafePathError
    ) as error_info:
        generator._validate_removal_path(
            path=state_path,
            output_path=output_path,
            module_key=None,
        )

    error = error_info.value

    assert error.code == "unsafe_path"
    assert error.context["reason"] == (
        "reserved_state_path"
    )
    assert error.context["reserved_root"] == ".boilr"


def test_other_hidden_output_paths_remain_available(
    registry,
    tmp_path,
):
    output_path = tmp_path / "project"
    generator = ProjectGenerator(registry)

    relative_path = (
        generator._validate_destination_path(
            path=output_path / ".env",
            output_path=output_path,
            module_key=None,
            field_path="generation.files",
        )
    )

    assert relative_path == ".env"