
import pytest
from boilr_generator.core.generation_plan import GenerationPlan
from boilr_generator.exceptions import (
    FileConflictError,
    SourceNotFoundError,
)
from boilr_generator.generation import ProjectGenerator
from boilr_generator.modules.schemas import RenderSource


def test_project_generator_creates_output_directory(tmp_path, registry, manifest):
    output_path = tmp_path / "my_app"

    ProjectGenerator(registry).generate(
        manifest=manifest,
        output_path=output_path,
        clean=True,
    )

    assert output_path.exists()
    assert output_path.is_dir()


def test_project_generator_writes_docker_compose(tmp_path, registry, manifest):
    output_path = tmp_path / "my_app"

    ProjectGenerator(registry).generate(
        manifest=manifest,
        output_path=output_path,
        clean=True,
    )

    assert (output_path / "docker-compose.yml").exists()


def test_project_generator_writes_env_file(tmp_path, registry, manifest):
    output_path = tmp_path / "my_app"

    ProjectGenerator(registry).generate(
        manifest=manifest,
        output_path=output_path,
        clean=True,
    )

    env_file = output_path / ".env"

    assert env_file.exists()
    assert "DB_NAME=my_app" in env_file.read_text(encoding="utf-8")


def test_project_generator_returns_resolved_project(tmp_path, registry, manifest):
    output_path = tmp_path / "my_app"

    resolved_project = ProjectGenerator(registry).generate(
        manifest=manifest,
        output_path=output_path,
        clean=True,
    )

    assert resolved_project.project.name == "my_app"
    assert resolved_project.list_module_keys() == ["postgres", "django"]


def test_project_generator_clean_removes_existing_files(tmp_path, registry, manifest):
    output_path = tmp_path / "my_app"
    output_path.mkdir()

    old_file = output_path / "old.txt"
    old_file.write_text("old content", encoding="utf-8")

    ProjectGenerator(registry).generate(
        manifest=manifest,
        output_path=output_path,
        clean=True,
    )

    assert old_file.exists() is False

def test_project_generator_creates_generation_plan(
    registry, 
    manifest, 
    tmp_path,
):
    generator = ProjectGenerator(registry)

    plan = generator.plan(
        manifest=manifest,
        output_path=tmp_path,
    )

    assert isinstance(plan, GenerationPlan)
    assert plan.output_path == tmp_path
    assert plan.resolved_project is not None
    assert len(plan.files) > 0
    assert "docker-compose.yml" in [file.relative_destination_path for file in plan.files]
    assert ".env" in [file.relative_destination_path for file in plan.files]
    assert "backend" in plan.docker_services or len(plan.docker_services) > 0
    assert len(plan.env_variables) > 0

def test_project_generator_plan_does_not_write_files(
        registry, 
        manifest, 
        tmp_path,
):
    generator = ProjectGenerator(registry)

    generator.plan(
        manifest=manifest,
        output_path=tmp_path,
    )

    assert not (tmp_path / "docker-compose.yml").exists()
    assert not (tmp_path / ".env").exists()

def test_project_generator_execute_writes_files(
    registry, 
    manifest, 
    tmp_path,
):
    generator = ProjectGenerator(registry)

    plan = generator.plan(
        manifest=manifest,
        output_path=tmp_path,
    )

    generator.execute(plan)

    assert (tmp_path / "docker-compose.yml").exists()
    assert (tmp_path / ".env").exists()



def test_project_generator_plan_detects_overwritten_files(
        registry,
        manifest, 
        tmp_path,
):
    existing_file = tmp_path / ".env"
    existing_file.write_text("OLD=value\n", encoding="utf-8")

    generator = ProjectGenerator(registry)

    plan = generator.plan(manifest, tmp_path)

    env_file = next(
        file for file in plan.files if file.relative_destination_path == ".env"
    )

    assert env_file.action == "overwrite"

def test_project_generator_plan_contains_file_operations(
    registry,
    manifest,
    tmp_path,
):
    generator = ProjectGenerator(registry)

    plan = generator.plan(manifest, tmp_path)

    operations = {file.operation for file in plan.files}

    assert "copy" in operations or "render" in operations
    assert "generate" in operations

def test_generation_plan_can_be_serialized(
    registry,
    manifest,
    tmp_path,
):
    generator = ProjectGenerator(registry)

    plan = generator.plan(manifest, tmp_path)

    data = plan.to_dict()

    assert data["summary"]["files_count"] == len(plan.files)
    assert isinstance(data["files"], list)
    assert data["files"][0]["relative_destination_path"]

def test_project_generator_plan_reports_missing_template(
    registry,
    manifest,
    resolved_project,
    tmp_path,
    monkeypatch,
):
    project = resolved_project.model_copy(deep=True)
    postgres = project.get_module("postgres")

    assert postgres is not None

    postgres.manifest.sources.render = [
        RenderSource.model_validate(
            {
                "from": "missing-plan-template.j2",
                "to": "generated.txt",
            }
        )
    ]

    generator = ProjectGenerator(registry)

    monkeypatch.setattr(
        generator.resolver,
        "resolve",
        lambda _: project,
    )

    with pytest.raises(SourceNotFoundError) as error_info:
        generator.plan(manifest, tmp_path)

    error = error_info.value

    assert error.code == "source_not_found"
    assert error.module_key == "postgres"
    assert error.field_path == (
        "modules.postgres.sources.render[0].from"
    )
    assert error.context["source_kind"] == "template"
    assert error.context["source_path"].endswith(
        "missing-plan-template.j2"
    )


def test_project_generator_plan_rejects_file_conflicts(
    registry,
    manifest,
    resolved_project,
    tmp_path,
    monkeypatch,
):
    project = resolved_project.model_copy(deep=True)

    module = next(
        (
            candidate
            for candidate in project.modules
            if candidate.manifest.sources.render
        ),
        None,
    )

    assert module is not None

    original_source = module.manifest.sources.render[0]
    module.manifest.sources.render.append(
        original_source.model_copy(deep=True)
    )

    generator = ProjectGenerator(registry)

    monkeypatch.setattr(
        generator.resolver,
        "resolve",
        lambda _: project,
    )

    with pytest.raises(FileConflictError) as error_info:
        generator.plan(manifest, tmp_path)

    error = error_info.value

    assert error.code == "file_conflict"
    assert error.module_key == module.key
    assert error.field_path.startswith("generation.files[")
    assert error.context["destination"]
    assert error.context["first_module"] == module.key
    assert error.context["conflicting_module"] == module.key
    assert error.context["first_operation"] == "render"
    assert error.context["conflicting_operation"] == "render"
    assert error.suggestion is not None