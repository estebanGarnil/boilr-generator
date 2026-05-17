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

    _validate_existing_modules(manifest, registry, result)

    if not result.valid:
        return result

    _validate_resolution(manifest, registry, result)

    return result

def _validate_existing_modules(
        manifest: ProjectManifest, 
        registry: ModuleRegistry, 
        result: ValidationResult,
) -> None:
    """Validate that all requested module exist."""
    for module in manifest.modules:
        if module.key not in registry.modules:
            result.add_error(
                code="module_not_found",
                message=f"Module not found: {module.key}",
                module=module.key
            )

def _validate_resolution(
        manifest: ProjectManifest,
        registry: ModuleRegistry,
        result: ValidationResult,
) -> None:
    """Validate resolver rules."""
    try: 
        Resolver(registry).resolve(manifest)
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
    