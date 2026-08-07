
import pytest
from boilr_generator.core.generation_plan import (
    GenerationPlan,
    PlannedRemoval,
)
from boilr_generator.exceptions import (
    FileConflictError,
    SourceNotFoundError,
)
from boilr_generator.generation import ProjectGenerator
from boilr_generator.modules.schemas import (
    CopySource,
    RenderSource,
)


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
    assert resolved_project.list_module_keys() == [
        "postgres",
        "django",
        "django-postgres",
    ]

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

    serialized_files = {
        file["relative_destination_path"]: file
        for file in data["files"]
    }

    docker_file = serialized_files[
        "docker-compose.yml"
    ]
    env_file = serialized_files[".env"]

    assert "content" not in docker_file
    assert "content" not in env_file
    assert docker_file["content_size"] > 0
    assert env_file["content_size"] > 0
    assert len(docker_file["content_sha256"]) == 64
    assert len(env_file["content_sha256"]) == 64
    assert data["summary"]["content_bytes"] > 0
    assert data["clean_output"] is False
    assert data["removals"] == []
    assert data["summary"]["removals_count"] == 0

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

def test_project_generator_plan_prepares_generated_files(
    registry,
    manifest,
    tmp_path,
):
    plan = ProjectGenerator(registry).plan(
        manifest,
        tmp_path,
    )

    planned_files = {
        file.relative_destination_path: file
        for file in plan.files
    }

    docker_file = planned_files[
        "docker-compose.yml"
    ]
    env_file = planned_files[".env"]

    assert b"services:" in docker_file.content
    assert b"DB_NAME=my_app" in env_file.content
    assert docker_file.content_size > 0
    assert env_file.content_size > 0

def test_project_generator_plan_prepares_module_files(
    registry,
    manifest,
    tmp_path,
):
    plan = ProjectGenerator(registry).plan(
        manifest,
        tmp_path,
    )

    copied_files = [
        file
        for file in plan.files
        if file.operation == "copy"
    ]
    rendered_files = [
        file
        for file in plan.files
        if file.operation == "render"
    ]

    assert copied_files
    assert rendered_files

    for planned_file in copied_files:
        assert planned_file.source_path is not None
        assert planned_file.content == (
            planned_file.source_path.read_bytes()
        )
        assert planned_file.mode is not None

    for planned_file in rendered_files:
        assert planned_file.source_path is not None
        assert planned_file.content_size > 0
        assert isinstance(
            planned_file.content,
            bytes,
        )

def test_project_generator_execute_uses_plan_only(
    registry,
    manifest,
    tmp_path,
    monkeypatch,
):
    generator = ProjectGenerator(registry)
    plan = generator.plan(manifest, tmp_path)

    def fail_if_called(*args, **kwargs):
        raise AssertionError(
            "Execution must not recalculate outputs."
        )

    monkeypatch.setattr(
        generator.file_generator,
        "copy_sources",
        fail_if_called,
    )
    monkeypatch.setattr(
        generator.file_generator,
        "render_sources",
        fail_if_called,
    )
    monkeypatch.setattr(
        generator.docker_generator,
        "generate",
        fail_if_called,
    )
    monkeypatch.setattr(
        generator.env_generator,
        "generate",
        fail_if_called,
    )

    generator.execute(plan)

    for planned_file in plan.files:
        if planned_file.action == "skip":
            continue

        assert (
            planned_file.destination_path.read_bytes()
            == planned_file.content
        )


def test_project_generator_clean_is_planned(
    registry,
    manifest,
    tmp_path,
):
    old_file = tmp_path / "old.txt"
    tmp_path.mkdir(
        parents=True,
        exist_ok=True,
    )
    old_file.write_text(
        "old",
        encoding="utf-8",
    )

    generator = ProjectGenerator(registry)
    plan = generator.plan(
        manifest,
        tmp_path,
        clean=True,
    )

    assert plan.clean_output is True
    assert all(
        file.action == "create"
        for file in plan.files
    )

    generator.execute(plan)

    assert old_file.exists() is False
    assert (
        tmp_path / "docker-compose.yml"
    ).exists()

