from boilr_generator.core import ResolvedModule
from boilr_generator.core.project import ResolvedProject
from boilr_generator.manifest.schemas import ProjectManifest
from boilr_generator.modules.registry import ModuleRegistry
from boilr_generator.resolver.validator import ProjectValidator
from boilr_generator.resolver.merger import ProjectMerger

class Resolver:
    def __init__(self, registry: ModuleRegistry):
        self.registry = registry 
        self.validator = ProjectValidator()
        self.merger = ProjectMerger()


    def resolve(self, manifest: ProjectManifest) -> ResolvedProject:
        resolved_modules: list[ResolvedModule] = self._resolve_modules(manifest)

        self.validator.validate_requirements(resolved_modules)
        self.validator._validate_compatibility(resolved_modules)
        self.validator.validate_variables(resolved_modules)
        self.validator.validate_variable_types(resolved_modules)

        return ResolvedProject(
            project=manifest.project,
            modules=resolved_modules,
        )

    def _resolve_modules(self, manifest: ProjectManifest) -> list[ResolvedModule]:
        resolved_modules: list[ResolvedModule] = []

        for project_module in manifest.modules: 
            module_manifest = self.registry.get(project_module.key)

            variables = self.merger.merge_variables(
                module_manifest=module_manifest,
                project_module=project_module,
            )

            options = self.merger.merge_options(
                module_manifest=module_manifest,
                project_module=project_module,
            )

            resolved_module = ResolvedModule(
                manifest=module_manifest,
                module_path=self.registry.get_path(project_module.key),
                variables=variables,
                options=options,
            )

            resolved_modules.append(resolved_module)

        return resolved_modules