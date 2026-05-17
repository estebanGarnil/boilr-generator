import pytest

from boilr_generator.core import (
    BoilrError,
    DuplicateModuleError,
    ModuleNotFoundError,
    ModuleVariableError,
)


def test_custom_exceptions_inherit_from_boilr_error():
    assert issubclass(DuplicateModuleError, BoilrError)
    assert issubclass(ModuleNotFoundError, BoilrError)
    assert issubclass(ModuleVariableError, BoilrError)


def test_custom_exception_can_be_raised():
    with pytest.raises(ModuleNotFoundError):
        raise ModuleNotFoundError("Module not found: django")