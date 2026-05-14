from boilr_generator.generation.docker import DockerComposeGenerator


def test_docker_generator_returns_compose_dict(resolved_project):
    compose = DockerComposeGenerator().generate(resolved_project)

    assert isinstance(compose, dict)
    assert "services" in compose


def test_docker_generator_contains_postgres_service(resolved_project):
    compose = DockerComposeGenerator().generate(resolved_project)

    assert "db" in compose["services"]
    assert compose["services"]["db"]["image"] == "postgres:16"


def test_docker_generator_renders_postgres_port(resolved_project):
    compose = DockerComposeGenerator().generate(resolved_project)

    assert "5432:5432" in compose["services"]["db"]["ports"]


def test_docker_generator_contains_volumes(resolved_project):
    compose = DockerComposeGenerator().generate(resolved_project)

    assert "volumes" in compose
    assert "postgres_data" in compose["volumes"]