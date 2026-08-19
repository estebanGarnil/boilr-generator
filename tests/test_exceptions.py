import pytest
from boilr_generator.core.exceptions import (
    ModuleNotFoundError as LegacyModuleNotFoundError,
)
from boilr_generator.exceptions import (
    AmbiguousProviderError,
    BoilrError,
    ContributionConflictError,
    DuplicateModuleError,
    InvalidEnvironmentVariableError,
    InvalidOptionTypeError,
    ManifestNotFoundError,
    MissingCapabilityError,
    MissingRequirementError,
    ModuleNotFoundError,
    OutputDirectoryError,
    ProviderSelectionError,
    SourceReadError,
    StaleGenerationPlanError,
    TemplateRenderError,
    UnknownOptionError,
    UnknownVariableError,
    UnsafePathError,
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
        InvalidOptionTypeError,
        UnknownOptionError,
        UnknownVariableError,
        UnsafePathError,
        SourceReadError,
        InvalidEnvironmentVariableError,
        ProviderSelectionError,
        StaleGenerationPlanError,
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

def test_boilr_error_serializes_complete_contract():
    error = ProviderSelectionError(
        "No provider matches the requested criteria.",
        module_key="django",
        field_path="modules.django.bindings.database",
        context={
            "reason": "no_matching_provider",
            "candidates": ["postgres"],
        },
        suggestion="Change the provider selection criteria.",
    )

    assert error.to_dict() == {
        "code": "provider_selection_error",
        "message": (
            "No provider matches the requested criteria."
        ),
        "module_key": "django",
        "field_path": (
            "modules.django.bindings.database"
        ),
        "context": {
            "reason": "no_matching_provider",
            "candidates": ["postgres"],
        },
        "suggestion": (
            "Change the provider selection criteria."
        ),
    }


def test_boilr_error_serialization_preserves_empty_fields():
    error = BoilrError("Unexpected Boilr error.")

    assert error.to_dict() == {
        "code": "boilr_error",
        "message": "Unexpected Boilr error.",
        "module_key": None,
        "field_path": None,
        "context": {},
        "suggestion": None,
    }


def test_boilr_error_serialization_copies_context():
    error = BoilrError(
        "Unexpected Boilr error.",
        context={
            "reason": "unexpected",
        },
    )

    serialized = error.to_dict()
    serialized["context"]["additional"] = True

    assert error.context == {
        "reason": "unexpected",
    }

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