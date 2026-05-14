from typing import Any 

from boilr_generator.manifest.schemas import ProjectModule
from boilr_generator.modules.schemas import ModuleManifest


class ProjectMerger:
    def merge_variables(
            self, 
            module_manifest: ModuleManifest,
            project_module: ProjectModule,
    ) -> dict[str, Any]:
        merged: dict[str, Any] = {}

        for name, definition in module_manifest.variables.items():
            if definition.default is not None:
                merged[name] = definition.default
        
        merged.update(project_module.variables)

        return merged

    def merge_options(
            self, 
            module_manifest: ModuleManifest, 
            project_module: ProjectModule,
    ) -> dict[str, Any]: 
        merged: dict[str, Any] = {}

        for name, definition in module_manifest.options.items():
            if definition.default is not None:
                merged[name] = definition.default
        
        merged.update(project_module.options)

        return merged