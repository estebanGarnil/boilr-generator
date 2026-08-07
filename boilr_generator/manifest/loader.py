from pathlib import Path
from typing import Any

import yaml
from pydantic import ValidationError

from boilr_generator.exceptions import (
    ManifestLoadError,
    ManifestNotFoundError,
    ManifestParseError,
    ManifestSchemaError,
)
from boilr_generator.manifest.schemas import ProjectManifest


def load_project_manifest_from_dict(
    data: dict[str, Any],
) -> ProjectManifest:
    try:
        return ProjectManifest.model_validate(data)
    except ValidationError as error:
        details = _serialize_validation_errors(error)

        raise ManifestSchemaError(
            "Project manifest does not match the expected schema.",
            field_path=details[0]["path"] if details else None,
            context={"errors": details},
            suggestion="Check the structure and values of the project manifest.",
        ) from error


def load_project_manifest_from_yaml(
    path: str | Path,
) -> ProjectManifest:
    data = _read_yaml_file(path)
    return load_project_manifest_from_dict(data)


def _read_yaml_file(path: str | Path) -> dict[str, Any]:
    manifest_path = Path(path)

    if not manifest_path.exists():
        raise ManifestNotFoundError(
            f"Manifest file not found: {manifest_path}",
            context={"path": str(manifest_path)},
            suggestion="Check that the manifest path is correct.",
        )

    if not manifest_path.is_file():
        raise ManifestLoadError(
            f"Manifest path is not a file: {manifest_path}",
            context={"path": str(manifest_path)},
            suggestion="Provide the path to a YAML manifest file.",
        )

    try:
        with manifest_path.open("r", encoding="utf-8") as file:
            data = yaml.safe_load(file)
    except yaml.YAMLError as error:
        context: dict[str, Any] = {
            "path": str(manifest_path),
        }

        problem_mark = getattr(error, "problem_mark", None)

        if problem_mark is not None:
            context["line"] = problem_mark.line + 1
            context["column"] = problem_mark.column + 1

        raise ManifestParseError(
            f"Invalid YAML in manifest file: {manifest_path}",
            context=context,
            suggestion="Check the YAML syntax near the indicated position.",
        ) from error
    except (OSError, UnicodeError) as error:
        raise ManifestLoadError(
            f"Unable to read manifest file: {manifest_path}",
            context={"path": str(manifest_path)},
            suggestion="Check the file permissions and encoding.",
        ) from error

    if data is None:
        raise ManifestParseError(
            f"Manifest file is empty: {manifest_path}",
            context={"path": str(manifest_path)},
            suggestion="Add the project and modules sections to the manifest.",
        )

    if not isinstance(data, dict):
        raise ManifestParseError(
            "Manifest root must be a YAML object.",
            field_path="<root>",
            context={
                "path": str(manifest_path),
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