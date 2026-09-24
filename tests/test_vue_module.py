"""Integration coverage for the built-in Vue module."""
import json
from pathlib import Path

import pytest
import yaml

from boilr_generator.generation import ProjectGenerator
from boilr_generator.manifest import load_project_manifest_from_dict
from boilr_generator.modules.registry import ModuleRegistry
from boilr_generator.paths import get_builtin_modules_path


@pytest.mark.parametrize("example", ["vue-only.yml", "django-vue-postgres.yml"])
def test_vue_example_plan_and_execution(tmp_path, example):
    registry = ModuleRegistry(get_builtin_modules_path())
    source = registry.get_path("vue") / "docs" / "examples" / example
    manifest = load_project_manifest_from_dict(yaml.safe_load(source.read_text()))
    generator = ProjectGenerator(registry)
    output = tmp_path / "generated"
    plan = generator.plan(manifest, output)
    assert not output.exists(), "Planning must not create the output"
    generator.execute(plan)
    for planned in plan.files:
        if planned.action != "skip":
            actual = output / planned.relative_destination_path
            assert actual.read_bytes() == planned.content
    app = (output / "frontend/src/App.vue").read_text()
    assert "{{ count }}" in app
    assert "{{ projectName }}" in app
    compose = yaml.safe_load((output / "docker-compose.yml").read_text())
    frontend = compose["services"]["frontend"]
    assert frontend["ports"] == ["127.0.0.1:5173:5173"]
    assert "depends_on" not in frontend
    if example == "django-vue-postgres.yml":
        assert {"frontend", "backend"}.issubset(compose["services"])
        assert frontend["environment"]["BOILR_API_PROXY_TARGET"] == "http://backend:8000"
    else:
        assert set(compose["services"]) == {"frontend"}
        assert frontend["environment"]["BOILR_API_PROXY_TARGET"] == ""
    package = json.loads((output / "frontend/package.json").read_text())
    lock = json.loads((output / "frontend/package-lock.json").read_text())
    assert package["dependencies"] == lock["packages"][""]["dependencies"]
    assert package["devDependencies"] == lock["packages"][""]["devDependencies"]


def test_vue_custom_values_are_preserved(tmp_path):
    registry = ModuleRegistry(get_builtin_modules_path())
    title = 'Été "Vue" \\ test\n<script>'
    manifest = load_project_manifest_from_dict({
        "project": {"name": "custom", "type": "frontend", "version": "1.0.0"},
        "modules": [{
            "key": "vue",
            "variables": {"project_name": title, "frontend_port": 5199},
            "options": {"polling": True},
        }],
    })
    generator = ProjectGenerator(registry)
    generator.execute(generator.plan(manifest, tmp_path / "output"))
    frontend = tmp_path / "output/frontend"
    text = (frontend / "src/app-config.js").read_text()
    assert json.loads(text.removeprefix("export const projectName = ").strip()) == title
    assert "usePolling: true" in (frontend / "vite.config.js").read_text()
    compose = yaml.safe_load((frontend.parent / "docker-compose.yml").read_text())
    assert compose["services"]["frontend"]["ports"] == ["127.0.0.1:5199:5173"]


def test_vue_defaults_need_no_backend(tmp_path):
    registry = ModuleRegistry(get_builtin_modules_path())
    manifest = load_project_manifest_from_dict({
        "project": {"name": "minimal", "type": "frontend", "version": "1.0.0"},
        "modules": [{"key": "vue"}],
    })
    generator = ProjectGenerator(registry)
    generator.execute(generator.plan(manifest, tmp_path / "minimal"))
    assert Path(tmp_path / "minimal/frontend/package-lock.json").is_file()
