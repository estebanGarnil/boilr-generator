"""File copying and template rendering."""

from pathlib import Path
from typing import Any

from jinja2 import Environment, StrictUndefined
from jinja2.exceptions import TemplateError

from boilr_generator.core.project import ResolvedProject
from boilr_generator.exceptions import (
    SourceNotFoundError,
    TemplateRenderError,
)
from boilr_generator.generation.context import (
    build_module_context,
)

JINJA_ENVIRONMENT = Environment(
    autoescape=False,
    undefined=StrictUndefined,
)


class FileGenerator:
    """Copy and render module source files."""

    def render_sources(
        self,
        project: ResolvedProject,
        output_path: str | Path,
    ) -> None:
        """Render every template declared by the modules."""
        output_path = Path(output_path)

        for module in project.ordered_modules():
            context = build_module_context(
                project,
                module,
            )

            for index, source in enumerate(
                module.manifest.sources.render
            ):
                template_path = (
                    module.resolve_source_path(source.from_)
                )
                destination_path = output_path / source.to
                field_path = (
                    f"modules.{module.key}."
                    f"sources.render[{index}].from"
                )

                self._render_template(
                    template_path=template_path,
                    destination_path=destination_path,
                    context=context,
                    module_key=module.key,
                    field_path=field_path,
                )

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

    def _render_template(
        self,
        template_path: Path,
        destination_path: Path,
        context: dict[str, Any],
        *,
        module_key: str,
        field_path: str,
    ) -> None:
        """Render and write one template."""
        rendered_content = self.render_template_content(
            template_path=template_path,
            destination_path=destination_path,
            context=context,
            module_key=module_key,
            field_path=field_path,
        )

        destination_path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )
        destination_path.write_text(
            rendered_content,
            encoding="utf-8",
        )