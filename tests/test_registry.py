import pytest

from boilr_generator.modules.registry import ModuleRegistry
from boilr_generator.core.exceptions import ModuleNotFoundError

def test_registry_loads_available_modules(registry):
    keys = registry.list_keys()

    assert "django" in keys
    assert "postgres" in keys


def test_registry_can_get_module(registry):
    module = registry.get("django")

    assert module.meta.key == "django"
    assert module.meta.type == "backend"


def test_registry_can_get_module_path(registry):
    path = registry.get_path("django")

    assert path.exists()
    assert path.name == "django"


def test_registry_checks_existing_module(registry):
    assert registry.has("django") is True
    assert registry.has("unknown") is False


def test_registry_lists_modules_by_type(registry):
    database_modules = registry.list_by_type("database")

    assert len(database_modules) >= 1
    assert any(module.meta.key == "postgres" for module in database_modules)


def test_registry_raises_for_unknown_module(registry):
    with pytest.raises(ModuleNotFoundError):
        registry.get("unknown")