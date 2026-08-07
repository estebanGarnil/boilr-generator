"""Shared native Jinja rendering for resolver values."""

from typing import Any

from jinja2 import StrictUndefined, Undefined
from jinja2.exceptions import TemplateError
from jinja2.nativetypes import NativeEnvironment

JINJA_ENVIRONMENT = NativeEnvironment(
    autoescape=False,
    undefined=StrictUndefined,
)


class NativeRenderFailure(Exception):
    """Internal failure preserving the exact rendered field path."""

    def __init__(
        self,
        *,
        field_path: str,
        error: TemplateError,
    ) -> None:
        super().__init__(str(error))
        self.field_path = field_path
        self.error = error


def render_native_value(
    value: Any,
    context: dict[str, Any],
    *,
    field_path: str,
) -> Any:
    """Render strings recursively while preserving native types."""
    if isinstance(value, str):
        try:
            template = JINJA_ENVIRONMENT.from_string(value)
            rendered_value = template.render(**context)

            if isinstance(rendered_value, Undefined):
                str(rendered_value)

            return rendered_value
        except TemplateError as error:
            raise NativeRenderFailure(
                field_path=field_path,
                error=error,
            ) from error

    if isinstance(value, list):
        return [
            render_native_value(
                item,
                context,
                field_path=f"{field_path}[{index}]",
            )
            for index, item in enumerate(value)
        ]

    if isinstance(value, dict):
        return {
            key: render_native_value(
                item,
                context,
                field_path=f"{field_path}.{key}",
            )
            for key, item in value.items()
        }

    return value