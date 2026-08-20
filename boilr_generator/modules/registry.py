from pathlib import Path

from boilr_generator.exceptions import (
    DuplicateModuleError,
    ModuleNotFoundError,
)
from boilr_generator.modules.loader import load_module_from_yaml
from boilr_generator.modules.schemas import ModuleManifest


class ModuleRegistry: 
    def __init__(self, base_path: str | Path):
        self.base_path = Path(base_path)
        self.modules: dict[str, ModuleManifest] = {}
        self.module_path: dict[str, Path] = {}

        self._load_modules()

    def _load_modules(self):
        for module_file in self.base_path.rglob("module.yml"):
            module = load_module_from_yaml(module_file)

            key = module.meta.key 

            if key in self.modules:
                first_module_file = (
                    self.module_path[key] / "module.yml"
                )

                raise DuplicateModuleError(
                    f"Duplicate module key '{key}'.",
                    module_key=key,
                    field_path="meta.key",
                    context={
                        "module_key": key,
                        "first_module_path": str(
                            first_module_file
                        ),
                        "duplicate_module_path": str(
                            module_file
                        ),
                    },
                    suggestion=(
                        "Give every module manifest a unique "
                        "'meta.key' value."
                    ),
                )
            
            self.modules[key] = module
            self.module_path[key] = module_file.parent

    def get(self, key: str) -> ModuleManifest:
        if key not in self.modules:
            raise ModuleNotFoundError(
                f"Module not found: {key}",
                module_key=key,
                field_path=f"modules.{key}",
                context={
                    "requested_module": key,
                    "available_modules": sorted(
                        self.modules
                    ),
                },
                suggestion=(
                    "Check the project manifest and the "
                    "configured module registry."
                ),
            )

        return self.modules[key]
    
    def get_path(self, key: str) -> Path:
        if key not in self.module_path:
            raise ModuleNotFoundError(
                f"Module path not found: {key}",
                module_key=key,
                field_path=f"modules.{key}",
                context={
                    "requested_module": key,
                    "available_modules": sorted(
                        self.module_path
                    ),
                },
                suggestion=(
                    "Check the project manifest and the "
                    "configured module registry."
                ),
            )

        return self.module_path[key]
    
    def has(self, key:str) -> bool:
        return key in self.modules
    
    def list_keys(self) -> list[str]:
        return list(self.modules.keys())
    
    def list_by_type(self, module_type: str) -> list[ModuleManifest]:
        return [m for m in self.modules.values() if m.meta.type == module_type]
    
    