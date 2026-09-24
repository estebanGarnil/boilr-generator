"""Neo4j module: generation, coexistence and provider contract."""
import pytest
import yaml

from boilr_generator.generation import ProjectGenerator
from boilr_generator.manifest import load_project_manifest_from_dict
from boilr_generator.modules.registry import ModuleRegistry
from boilr_generator.paths import get_builtin_modules_path


def generate(tmp_path, modules):
    registry = ModuleRegistry(get_builtin_modules_path())
    manifest = load_project_manifest_from_dict({
        "project": {"name": "graph_test", "type": "graph", "version": "1.0.0"},
        "modules": modules,
    })
    generator = ProjectGenerator(registry)
    output = tmp_path / "generated"
    plan = generator.plan(manifest, output)
    assert not output.exists()
    generator.execute(plan)
    for file in plan.files:
        assert (output / file.relative_destination_path).read_bytes() == file.content
    return yaml.safe_load((output / "docker-compose.yml").read_text()), output


@pytest.mark.parametrize("example", ["neo4j-only.yml", "django-postgres-neo4j.yml"])
def test_neo4j_examples(tmp_path, example):
    registry = ModuleRegistry(get_builtin_modules_path())
    path = registry.get_path("neo4j") / "docs/examples" / example
    data = yaml.safe_load(path.read_text())
    compose, output = generate(tmp_path, data["modules"])
    service = compose["services"]["neo4j"]
    assert service["environment"]["NEO4J_AUTH"] == "neo4j/dev-graph-password"
    assert "neo4j_data:/data" in service["volumes"]
    assert "RETURN 1;" in service["healthcheck"]["test"][1]
    assert (output / "database/neo4j/import/README.md").is_file()
    env = (output / ".env").read_text()
    assert "NEO4J_URI=bolt://neo4j:7687" in env
    assert "NEO4J_PASSWORD=" not in env
    if example.startswith("django"):
        assert {"neo4j", "db", "backend"} == set(compose["services"])
        assert "DB_ENGINE=postgresql" in env
        assert "django.db.backends.postgresql" in (
            output / "backend/config/settings/base.py"
        ).read_text()
    else:
        assert set(compose["services"]) == {"neo4j"}


def test_custom_ports_and_literal_dollars(tmp_path):
    password = 'pass$WORD${VAR}"with space'
    compose, output = generate(tmp_path, [{
        "key": "neo4j",
        "variables": {
            "neo4j_password": password,
            "neo4j_http_port": 17474,
            "neo4j_bolt_port": 17687,
        },
    }])
    service = compose["services"]["neo4j"]
    assert service["ports"] == ["127.0.0.1:17474:7474", "127.0.0.1:17687:7687"]
    assert service["environment"]["NEO4J_AUTH"] == "neo4j/" + password.replace("$", "$$")
    assert "$${NEO4J_AUTH#*/}" in service["healthcheck"]["test"][1]
    assert "NEO4J_LOCAL_URI=bolt://localhost:17687" in (output / ".env").read_text()


def test_graph_capability_and_typed_binding(tmp_path):
    from boilr_generator.resolver import Resolver

    root = tmp_path / "modules"
    consumer = root / "consumer"
    consumer.mkdir(parents=True)
    (consumer / "module.yml").write_text(yaml.safe_dump({
        "meta": {"name": "Consumer", "key": "consumer", "type": "backend", "version": "1.0.0"},
        "role": {"group": "backend"},
        "assembly": {"destination_root": "backend"},
        "requires": [{
            "capability": "graph.connection", "binding": "graph", "unique": True,
            "contract": {"port": "int", "uri": "string", "password": "string"},
        }],
    }))
    import shutil
    shutil.copytree(get_builtin_modules_path() / "database/neo4j", root / "neo4j")
    registry = ModuleRegistry(root)
    manifest = load_project_manifest_from_dict({
        "project": {"name": "test", "type": "graph", "version": "1.0.0"},
        "modules": [
            {"key": "neo4j", "variables": {"neo4j_password": "pass$literal"}},
            {"key": "consumer"},
        ],
    })
    project = Resolver(registry).resolve(manifest)
    values = project.binding_context_for("consumer")["graph"]
    assert values["port"] == 7687
    assert values["uri"] == "bolt://neo4j:7687"
    assert values["password"] == "pass$literal"
    assert [p.capability for p in registry.get("neo4j").provides] == ["graph.connection"]
