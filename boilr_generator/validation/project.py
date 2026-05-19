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

    _validate_required_variables(manifest, registry, result)

    if not result.valid:
        return result
    
    _validate_unknown_variables(manifest, registry, result)

    if not result.valid:
        return result
    
    _validate_variable_types(manifest, registry, result)

    if not result.valid:
        return result
    
    _validate_unknown_options(manifest, registry, result)

    if not result.valid:
        return result
    
    _validate_option_types(manifest, registry, result)

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
    
def _validate_required_variables(
    manifest: ProjectManifest,
    registry: ModuleRegistry,
    result: ValidationResult,
) -> None:
    """Validate required module variables."""
    for project_module in manifest.modules:
        module_manifest = registry.get(project_module.key)

        for variable_name, variable in module_manifest.variables.items():
            if not variable.required:
                continue

            if variable_name not in project_module.variables:
                result.add_error(
                    code="missing_required_variable",
                    message=(
                        f"Variable {variable_name} is required "
                        f"for module {project_module.key}."
                    ),
                    module=project_module.key,
                    field=variable_name,
                )

def _validate_variable_types(
        manifest: ProjectManifest, 
        registry: ModuleRegistry, 
        result: ValidationResult,
) -> None:
    """Validate module variable types."""
    type_mapping = {
        "string":str,
        "int":int,
        "boolean":bool,
        "list":list,
    }

    for project_module in manifest.modules:
        module_manifest = registry.get(project_module.key)

        for variable_name, value in project_module.variables.items():
            definition = module_manifest.variables.get(variable_name)

            if definition is None:
                continue
                
            expected_type = type_mapping[definition.type]

            if not isinstance(value, expected_type):
                result.add_error(
                    code="invalid_variable_type",
                    message=(
                        f"Variable {variable_name} for module "
                        f"{project_module.key} must be of type {definition.type}."
                    ),
                    module=project_module.key,
                    field=variable_name,
                )

def _validate_unknown_variables(
        manifest: ProjectManifest, 
        registry: ModuleRegistry,
        result: ValidationResult,
) -> None: 
    """Validate that provided variables are declared by the module."""
    for project_module in manifest.modules:
        module_manifest = registry.get(project_module.key)
        allowed_variables = set(module_manifest.variables.keys())

        for variables_name in project_module.variables:
            if variables_name not in allowed_variables:
                result.add_error(
                    code="unknown_variable",
                    message=(
                        f"Variable {variables_name} is not declared "
                        f"for module {project_module.key}."
                    ),
                    module=project_module.key,
                    field=variables_name,
                )

def _validate_unknown_options(
        manifest: ProjectManifest, 
        registry: ModuleRegistry, 
        result: ValidationResult,
) -> None:
    """Validate that provided options are declared by the module."""
    for project_module in manifest.modules:
        module_manifest = registry.get(project_module.key)
        allowed_options = set(module_manifest.options.keys())

        for option_name in project_module.options:
            if option_name not in allowed_options: 
                result.add_error(
                    code="unknown_option",
                    message=(
                        f"Option {option_name} is not declared "
                        f"for module {project_module.key}."
                    ),
                    module=project_module.key,
                    field=option_name,
                )

def _validate_option_types(
        manifest: ProjectManifest,
        registry: ModuleRegistry,
        result: ValidationResult,
) -> None:
    """Validate module option types."""
    type_mapping = {
        "string": str,
        "int" : int, 
        "boolean": bool,
        "list": list,
    }

    for project_module in manifest.modules:
        module_manifest = registry.get(project_module.key)

        for option_name, value in project_module.options.items():
            definition = module_manifest.options.get(option_name)

            if definition is None:
                continue

            expected_type = type_mapping[definition.type]

            if not isinstance(value, expected_type):
                result.add_error(
                    code="invalid_option_type",
                    message=(
                        f"Option {option_name} for module "
                        f"{project_module.key} must be of type "
                        f"{definition.type}."
                    ),
                    module=project_module.key,
                    field=option_name,
                )