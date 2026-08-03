"""Project validation service."""

from collections.abc import Iterable
from typing import Any

from boilr_generator.diagnostics import ValidationResult
from boilr_generator.exceptions import ResolutionError
from boilr_generator.manifest.schemas import ProjectManifest
from boilr_generator.modules.registry import ModuleRegistry
from boilr_generator.modules.schemas import ModuleManifest
from boilr_generator.resolver import Resolver

TYPE_MAPPING: dict[str, type] = {
    "string": str,
    "int": int,
    "boolean": bool,
    "list": list,
}


def validate_project(
    manifest: ProjectManifest,
    registry: ModuleRegistry,
) -> ValidationResult:
    """Validate a project manifest against the module registry."""
    result = ValidationResult()

    _validate_existing_modules(manifest, registry, result)

    if not result.is_valid:
        return result

    _validate_module_inputs(manifest, registry, result)
    _validate_requirements(manifest, registry, result)
    _validate_unique_roles(manifest, registry, result)

    if not result.is_valid:
        return result

    _validate_resolution(manifest, registry, result)

    return result


def _validate_existing_modules(
    manifest: ProjectManifest,
    registry: ModuleRegistry,
    result: ValidationResult,
) -> None:
    """Validate that all requested modules exist."""
    for project_module in manifest.modules:
        if registry.has(project_module.key):
            continue

        result.add_error(
            code="module_not_found",
            message=f"Module not found: {project_module.key}.",
            module_key=project_module.key,
            field_path=f"modules.{project_module.key}",
            context={
                "requested_module": project_module.key,
            },
            suggestion=(
                "Check the module key or install a module providing this key."
            ),
        )


def _validate_module_inputs(
    manifest: ProjectManifest,
    registry: ModuleRegistry,
    result: ValidationResult,
) -> None:
    """Validate variables and options for all selected modules."""
    for project_module in manifest.modules:
        module_manifest = registry.get(project_module.key)

        _validate_required_variables(
            project_module_key=project_module.key,
            provided_variables=project_module.variables,
            module_manifest=module_manifest,
            result=result,
        )

        _validate_unknown_fields(
            project_module_key=project_module.key,
            provided_fields=project_module.variables,
            declared_fields=module_manifest.variables.keys(),
            field_kind="variable",
            result=result,
        )

        _validate_field_types(
            project_module_key=project_module.key,
            provided_fields=project_module.variables,
            definitions=module_manifest.variables,
            field_kind="variable",
            result=result,
        )

        _validate_unknown_fields(
            project_module_key=project_module.key,
            provided_fields=project_module.options,
            declared_fields=module_manifest.options.keys(),
            field_kind="option",
            result=result,
        )

        _validate_field_types(
            project_module_key=project_module.key,
            provided_fields=project_module.options,
            definitions=module_manifest.options,
            field_kind="option",
            result=result,
        )


def _validate_required_variables(
    project_module_key: str,
    provided_variables: dict[str, Any],
    module_manifest: ModuleManifest,
    result: ValidationResult,
) -> None:
    """Validate required module variables."""
    for variable_name, variable in module_manifest.variables.items():
        if not variable.required:
            continue

        if variable_name in provided_variables:
            continue

        result.add_error(
            code="missing_required_variable",
            message=(
                f"Variable {variable_name} is required "
                f"for module {project_module_key}."
            ),
            module_key=project_module_key,
            field_path=(
                f"modules.{project_module_key}.variables.{variable_name}"
            ),
            context={
                "variable": variable_name,
                "required": True,
            },
            suggestion=(
                f"Provide a value for variable {variable_name} "
                f"in module {project_module_key}."
            ),
        )


def _validate_unknown_fields(
    project_module_key: str,
    provided_fields: dict[str, Any],
    declared_fields: Iterable[str],
    field_kind: str,
    result: ValidationResult,
) -> None:
    """Validate that provided fields are declared by the module."""
    declared_field_set = set(declared_fields)
    section = _field_section(field_kind)

    for field_name in provided_fields:
        if field_name in declared_field_set:
            continue

        result.add_error(
            code=f"unknown_{field_kind}",
            message=(
                f"{field_kind.capitalize()} {field_name} is not declared "
                f"for module {project_module_key}."
            ),
            module_key=project_module_key,
            field_path=(
                f"modules.{project_module_key}.{section}.{field_name}"
            ),
            context={
                "field": field_name,
                "field_kind": field_kind,
                "declared_fields": sorted(declared_field_set),
            },
            suggestion=(
                f"Remove {field_name} or declare it in the module manifest."
            ),
        )


