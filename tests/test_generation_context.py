from boilr_generator.core import (
    CapabilityBinding,
    CapabilityRequirement,
    ExtensionPointValue,
)
from boilr_generator.generation.context import (
    build_module_context,
)
from boilr_generator.generation.docker import (
    DockerComposeGenerator,
)
from boilr_generator.generation.env import EnvGenerator
from boilr_generator.generation.files import FileGenerator


def configure_unique_binding(project):
    requirement = CapabilityRequirement(
        module_key="django",
        binding_key="primary_database",
        capability="database.connection",
        unique=True,
    )

    binding = CapabilityBinding(
        binding_key="primary_database",
        capability="database.connection",
        consumer_module_key="django",
        provider_module_key="postgres",
        values={
            "engine": "postgresql",
            "host": "db",
            "port": 5432,
            "name": "my_app",
            "user": "my_app",
            "password": "password",
            "service": "db",
        },
    )

    project.requirements = [requirement]
    project.bindings = [binding]

    return project


def test_module_context_contains_unique_binding(
    resolved_project,
):
    project = resolved_project.model_copy(deep=True)
    configure_unique_binding(project)

    django = project.get_module("django")

    assert django is not None

    context = build_module_context(
        project,
        django,
    )

    assert context["project_name"] == "my_app"
    assert context["options"]["rest_framework"] is True
    assert context["bindings"]["primary_database"] == {
        "engine": "postgresql",
        "host": "db",
        "port": 5432,
        "name": "my_app",
        "user": "my_app",
        "password": "password",
        "service": "db",
    }


def test_module_context_contains_multiple_bindings(
    resolved_project,
):
    project = resolved_project.model_copy(deep=True)

    project.requirements = [
        CapabilityRequirement(
            module_key="django",
            binding_key="databases",
            capability="database.connection",
            unique=False,
        )
    ]

    project.bindings = [
        CapabilityBinding(
            binding_key="databases",
            capability="database.connection",
            consumer_module_key="django",
            provider_module_key="postgres",
            values={
                "host": "postgres",
            },
        ),
        CapabilityBinding(
            binding_key="databases",
            capability="database.connection",
            consumer_module_key="django",
            provider_module_key="mysql",
            values={
                "host": "mysql",
            },
        ),
    ]

    django = project.get_module("django")

    assert django is not None

    context = build_module_context(project, django)

    assert context["bindings"]["databases"] == [
        {
            "host": "postgres",
        },
        {
            "host": "mysql",
        },
    ]


def test_env_generator_can_render_binding_values(
    resolved_project,
):
    project = resolved_project.model_copy(deep=True)
    configure_unique_binding(project)

    django = project.get_module("django")

    assert django is not None
    assert django.manifest.exports is not None
    assert django.manifest.exports.env is not None

    django.manifest.exports.env.root[
        "BOUND_DATABASE_HOST"
    ] = "{{ bindings.primary_database.host }}"

    env = EnvGenerator().generate(project)

    assert env["BOUND_DATABASE_HOST"] == "db"


def test_docker_generator_can_render_binding_values(
    resolved_project,
):
    project = resolved_project.model_copy(deep=True)
    configure_unique_binding(project)

    django = project.get_module("django")

    assert django is not None
    assert django.manifest.docker is not None

    django.manifest.docker.services[
        "backend"
    ].root["database_service"] = (
        "{{ bindings.primary_database.service }}"
    )

    compose = DockerComposeGenerator().generate(project)

    assert compose["services"]["backend"][
        "database_service"
    ] == "db"


def test_file_generator_can_render_binding_values(
    resolved_project,
    tmp_path,
):
    project = resolved_project.model_copy(deep=True)
    configure_unique_binding(project)

    django = project.get_module("django")

    assert django is not None

    template_path = tmp_path / "binding.txt.j2"
    destination_path = tmp_path / "output" / "binding.txt"

    template_path.write_text(
        "{{ bindings.primary_database.host }}",
        encoding="utf-8",
    )

    context = build_module_context(project, django)

    content = FileGenerator().render_template_content(
        template_path=template_path,
        destination_path=destination_path,
        context=context,
        module_key="django",
        field_path="modules.django.sources.render[0].from",
    )

    assert content == "db"
    assert destination_path.exists() is False
    
def test_module_context_contains_extension_values(
    resolved_project,
):
    project = resolved_project.model_copy(deep=True)

    django = project.get_module("django")

    assert django is not None

    project.extension_point_values = [
        ExtensionPointValue(
            module_key="django",
            extension_point="python.dependencies",
            value=[
                "psycopg[binary]",
            ],
            contributor_module_keys=[
                "django_postgres",
            ],
        )
    ]

    context = build_module_context(
        project,
        django,
    )

    assert context["extensions"] == {
        "python.dependencies": [
            "psycopg[binary]",
        ]
    }

    context["extensions"][
        "python.dependencies"
    ].append("changed")

    assert project.extension_point_values[0].value == [
        "psycopg[binary]"
    ]