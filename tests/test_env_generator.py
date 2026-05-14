from boilr_generator.generation.env import EnvGenerator


def test_env_generator_returns_dict(resolved_project):
    env = EnvGenerator().generate(resolved_project)

    assert isinstance(env, dict)


def test_env_generator_contains_database_values(resolved_project):
    env = EnvGenerator().generate(resolved_project)

    assert env["DB_ENGINE"] == "postgresql"
    assert env["DB_HOST"] == "db"
    assert env["DB_NAME"] == "my_app"
    assert env["DB_USER"] == "my_app"
    assert env["DB_PASSWORD"] == "password"
    assert env["DB_PORT"] == "5432"


def test_env_generator_values_are_strings(resolved_project):
    env = EnvGenerator().generate(resolved_project)

    for value in env.values():
        assert isinstance(value, str)