from boilr_generator.core.generation_plan import PlannedFile
from boilr_generator.generation.project import ProjectGenerator
from boilr_generator.manifest import (
    load_project_manifest_from_dict,
)


def _files_by_resource_id(plan):
    return {
        planned_file.resource_id: planned_file
        for planned_file in plan.files
    }


def _manifest_with_integrations():
    return load_project_manifest_from_dict(
        {
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
                    "key": "redis",
                    "variables": {
                        "redis_host_port": 6379,
                        "redis_database": 0,
                    },
                },
                {
                    "key": "django",
                    "variables": {
                        "project_name": "my_app",
                        "secret_key": "dev-secret",
                        "django_settings_module": (
                            "config.settings.local"
                        ),
                        "allowed_hosts": [
                            "localhost",
                            "127.0.0.1",
                        ],
                        "backend_port": 8000,
                        "debug": True,
                    },
                    "options": {
                        "rest_framework": True,
                        "cors": True,
                    },
                },
                {
                    "key": "django-postgres",
                },
                {
                    "key": "django-redis",
                },
            ],
        }
    )


def test_planned_file_normalizes_owner_and_contributors(
    tmp_path,
):
    planned_file = PlannedFile(
        source_path=None,
        destination_path=tmp_path / "generated.txt",
        relative_destination_path="generated.txt",
        resource_id="module:django:render:generated",
        default_relative_path="generated.txt",
        operation="render",
        action="create",
        content=b"content",
        module="django",
        contributors=[
            "django-redis",
            "django",
            "django-redis",
        ],
    )

    assert planned_file.owner == "django"
    assert planned_file.contributors == [
        "django",
        "django-redis",
    ]


def test_generation_plan_tracks_exact_resource_contributors(
    registry,
    tmp_path,
):
    plan = ProjectGenerator(registry).plan(
        manifest=_manifest_with_integrations(),
        output_path=tmp_path / "output",
    )
    files = _files_by_resource_id(plan)

    assert files["module:django:render:manage"].contributors == [
        "django",
    ]
    assert files[
        "module:django:render:dockerfile"
    ].contributors == [
        "django",
    ]
    assert files[
        "module:django:render:requirements"
    ].contributors == [
        "django",
        "django-postgres",
        "django-redis",
    ]
    assert files[
        "module:django:render:settings-base"
    ].contributors == [
        "django",
        "django-postgres",
        "django-redis",
        "postgres",
    ]

    copied_files = [
        planned_file
        for planned_file in plan.files
        if planned_file.resource_id.startswith(
            "module:django:copy:"
        )
    ]

    assert copied_files
    assert all(
        planned_file.owner == "django"
        and planned_file.contributors == ["django"]
        for planned_file in copied_files
    )

    assert files["core:docker-compose"].owner is None
    assert files["core:docker-compose"].contributors == [
        "django",
        "postgres",
        "redis",
    ]
    assert files["core:environment"].owner is None
    assert files["core:environment"].contributors == [
        "django",
        "postgres",
        "redis",
    ]


def test_generation_plan_serializes_resource_contributors(
    registry,
    tmp_path,
):
    plan = ProjectGenerator(registry).plan(
        manifest=_manifest_with_integrations(),
        output_path=tmp_path / "output",
    )
    serialized_files = {
        planned_file["resource_id"]: planned_file
        for planned_file in plan.to_dict()["files"]
    }

    assert serialized_files[
        "module:django:render:settings-base"
    ]["module"] == "django"
    assert serialized_files[
        "module:django:render:settings-base"
    ]["contributors"] == [
        "django",
        "django-postgres",
        "django-redis",
        "postgres",
    ]
    assert serialized_files[
        "core:docker-compose"
    ]["module"] is None
    assert serialized_files[
        "core:docker-compose"
    ]["contributors"] == [
        "django",
        "postgres",
        "redis",
    ]
