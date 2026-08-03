"""Validation rules used during project resolution."""

from typing import Any

from boilr_generator.core import ResolvedModule
from boilr_generator.exceptions import (
    AmbiguousRequirementError,
    IncompatibleModuleError,
    InvalidVariableTypeError,
    MissingRequirementError,
    MissingVariableError,
)

TYPE_MAPPING: dict[str, type] = {
    "string": str,
    "int": int,
    "boolean": bool,
    "list": list,
}


class ProjectValidator:
    """Validate resolved modules before assembling the project."""

    def validate_requirements(
        self,
        modules: list[ResolvedModule],
    ) -> None:
        """Validate mandatory requirements for every selected module."""
        for module in modules:
            self._validate_module_requirements(module, modules)

    def validate_compatibility(
        self,
        modules: list[ResolvedModule],
    ) -> None:
        """Validate compatibility rules between selected modules."""
        for module in modules:
            for other in modules:
                if module is other:
                    continue

                if module.manifest.compatibility.is_compatible(
                    other.type,
                    other.key,
                ):
                    continue

                raise IncompatibleModuleError(
                    (
                        f"Module '{module.key}' is not compatible with "
                        f"'{other.key}' (type: {other.type})."
                    ),
                    module_key=module.key,
                    field_path=(
                        f"modules.{module.key}.compatibility.{other.type}"
                    ),
                    context={
                        "module": module.key,
                        "incompatible_module": other.key,
                        "incompatible_module_type": other.type,
                    },
                    suggestion=(
                        f"Remove module '{other.key}' or select a compatible "
                        f"module of type '{other.type}'."
                    ),
                )

    def _validate_module_requirements(
        self,
        module: ResolvedModule,
        all_modules: list[ResolvedModule],
    ) -> None:
        """Validate the mandatory requirements of one module."""
        for requirement in module.manifest.requirements.mandatory:
            matching_modules = [
                candidate
                for candidate in all_modules
                if candidate.type == requirement.type
            ]

            field_path = (
                f"modules.{module.key}.requirements.{requirement.type}"
            )

            if not matching_modules:
                available_types = sorted(
                    {candidate.type for candidate in all_modules}
                )

                raise MissingRequirementError(
                    (
                        f"Module '{module.key}' requires a module of type "
                        f"'{requirement.type}', but none was found."
                    ),
                    module_key=module.key,
                    field_path=field_path,
                    context={
                        "required_type": requirement.type,
                        "available_types": available_types,
                    },
                    suggestion=(
                        f"Add a module of type '{requirement.type}' "
                        "to the project manifest."
                    ),
                )

            if requirement.unique and len(matching_modules) > 1:
                candidate_keys = [
                    candidate.key for candidate in matching_modules
                ]

                raise AmbiguousRequirementError(
                    (
                        f"Module '{module.key}' requires a unique module "
                        f"of type '{requirement.type}', but "
                        f"{len(matching_modules)} were found."
                    ),
                    module_key=module.key,
                    field_path=field_path,
                    context={
                        "required_type": requirement.type,
                        "candidate_modules": candidate_keys,
                        "candidate_count": len(matching_modules),
                    },
                    suggestion=(
                        f"Keep only one module of type "
                        f"'{requirement.type}'."
                    ),
                )

    def validate_variables(
        self,
        modules: list[ResolvedModule],
    ) -> None:
        """Validate required variables for every selected module."""
        for module in modules:
            self._validate_module_variables(module)

    def _validate_module_variables(
        self,
        module: ResolvedModule,
    ) -> None:
        """Validate the required variables of one module."""
        for name, definition in module.manifest.variables.items():
            if not definition.required or name in module.variables:
                continue

            raise MissingVariableError(
                (
                    f"Module '{module.key}' requires variable '{name}', "
                    "but it was not provided and has no default."
                ),
                module_key=module.key,
                field_path=f"modules.{module.key}.variables.{name}",
                context={
                    "variable": name,
                    "required": True,
                },
                suggestion=(
                    f"Provide variable '{name}' for module "
                    f"'{module.key}'."
                ),
            )

    def validate_variable_types(
        self,
        modules: list[ResolvedModule],
    ) -> None:
        """Validate the types of all resolved module variables."""
        for module in modules:
            self._validate_module_variable_types(module)

    def _validate_module_variable_types(
        self,
        module: ResolvedModule,
    ) -> None:
        """Validate the resolved variable types of one module."""
        for name, value in module.variables.items():
            definition = module.manifest.variables.get(name)

            if definition is None:
                continue

            expected_type = definition.type

            if self._check_type(value, expected_type):
                continue

            raise InvalidVariableTypeError(
                (
                    f"Variable '{name}' in module '{module.key}' "
                    f"must be of type '{expected_type}', "
                    f"got '{type(value).__name__}'."
                ),
                module_key=module.key,
                field_path=f"modules.{module.key}.variables.{name}",
                context={
                    "variable": name,
                    "expected_type": expected_type,
                    "actual_type": type(value).__name__,
                },
                suggestion=(
                    f"Provide a value of type '{expected_type}' "
                    f"for variable '{name}'."
                ),
            )

    def _check_type(
        self,
        value: Any,
        expected_type: str,
    ) -> bool:
        """Check a variable type without accepting booleans as integers."""
        expected_python_type = TYPE_MAPPING.get(expected_type)

        if expected_python_type is None:
            return False

        if expected_python_type is int:
            return isinstance(value, int) and not isinstance(value, bool)

        return isinstance(value, expected_python_type)