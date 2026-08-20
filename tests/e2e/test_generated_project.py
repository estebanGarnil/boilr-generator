from pathlib import Path

import yaml


def test_cli_generates_docker_e2e_inputs(
    generated_e2e_project: Path,
):
    expected_files = {
        ".env",
        "docker-compose.yml",
        "backend/Dockerfile",
        "backend/manage.py",
        "backend/requirements.txt",
        "backend/config/settings/base.py",
        "backend/config/settings/local.py",
        "backend/config/urls.py",
        "backend/apps/core/urls.py",
        "backend/apps/core/views.py",
    }

    generated_files = {
        path.relative_to(
            generated_e2e_project
        ).as_posix()
        for path in generated_e2e_project.rglob("*")
        if path.is_file()
    }

    assert expected_files <= generated_files

    compose_path = (
        generated_e2e_project
        / "docker-compose.yml"
    )
    compose = yaml.safe_load(
        compose_path.read_text(
            encoding="utf-8"
        )
    )

    services = compose["services"]

    assert set(services) == {
        "backend",
        "db",
    }

    backend = services["backend"]

    assert backend["build"] == {
        "context": "./backend",
        "dockerfile": "Dockerfile",
    }
    assert backend["depends_on"] == ["db"]
    assert backend["ports"] == ["8000:8000"]
    assert "python manage.py migrate" in backend["command"]
    assert (
        "python manage.py runserver "
        "0.0.0.0:8000"
        in backend["command"]
    )

    database = services["db"]

    assert database["image"] == "postgres:16"
    assert database["ports"] == ["5432:5432"]
    assert database["environment"] == {
        "POSTGRES_DB": "docker_e2e",
        "POSTGRES_USER": "docker_e2e",
        "POSTGRES_PASSWORD": (
            "docker-e2e-password"
        ),
    }

    env_values = dict(
        line.split("=", maxsplit=1)
        for line in (
            generated_e2e_project
            / ".env"
        ).read_text(
            encoding="utf-8"
        ).splitlines()
        if line and not line.startswith("#")
    )

    assert env_values[
        "DJANGO_SETTINGS_MODULE"
    ] == "config.settings.local"
    assert env_values["DB_HOST"] == "db"
    assert env_values["DB_PORT"] == "5432"
    assert env_values["DB_NAME"] == "docker_e2e"

    requirements = {
        line.strip()
        for line in (
            generated_e2e_project
            / "backend"
            / "requirements.txt"
        ).read_text(
            encoding="utf-8"
        ).splitlines()
        if line.strip()
    }

    assert "psycopg[binary]" in requirements

    config_urls = (
        generated_e2e_project
        / "backend"
        / "config"
        / "urls.py"
    ).read_text(
        encoding="utf-8"
    )
    core_urls = (
        generated_e2e_project
        / "backend"
        / "apps"
        / "core"
        / "urls.py"
    ).read_text(
        encoding="utf-8"
    )

    assert (
        'path("api/", include("apps.core.urls"))'
        in config_urls
    )
    assert (
        'path("health/", health, name="health")'
        in core_urls
    )