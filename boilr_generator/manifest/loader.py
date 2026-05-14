from pathlib import Path
from typing import Any

import yaml
from pydantic import ValidationError

from boilr_generator.manifest.exceptions import ManifestError, ManifestLoadError, ManifestValidationError
from boilr_generator.manifest.schemas import ProjectManifest


def load_project_manifest_from_dict(data: dict[str, Any]) -> ProjectManifest:
    try: 
        return ProjectManifest.model_validate(data)
    except ValidationError as error:
        raise ManifestValidationError("Invalid project manigest structure.") from error
    

def load_project_manifest_from_yaml(path: str | Path) -> ProjectManifest:
    data = _read_yaml_file(path)
    return load_project_manifest_from_dict(data)

def _read_yaml_file(path: str | Path) -> dict[str, Any]:
    path = Path(path)

    if not path.exists():
        raise ManifestLoadError(f"Manifest file not found {path}")
    
    if not path.is_file():
        raise ManifestLoadError(f"Manifest path is not a file: {path}")

    try:
        with path.open("r", encoding="utf-8") as file:
            data = yaml.safe_load(file)
    except yaml.YAMLError as error:
        raise ManifestLoadError(f"Invalid YAML file: {path}") from error

    if data is None:
        raise ManifestLoadError(f"Manifest file is empty: {path}")

    if not isinstance(data, dict):
        raise ManifestLoadError("Manifest root must be a YAML object.")

    return data