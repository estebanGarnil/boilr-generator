"""Project validation service."""

from boilr_generator.core.exceptions import (
    ModuleCompatibilityError,
    ModuleNotFoundError,
    ModuleRequirementError,
    ModuleVariableError,
)
from boilr_generator.core.validation import ValidationResult
from boilr_generator.manifest.schemas import ProjectManifest
from boilr_generator.modules.registry import ModuleRegistry
from boilr_generator.resolver import Resolver


def validate_project(
    manifest: ProjectManifest,
    registry: ModuleRegistry,
) -> ValidationResult:
    """Validate a project manifest against the module registry."""
    result = ValidationResult()

    try:
        Resolver(registry).resolve(manifest)
    except ModuleNotFoundError as error:
        result.add_error(
            code="module_not_found",
            message=str(error),
        )
    except ModuleRequirementError as error:
        result.add_error(
            code="missing_requirement",
            message=str(error),
        )
    except ModuleCompatibilityError as error:
        result.add_error(
            code="module_incompatibility",
            message=str(error),
        )
    except ModuleVariableError as error:
        result.add_error(
            code="module_variable_error",
            message=str(error),
        )

    return result