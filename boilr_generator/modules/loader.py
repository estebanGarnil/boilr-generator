from pathlib import Path
from typing import Any

import yaml
from pydantic import ValidationError

from boilr_generator.modules.exceptions import ModuleLoadError, ModuleValidationError
from boilr_generator.modules.schemas import ModuleManifest


def load_module_from_dict(data: dict[str, Any]) -> ModuleManifest:
    try:
        return ModuleManifest.model_validate(data)
    except ValidationError as error:
        raise ModuleValidationError("Invalid module manifest.") from error


def load_module_from_yaml(path: str | Path) -> ModuleManifest:
    data = _read_yaml_file(path)
    return load_module_from_dict(data)


def _read_yaml_file(path: str | Path) -> dict[str, Any]:
    path = Path(path)

    if not path.exists():
        raise ModuleLoadError(f"Module file not found: {path}")

    try:
        with path.open("r", encoding="utf-8") as file:
            data = yaml.safe_load(file)
    except yaml.YAMLError as error:
        raise ModuleLoadError(f"Invalid YAML: {path}") from error

    if not isinstance(data, dict):
        raise ModuleLoadError("Module YAML must be an object.")

    return data