def _validate_field_types(
    project_module_key: str,
    provided_fields: dict[str, Any],
    definitions,
    field_kind: str,
    result: ValidationResult,
) -> None:
    """Validate provided field types."""
    section = _field_section(field_kind)

    for field_name, value in provided_fields.items():
        definition = definitions.get(field_name)

        if definition is None:
            continue

        expected_type = TYPE_MAPPING[definition.type]

        if _matches_expected_type(value, expected_type):
            continue

        result.add_error(
            code=f"invalid_{field_kind}_type",
            message=(
                f"{field_kind.capitalize()} {field_name} for module "
                f"{project_module_key} must be of type {definition.type}."
            ),
            module_key=project_module_key,
            field_path=(
                f"modules.{project_module_key}.{section}.{field_name}"
            ),
            context={
                "field": field_name,
                "field_kind": field_kind,
                "expected_type": definition.type,
                "actual_type": type(value).__name__,
            },
            suggestion=(
                f"Provide a value of type {definition.type} "
                f"for {field_name}."
            ),
        )


def _validate_requirements(
    manifest: ProjectManifest,
    registry: ModuleRegistry,
    result: ValidationResult,
) -> None:
    """Validate mandatory module requirements."""
    selected_modules = [
        registry.get(project_module.key)
        for project_module in manifest.modules
    ]

    selected_types = {module.meta.type for module in selected_modules}

    for module in selected_modules:
        for requirement in module.requirements.mandatory:
            if requirement.type in selected_types:
                continue

            result.add_error(
                code="missing_requirement",
                message=(
                    f"Module {module.meta.key} requires "
                    f"a module of type {requirement.type}."
                ),
                module_key=module.meta.key,
                field_path=(
                    f"modules.{module.meta.key}."
                    f"requirements.{requirement.type}"
                ),
                context={
                    "required_type": requirement.type,
                    "selected_types": sorted(selected_types),
                },
                suggestion=(
                    f"Add a module of type {requirement.type} "
                    f"to the project manifest."
                ),
            )


def _validate_unique_roles(
    manifest: ProjectManifest,
    registry: ModuleRegistry,
    result: ValidationResult,
) -> None:
    """Validate unique module roles."""
    selected_modules = [
        registry.get(project_module.key)
        for project_module in manifest.modules
    ]

    seen_groups: dict[str, str] = {}

    for module in selected_modules:
        if not module.role.unique:
            continue

        group = module.role.group

        if group not in seen_groups:
            seen_groups[group] = module.meta.key
            continue

        result.add_error(
            code="duplicate_unique_role",
            message=(
                f"Modules {seen_groups[group]} and {module.meta.key} "
                f"cannot both be used because role {group} is unique."
            ),
            module_key=module.meta.key,
            field_path=f"modules.{module.meta.key}.role.{group}",
            context={
                "role": group,
                "first_module": seen_groups[group],
                "conflicting_module": module.meta.key,
            },
            suggestion=(
                f"Keep only one module using the unique role {group}."
            ),
        )


def _validate_resolution(
    manifest: ProjectManifest,
    registry: ModuleRegistry,
    result: ValidationResult,
) -> None:
    """Validate resolver rules."""
    try:
        Resolver(registry).resolve(manifest)
    except ResolutionError as error:
        result.add_error(
            code=getattr(error, "code", "resolution_error"),
            message=str(error),
            module_key=getattr(error, "module_key", None),
            field_path=getattr(error, "field_path", None),
            context=getattr(error, "context", {}),
            suggestion=getattr(error, "suggestion", None),
        )


def _field_section(field_kind: str) -> str:
    """Return the manifest section associated with a field kind."""
    if field_kind == "variable":
        return "variables"

    return "options"


def _matches_expected_type(value: Any, expected_type: type) -> bool:
    """Check a value type without accepting booleans as integers."""
    if expected_type is int:
        return isinstance(value, int) and not isinstance(value, bool)

    return isinstance(value, expected_type)
