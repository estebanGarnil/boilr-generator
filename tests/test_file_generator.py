from pathlib import Path

import pytest
from boilr_generator.exceptions import (
    SourceReadError,
    TemplateRenderError,
)
from boilr_generator.generation.files import FileGenerator
from boilr_generator.modules.schemas import CopySource


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
        FileGenerator().render_template_content(
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

def test_file_generator_prepares_template_without_writing(
    tmp_path: Path,
):
    template_path = tmp_path / "example.txt.j2"
    destination_path = tmp_path / "output" / "example.txt"

    template_path.write_text(
        "Hello {{ name }}",
        encoding="utf-8",
    )

    content = FileGenerator().render_template_content(
        template_path=template_path,
        destination_path=destination_path,
        context={
            "name": "Boilr",
        },
        module_key="django",
        field_path=(
            "modules.django.sources.render[0].from"
        ),
    )

    assert content == "Hello Boilr"
    assert destination_path.exists() is False

def test_copy_source_rejects_unknown_strategy():
    with pytest.raises(
        ValueError,
        match="Input should be 'merge', 'skip' or 'replace'",
    ):
        CopySource.model_validate(
            {
                "from": "files",
                "to": "generated",
                "strategy": "unknown",
            }
        )

def test_file_generator_wraps_template_read_error(
    tmp_path: Path,
    monkeypatch,
):
    template_path = tmp_path / "template.j2"
    destination_path = tmp_path / "generated.txt"

    template_path.write_text(
        "content",
        encoding="utf-8",
    )

    original_read_text = Path.read_text

    def fail_template_read(
        path,
        *args,
        **kwargs,
    ):
        if path == template_path:
            raise PermissionError(13, "Access denied")

        return original_read_text(
            path,
            *args,
            **kwargs,
        )

    monkeypatch.setattr(
        Path,
        "read_text",
        fail_template_read,
    )

    with pytest.raises(SourceReadError) as error_info:
        FileGenerator().render_template_content(
            template_path=template_path,
            destination_path=destination_path,
            context={},
            module_key="example",
            field_path=(
                "modules.example.sources.render[0].from"
            ),
        )

    error = error_info.value

    assert isinstance(error.__cause__, PermissionError)
    assert error.code == "source_read_error"
    assert error.context["reason"] == "source_read_failed"
    assert error.context["source_kind"] == "template"
    assert error.context["errno"] == 13
    assert destination_path.exists() is False


def test_file_generator_rejects_non_utf8_template(
    tmp_path: Path,
):
    template_path = tmp_path / "template.j2"
    destination_path = tmp_path / "generated.txt"

    template_path.write_bytes(b"\xff\xfe")

    with pytest.raises(SourceReadError) as error_info:
        FileGenerator().render_template_content(
            template_path=template_path,
            destination_path=destination_path,
            context={},
            module_key="example",
            field_path=(
                "modules.example.sources.render[0].from"
            ),
        )

    error = error_info.value

    assert isinstance(error.__cause__, UnicodeDecodeError)
    assert error.context["reason"] == "invalid_encoding"
    assert error.context["source_kind"] == "template"
    assert destination_path.exists() is False