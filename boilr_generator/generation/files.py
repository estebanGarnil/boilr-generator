"""File copying and template rendering."""

from pathlib import Path
from typing import Any

from jinja2 import Environment, StrictUndefined
from jinja2.exceptions import TemplateError


from boilr_generator.exceptions import (
    SourceNotFoundError,
    TemplateRenderError,
)

JINJA_ENVIRONMENT = Environment(
    autoescape=False,
    undefined=StrictUndefined,
)


class FileGenerator:
    """Render template contents without writing files."""

    def render_template_content(
        self,
        template_path: Path,
        destination_path: Path,
        context: dict[str, Any],
        *,
        module_key: str,
        field_path: str,
    ) -> str:
        """Render a template without writing its destination."""
        if not template_path.is_file():
            raise SourceNotFoundError(
                f"Template not found: {template_path}",
                module_key=module_key,
                field_path=field_path,
                context={
                    "source_path": str(template_path),
                    "source_kind": "template",
                },
                suggestion=(
                    "Check the template path declared in the "
                    "module manifest and ensure the template "
                    "is packaged."
                ),
            )

        template_content = template_path.read_text(
            encoding="utf-8"
        )

        try:
            template = JINJA_ENVIRONMENT.from_string(
                template_content
            )
            return template.render(**context)
        except TemplateError as error:
            raise TemplateRenderError(
                (
                    f"Unable to render template "
                    f"'{template_path}': {error}"
                ),
                module_key=module_key,
                field_path=field_path,
                context={
                    "target": "file",
                    "source_path": str(template_path),
                    "destination_path": str(
                        destination_path
                    ),
                    "error_type": type(error).__name__,
                },
                suggestion=(
                    "Check the template syntax and ensure "
                    "every referenced variable is declared "
                    "by the module."
                ),
            ) from error
