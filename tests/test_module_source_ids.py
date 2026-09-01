import pytest
from pydantic import ValidationError

from boilr_generator.modules.registry import (
    ModuleRegistry,
)
from boilr_generator.modules.schemas import (
    CopySource,
    ModuleSources,
    RenderSource,
)
from boilr_generator.paths import (
    get_builtin_modules_path,
)


@pytest.mark.parametrize(
    ("model", "payload"),
    [
        (
            CopySource,
            {
                "id": "application-files",
                "from": "files/apps",
                "to": "backend/apps",
            },
        ),
        (
            RenderSource,
            {
                "id": "settings-base",
                "from": "settings.py.j2",
                "to": "backend/settings.py",
            },
        ),
    ],
)
def test_source_models_accept_stable_identifier(
    model,
    payload,
):
    source = model.model_validate(payload)

    assert source.id == payload["id"]


@pytest.mark.parametrize(
    ("model", "payload"),
    [
        (
            CopySource,
            {
                "from": "files/apps",
                "to": "backend/apps",
            },
        ),
        (
            RenderSource,
            {
                "from": "settings.py.j2",
                "to": "backend/settings.py",
            },
        ),
    ],
)
def test_source_models_require_identifier(
    model,
    payload,
):
    with pytest.raises(ValidationError):
        model.model_validate(payload)


@pytest.mark.parametrize(
    "invalid_id",
    [
        "",
        "Settings",
        "settings_base",
        "settings base",
    ],
)
def test_source_models_reject_invalid_identifier(
    invalid_id,
):
    with pytest.raises(ValidationError):
        CopySource.model_validate(
            {
                "id": invalid_id,
                "from": "files",
                "to": "backend",
            }
        )


def test_module_sources_reject_duplicate_identifiers():
    with pytest.raises(
        ValidationError,
        match=(
            "Duplicate source identifiers "
            "are not allowed"
        ),
    ):
        ModuleSources.model_validate(
            {
                "copy": [
                    {
                        "id": "shared",
                        "from": "files",
                        "to": "backend",
                    }
                ],
                "render": [
                    {
                        "id": "shared",
                        "from": "template.j2",
                        "to": "backend/file.py",
                    }
                ],
            }
        )


def test_builtin_django_sources_have_stable_identifiers():
    registry = ModuleRegistry(
        get_builtin_modules_path()
    )
    django = registry.get("django")

    copy_ids = [
        source.id
        for source in django.sources.copy_sources
    ]
    render_ids = [
        source.id
        for source in django.sources.render
    ]

    assert copy_ids == [
        "apps",
        "config",
    ]
    assert render_ids == [
        "manage",
        "dockerfile",
        "requirements",
        "settings-base",
    ]

    all_ids = [
        *copy_ids,
        *render_ids,
    ]

    assert len(all_ids) == len(set(all_ids))