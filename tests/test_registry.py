import pytest
from boilr_generator.exceptions import (
    DuplicateModuleError,
    ModuleNotFoundError,
)
from boilr_generator.modules.registry import ModuleRegistry


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


@pytest.mark.parametrize(
    "method_name",
    [
        "get",
        "get_path",
    ],
)
def test_registry_reports_unknown_module(
    registry,
    method_name,
):
    with pytest.raises(
        ModuleNotFoundError
    ) as error_info:
        getattr(registry, method_name)("unknown")

    error = error_info.value

    assert error.code == "module_not_found"
    assert error.module_key == "unknown"
    assert error.field_path == "modules.unknown"
    assert error.context == {
        "requested_module": "unknown",
        "available_modules": sorted(
            registry.list_keys()
        ),
    }
    assert error.suggestion is not None

def test_registry_reports_duplicate_module_paths(
    registry,
    tmp_path,
    monkeypatch,
):
    first_module_file = (
        tmp_path / "first" / "module.yml"
    )
    duplicate_module_file = (
        tmp_path / "second" / "module.yml"
    )

    for module_file in (
        first_module_file,
        duplicate_module_file,
    ):
        module_file.parent.mkdir()
        module_file.write_text(
            "",
            encoding="utf-8",
        )

    module_manifest = registry.get("django")

    monkeypatch.setattr(
        (
            "boilr_generator.modules.registry."
            "load_module_from_yaml"
        ),
        lambda _: module_manifest,
    )

    with pytest.raises(
        DuplicateModuleError
    ) as error_info:
        ModuleRegistry(tmp_path)

    error = error_info.value

    assert error.code == "duplicate_module"
    assert error.module_key == "django"
    assert error.field_path == "meta.key"
    assert error.context["module_key"] == "django"
    assert {
        error.context["first_module_path"],
        error.context["duplicate_module_path"],
    } == {
        str(first_module_file),
        str(duplicate_module_file),
    }
    assert error.suggestion is not None