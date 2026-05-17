from pathlib import Path

import pytest

from boilr_generator.manifest import load_project_manifest_from_dict
from boilr_generator.modules.registry import ModuleRegistry
from boilr_generator.resolver import Resolver


@pytest.fixture
def templates_path() -> Path:
    return Path("packages/boilr-generator/templates")


@pytest.fixture
def registry(templates_path: Path) -> ModuleRegistry:
    return ModuleRegistry(templates_path)


@pytest.fixture
def valid_manifest_data() -> dict:
    return {
        "project": {
            "name": "my_app",
            "type": "fullstack_web",
            "version": "1.0.0",
        },
        "modules": [
            {
                "key": "postgres",
                "variables": {
                    "db_name": "my_app",
                    "db_user": "my_app",
                    "db_password": "password",
                    "db_port": 5432,
                },
            },
            {
                "key": "django",
                "variables": {
                    "project_name": "my_app",
                    "secret_key": "dev-secret",
                    "db_engine": "postgresql",
                    "db_host": "db",
                    "db_port": 5432,
                    "db_name": "my_app",
                    "db_user": "my_app",
                    "db_password": "password",
                },
                "options": {
                    "rest_framework": True,
                    "cors": True,
                },
            },
        ],
    }


@pytest.fixture
def manifest(valid_manifest_data: dict):
    return load_project_manifest_from_dict(valid_manifest_data)


@pytest.fixture
def resolved_project(registry: ModuleRegistry, manifest):
    return Resolver(registry).resolve(manifest)