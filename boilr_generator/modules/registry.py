from pathlib import Path 

from boilr_generator.modules.loader import load_module_from_yaml
from boilr_generator.modules.schemas import ModuleManifest
from boilr_generator.core.exceptions import DuplicateModuleError, ModuleNotFoundError

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
                raise DuplicateModuleError(f"Duplicate module key: {key}")
            
            self.modules[key] = module
            self.module_path[key] = module_file.parent

    def get(self, key: str) -> ModuleManifest:
        if key not in self.modules: 
            raise ModuleNotFoundError(f"Module not found: {key}")
        return self.modules[key]
    
    def get_path(self, key: str) -> Path:
        if key not in self.module_path:
            raise ModuleNotFoundError(f"Module path not found: {key}")
        return self.module_path[key]
    
    def has(self, key:str) -> bool:
        return key in self.modules
    
    def list_keys(self) -> list[str]:
        return list(self.modules.keys())
    
    def list_by_type(self, module_type: str) -> list[ModuleManifest]:
        return [m for m in self.modules.values() if m.meta.type == module_type]
    
    