def test_copy_strategy_skip_skips_existing_tree(
    registry,
    tmp_path,
):
    source_root = tmp_path / "module" / "source"
    output_path = tmp_path / "output"
    destination = output_path / "target"

    source_root.mkdir(parents=True)
    destination.mkdir(parents=True)

    (source_root / "new.txt").write_text(
        "new",
        encoding="utf-8",
    )
    (destination / "old.txt").write_text(
        "old",
        encoding="utf-8",
    )

    generator = ProjectGenerator(registry)

    files, removals = generator._plan_copy_source(
        module_key="example",
        module_path=tmp_path / "module",
        source=CopySource.model_validate(
            {
                "from": "source",
                "to": "target",
                "strategy": "skip",
            }
        ),
        output_path=output_path,
        field_path="modules.example.sources.copy[0].from",
        clean=False,
    )

    assert files
    assert all(file.action == "skip" for file in files)
    assert removals == []


def test_copy_strategy_replace_plans_removal(
    registry,
    tmp_path,
):
    source_root = tmp_path / "module" / "source"
    output_path = tmp_path / "output"
    destination = output_path / "target"

    source_root.mkdir(parents=True)
    destination.mkdir(parents=True)

    (source_root / "new.txt").write_text(
        "new",
        encoding="utf-8",
    )
    (destination / "old.txt").write_text(
        "old",
        encoding="utf-8",
    )

    generator = ProjectGenerator(registry)

    files, removals = generator._plan_copy_source(
        module_key="example",
        module_path=tmp_path / "module",
        source=CopySource.model_validate(
            {
                "from": "source",
                "to": "target",
                "strategy": "replace",
            }
        ),
        output_path=output_path,
        field_path="modules.example.sources.copy[0].from",
        clean=False,
    )

    assert all(
        file.action == "create"
        for file in files
    )
    assert len(removals) == 1
    assert removals[0].path == destination
    assert removals[0].relative_path == "target"
    assert removals[0].reason == "replace"

def test_copy_strategy_replace_executes_removal(
    registry,
    resolved_project,
    tmp_path,
):
    source_root = tmp_path / "module" / "source"
    output_path = tmp_path / "output"
    destination = output_path / "target"

    source_root.mkdir(parents=True)
    destination.mkdir(parents=True)

    source_file = source_root / "new.txt"
    old_file = destination / "old.txt"

    source_file.write_text(
        "new content",
        encoding="utf-8",
    )
    old_file.write_text(
        "old content",
        encoding="utf-8",
    )

    generator = ProjectGenerator(registry)

    files, removals = generator._plan_copy_source(
        module_key="example",
        module_path=tmp_path / "module",
        source=CopySource.model_validate(
            {
                "from": "source",
                "to": "target",
                "strategy": "replace",
            }
        ),
        output_path=output_path,
        field_path=(
            "modules.example.sources.copy[0].from"
        ),
        clean=False,
    )

    plan = GenerationPlan(
        resolved_project=resolved_project,
        output_path=output_path,
        files=files,
        removals=removals,
    )

    generator.execute(plan)

    assert old_file.exists() is False
    assert (
        destination / "new.txt"
    ).read_text(encoding="utf-8") == (
        "new content"
    )


def test_execute_rejects_unsafe_removal(
    registry,
    resolved_project,
    tmp_path,
):
    output_path = tmp_path / "output"
    outside_path = tmp_path / "outside"

    outside_path.mkdir()
    protected_file = outside_path / "protected.txt"
    protected_file.write_text(
        "keep",
        encoding="utf-8",
    )

    plan = GenerationPlan(
        resolved_project=resolved_project,
        output_path=output_path,
        removals=[
            PlannedRemoval(
                path=outside_path,
                relative_path="../outside",
                module="example",
                reason="replace",
            )
        ],
    )

    with pytest.raises(
        FileConflictError
    ) as error_info:
        ProjectGenerator(registry).execute(plan)

    error = error_info.value

    assert error.context["reason"] == (
        "unsafe_removal"
    )
    assert error.context["removal_path"] == str(
        outside_path
    )
    assert protected_file.exists() is True