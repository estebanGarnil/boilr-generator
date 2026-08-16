"""Validation rules used during project resolution."""

from typing import Any

from boilr_generator.core import ResolvedModule
from boilr_generator.exceptions import (
    InvalidOptionTypeError,
    InvalidVariableTypeError,
    MissingVariableError,
    UnknownOptionError,
    UnknownVariableError,
)

TYPE_MAPPING: dict[str, type] = {
    "string": str,
    "int": int,
    "boolean": bool,
    "list": list,
}


class ProjectValidator:
    """Validate resolved modules before assembling the project."""

    def validate_variables(
        self,
        modules: list[ResolvedModule],
    ) -> None:
        """Validate variable names and required values."""
        for module in modules:
            self._validate_module_variables(module)

    def _validate_module_variables(
        self,
        module: ResolvedModule,
    ) -> None:
        """Validate the variables of one module."""
        unknown_variables = sorted(
            set(module.variables)
            - set(module.manifest.variables.keys())
        )

        if unknown_variables:
            variable = unknown_variables[0]

            raise UnknownVariableError(
                (
                    f"Module '{module.key}' received unknown "
                    f"variable '{variable}'."
                ),
                module_key=module.key,
                field_path=(
                    f"modules.{module.key}.variables.{variable}"
                ),
                context={
                    "variable": variable,
                    "available_variables": sorted(
                        module.manifest.variables.keys()
                    ),
                },
                suggestion=(
                    f"Remove variable '{variable}' or use a variable "
                    f"declared by module '{module.key}'."
                ),
            )

        for name, definition in module.manifest.variables.items():
            if not definition.required or name in module.variables:
                continue

            raise MissingVariableError(
                (
                    f"Module '{module.key}' requires variable "
                    f"'{name}', but it was not provided and "
                    "has no default."
                ),
                module_key=module.key,
                field_path=(
                    f"modules.{module.key}.variables.{name}"
                ),
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
                    f"Variable '{name}' in module "
                    f"'{module.key}' must be of type "
                    f"'{expected_type}', got "
                    f"'{type(value).__name__}'."
                ),
                module_key=module.key,
                field_path=(
                    f"modules.{module.key}.variables.{name}"
                ),
                context={
                    "variable": name,
                    "expected_type": expected_type,
                    "actual_type": type(value).__name__,
                },
                suggestion=(
                    f"Provide a value of type "
                    f"'{expected_type}' for variable '{name}'."
                ),
            )

    def validate_options(
        self,
        modules: list[ResolvedModule],
    ) -> None:
        """Validate option names for every selected module."""
        for module in modules:
            self._validate_module_options(module)

    def _validate_module_options(
        self,
        module: ResolvedModule,
    ) -> None:
        """Validate the options of one module."""
        unknown_options = sorted(
            set(module.options)
            - set(module.manifest.options.keys())
        )

        if not unknown_options:
            return

        option = unknown_options[0]

        raise UnknownOptionError(
            (
                f"Module '{module.key}' received unknown "
                f"option '{option}'."
            ),
            module_key=module.key,
            field_path=(
                f"modules.{module.key}.options.{option}"
            ),
            context={
                "option": option,
                "available_options": sorted(
                    module.manifest.options.keys()
                ),
            },
            suggestion=(
                f"Remove option '{option}' or use an option "
                f"declared by module '{module.key}'."
            ),
        )

    def validate_option_types(
        self,
        modules: list[ResolvedModule],
    ) -> None:
        """Validate the types of all resolved module options."""
        for module in modules:
            self._validate_module_option_types(module)

    def _validate_module_option_types(
        self,
        module: ResolvedModule,
    ) -> None:
        """Validate the resolved option types of one module."""
        for name, value in module.options.items():
            definition = module.manifest.options.get(name)

            if definition is None:
                continue

            expected_type = definition.type

            if self._check_type(value, expected_type):
                continue

            raise InvalidOptionTypeError(
                (
                    f"Option '{name}' in module "
                    f"'{module.key}' must be of type "
                    f"'{expected_type}', got "
                    f"'{type(value).__name__}'."
                ),
                module_key=module.key,
                field_path=(
                    f"modules.{module.key}.options.{name}"
                ),
                context={
                    "option": name,
                    "expected_type": expected_type,
                    "actual_type": type(value).__name__,
                },
                suggestion=(
                    f"Provide a value of type "
                    f"'{expected_type}' for option '{name}'."
                ),
            )

    def _check_type(
        self,
        value: Any,
        expected_type: str,
    ) -> bool:
        """Check a type without accepting booleans as integers."""
        expected_python_type = TYPE_MAPPING.get(
            expected_type
        )

        if expected_python_type is None:
            return False

        if expected_python_type is int:
            return (
                isinstance(value, int)
                and not isinstance(value, bool)
            )

        return isinstance(value, expected_python_type)