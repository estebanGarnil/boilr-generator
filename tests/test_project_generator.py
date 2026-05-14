from pathlib import Path

from boilr_generator.generation import ProjectGenerator


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