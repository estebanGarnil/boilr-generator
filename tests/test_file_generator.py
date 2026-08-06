from pathlib import Path

import pytest
from boilr_generator.exceptions import (
    SourceNotFoundError,
    TemplateRenderError,
)
from boilr_generator.generation.files import FileGenerator
from boilr_generator.modules.schemas import CopySource, RenderSource


def test_file_generator_reports_missing_copy_source(
    resolved_project,
    tmp_path,
):
    project = resolved_project.model_copy(deep=True)
    postgres = project.get_module("postgres")

    assert postgres is not None

    postgres.manifest.sources.copy_sources = [
        CopySource.model_validate(
            {
                "from": "missing-source",
                "to": "generated",
                "strategy": "merge",
            }
        )
    ]

    with pytest.raises(SourceNotFoundError) as error_info:
        FileGenerator().copy_sources(project, tmp_path)

    error = error_info.value

    assert error.code == "source_not_found"
    assert error.module_key == "postgres"
    assert error.field_path == "modules.postgres.sources.copy[0].from"
    assert error.context["source_kind"] == "copy"
    assert error.context["source_path"].endswith("missing-source")
    assert error.suggestion is not None


def test_file_generator_reports_missing_template(
    resolved_project,
    tmp_path,
):
    project = resolved_project.model_copy(deep=True)
    postgres = project.get_module("postgres")

    assert postgres is not None

    postgres.manifest.sources.render = [
        RenderSource.model_validate(
            {
                "from": "missing-template.j2",
                "to": "generated.txt",
            }
        )
    ]

    with pytest.raises(SourceNotFoundError) as error_info:
        FileGenerator().render_sources(project, tmp_path)

    error = error_info.value

    assert error.code == "source_not_found"
    assert error.module_key == "postgres"
    assert error.field_path == "modules.postgres.sources.render[0].from"
    assert error.context["source_kind"] == "template"
    assert error.context["source_path"].endswith(
        "missing-template.j2"
    )


def test_file_generator_reports_template_render_error(
    tmp_path: Path,
):
    template_path = tmp_path / "broken.txt.j2"
    destination_path = tmp_path / "output" / "broken.txt"

    template_path.write_text(
        "{{ missing_template_value }}",
        encoding="utf-8",
    )

    with pytest.raises(TemplateRenderError) as error_info:
        FileGenerator()._render_template(
            template_path=template_path,
            destination_path=destination_path,
            context={},
            module_key="postgres",
            field_path="modules.postgres.sources.render[0].from",
        )

    error = error_info.value

    assert error.code == "template_render_error"
    assert error.module_key == "postgres"
    assert error.field_path == (
        "modules.postgres.sources.render[0].from"
    )
    assert error.context["target"] == "file"
    assert error.context["error_type"] == "UndefinedError"
    assert error.context["source_path"] == str(template_path)
    assert error.context["destination_path"] == str(
        destination_path
    )
    assert destination_path.exists() is False