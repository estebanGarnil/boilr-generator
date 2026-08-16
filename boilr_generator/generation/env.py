"""Environment variable generation."""

import re
from typing import Any

from jinja2 import Environment, StrictUndefined
from jinja2.exceptions import TemplateError

from boilr_generator.core.project import ResolvedProject
from boilr_generator.exceptions import (
    EnvironmentConflictError,
    InvalidEnvironmentVariableError,
    TemplateRenderError,
)
from boilr_generator.generation.context import (
    build_module_context,
)

JINJA_ENVIRONMENT = Environment(
    autoescape=False,
    undefined=StrictUndefined,
)

ENV_VARIABLE_NAME_PATTERN = re.compile(
    r"^[A-Za-z_][A-Za-z0-9_]*$"
)

FORBIDDEN_VALUE_CHARACTERS = {
    "\n": "line_feed",
    "\r": "carriage_return",
    "\x00": "null_byte",
}


class EnvGenerator:
    """Generate environment variables from module exports."""

    def generate(
        self,
        project: ResolvedProject,
    ) -> dict[str, str]:
        """Render and merge environment variable contributions."""
        env: dict[str, str] = {}
        variable_origins: dict[str, str] = {}

        for module in project.ordered_modules():
            exports = module.manifest.exports

            if exports is None or exports.env is None:
                continue

            context = build_module_context(
                project,
                module,
            )

            for key, value in exports.env.root.items():
                field_path = f"modules.{module.key}.exports.env.{key}"

                self._validate_variable_name(
                    key=key,
                    module_key=module.key,
                    field_path=field_path,
                )

                rendered_value = self._render_value(
                    value,
                    context,
                    module_key=module.key,
                    field_path=field_path,
                )

                self._validate_variable_value(
                    key=key,
                    value=rendered_value,
                    module_key=module.key,
                    field_path=field_path,
                )

                if key in env and env[key] != rendered_value:
                    raise EnvironmentConflictError(
                        (
                            f"Environment variable '{key}' is exported "
                            "with conflicting values by modules "
                            f"'{variable_origins[key]}' and '{module.key}'."
                        ),
                        module_key=module.key,
                        field_path=field_path,
                        context={
                            "variable": key,
                            "first_module": variable_origins[key],
                            "conflicting_module": module.key,
                        },
                        suggestion=(
                            f"Use the same value for '{key}' in both "
                            "modules or rename one of the exports."
                        ),
                    )

                if key not in env:
                    env[key] = rendered_value
                    variable_origins[key] = module.key

        return env

    def _validate_variable_name(
        self,
        *,
        key: str,
        module_key: str,
        field_path: str,
    ) -> None:
        """Validate a portable environment variable name."""
        if ENV_VARIABLE_NAME_PATTERN.fullmatch(key):
            return

        raise InvalidEnvironmentVariableError(
            f"Invalid environment variable name: '{key}'.",
            module_key=module_key,
            field_path=field_path,
            context={
                "reason": "invalid_name",
                "variable": key,
                "expected_pattern": (
                    ENV_VARIABLE_NAME_PATTERN.pattern
                ),
            },
            suggestion=(
                "Use letters, digits, and underscores, starting "
                "with a letter or underscore."
            ),
        )

    def _validate_variable_value(
        self,
        *,
        key: str,
        value: str,
        module_key: str,
        field_path: str,
    ) -> None:
        """Reject values that could inject additional env lines."""
        invalid_characters = [
            character_name
            for character, character_name in (
                FORBIDDEN_VALUE_CHARACTERS.items()
            )
            if character in value
        ]

        if not invalid_characters:
            return

        raise InvalidEnvironmentVariableError(
            (
                f"Environment variable '{key}' contains "
                "characters that cannot be serialized safely."
            ),
            module_key=module_key,
            field_path=field_path,
            context={
                "reason": "invalid_value",
                "variable": key,
                "invalid_characters": invalid_characters,
            },
            suggestion=(
                "Remove line breaks and null bytes from the "
                "environment variable value."
            ),
        )

    def _render_value(
        self,
        value: Any,
        context: dict[str, Any],
        *,
        module_key: str,
        field_path: str,
    ) -> str:
        """Render one environment variable value using strict Jinja."""
        if not isinstance(value, str):
            return str(value)

        try:
            template = JINJA_ENVIRONMENT.from_string(value)
            return template.render(**context)
        except TemplateError as error:
            raise TemplateRenderError(
                (
                    f"Unable to render environment variable "
                    f"'{field_path}': {error}"
                ),
                module_key=module_key,
                field_path=field_path,
                context={
                    "target": "environment",
                    "error_type": type(error).__name__,
                },
                suggestion=(
                    "Check the template syntax and ensure every referenced "
                    "variable is declared by the module."
                ),
            ) from error