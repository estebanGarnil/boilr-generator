from pathlib import Path

PACKAGE_ROOT = Path(__file__).resolve().parent 


def get_builtin_modules_path() -> Path:
    return PACKAGE_ROOT / "templates"