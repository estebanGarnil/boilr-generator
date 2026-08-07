from pathlib import Path
from typing import Any

import yaml
from pydantic import ValidationError

from boilr_generator.exceptions import (
    ModuleLoadError,
    ModuleSchemaError,
)
from boilr_generator.modules.schemas import ModuleManifest


def load_module_from_dict(
    data: dict[str, Any],
) -> ModuleManifest:
    try:
        return ModuleManifest.model_validate(data)
    except ValidationError as error:
        details = _serialize_validation_errors(error)

        raise ModuleSchemaError(
            "Module manifest does not match the expected schema.",
            field_path=details[0]["path"] if details else None,
            context={"errors": details},
            suggestion="Check the structure and values of the module manifest.",
        ) from error


def load_module_from_yaml(
    path: str | Path,
) -> ModuleManifest:
    data = _read_yaml_file(path)
    return load_module_from_dict(data)


def _read_yaml_file(path: str | Path) -> dict[str, Any]:
    module_path = Path(path)

    if not module_path.exists():
        raise ModuleLoadError(
            f"Module file not found: {module_path}",
            context={"path": str(module_path)},
            suggestion="Check that the module.yml path is correct.",
        )

    if not module_path.is_file():
        raise ModuleLoadError(
            f"Module path is not a file: {module_path}",
            context={"path": str(module_path)},
            suggestion="Provide the path to a module.yml file.",
        )

    try:
        with module_path.open("r", encoding="utf-8") as file:
            data = yaml.safe_load(file)
    except yaml.YAMLError as error:
        context: dict[str, Any] = {
            "path": str(module_path),
        }

        problem_mark = getattr(error, "problem_mark", None)

        if problem_mark is not None:
            context["line"] = problem_mark.line + 1
            context["column"] = problem_mark.column + 1

        raise ModuleLoadError(
            f"Invalid YAML in module file: {module_path}",
            context=context,
            suggestion="Check the YAML syntax near the indicated position.",
        ) from error
    except (OSError, UnicodeError) as error:
        raise ModuleLoadError(
            f"Unable to read module file: {module_path}",
            context={"path": str(module_path)},
            suggestion="Check the file permissions and encoding.",
        ) from error

    if data is None:
        raise ModuleLoadError(
            f"Module file is empty: {module_path}",
            context={"path": str(module_path)},
            suggestion="Add a valid module definition.",
        )

    if not isinstance(data, dict):
        raise ModuleLoadError(
            "Module YAML root must be an object.",
            field_path="<root>",
            context={
                "path": str(module_path),
                "actual_type": type(data).__name__,
            },
            suggestion="Use YAML key-value pairs at the document root.",
        )

    return data


def _serialize_validation_errors(
    error: ValidationError,
) -> list[dict[str, str]]:
    details: list[dict[str, str]] = []

    for item in error.errors(include_url=False):
        path = ".".join(str(part) for part in item["loc"]) or "<root>"

        details.append(
            {
                "path": path,
                "type": str(item["type"]),
                "message": str(item["msg"]),
            }
        )

    return details