import pytest

from boilr_generator.core.exceptions import (
    ModuleNotFoundError as LegacyModuleNotFoundError,
)
from boilr_generator.exceptions import (
    AmbiguousProviderError,
    BoilrError,
    ContributionConflictError,
    DuplicateModuleError,
    ManifestNotFoundError,
    MissingCapabilityError,
    MissingRequirementError,
    ModuleNotFoundError,
    OutputDirectoryError,
    TemplateRenderError,
)


@pytest.mark.parametrize(
    "exception_type",
    [
        ManifestNotFoundError,
        ModuleNotFoundError,
        DuplicateModuleError,
        MissingRequirementError,
        MissingCapabilityError,
        AmbiguousProviderError,
        ContributionConflictError,
        TemplateRenderError,
        OutputDirectoryError,
    ],
)
def test_all_boilr_errors_inherit_from_root(exception_type):
    assert issubclass(exception_type, BoilrError)


def test_boilr_error_contains_structured_context():
    error = MissingRequirementError(
        'Module "django" requires a database.',
        module_key="django",
        field_path="requirements.database",
        context={
            "required_type": "database",
        },
        suggestion='Select a module of type "database".',
    )

    assert error.code == "missing_requirement"
    assert error.message == 'Module "django" requires a database.'
    assert str(error) == 'Module "django" requires a database.'
    assert error.module_key == "django"
    assert error.field_path == "requirements.database"
    assert error.context == {
        "required_type": "database",
    }
    assert error.suggestion == 'Select a module of type "database".'


def test_error_context_is_not_shared_between_instances():
    first_error = BoilrError("First error")
    second_error = BoilrError("Second error")

    first_error.context["value"] = 1

    assert second_error.context == {}


def test_legacy_exception_import_reuses_canonical_class():
    assert LegacyModuleNotFoundError is ModuleNotFoundError


def test_custom_exception_can_be_raised():
    with pytest.raises(ModuleNotFoundError):
        raise ModuleNotFoundError(
            "Module not found: django",
            module_key="django",
        )