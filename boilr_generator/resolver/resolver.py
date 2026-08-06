"""Project manifest resolver."""

from boilr_generator.core import ResolvedModule
from boilr_generator.core.project import ResolvedProject
from boilr_generator.manifest.schemas import ProjectManifest
from boilr_generator.modules.registry import ModuleRegistry
from boilr_generator.resolver.bindings import CapabilityBinder
from boilr_generator.resolver.capabilities import CapabilityCollector
from boilr_generator.resolver.merger import ProjectMerger
from boilr_generator.resolver.validator import ProjectValidator


class Resolver:
    """Resolve a project manifest into fully configured modules."""

    def __init__(self, registry: ModuleRegistry):
        self.registry = registry
        self.validator = ProjectValidator()
        self.merger = ProjectMerger()
        self.capability_collector = CapabilityCollector()
        self.capability_binder = CapabilityBinder()

    def resolve(self, manifest: ProjectManifest) -> ResolvedProject:
        """Resolve and validate all modules selected by a manifest."""
        resolved_modules = self._resolve_modules(manifest)

        self.validator.validate_requirements(resolved_modules)
        self.validator.validate_compatibility(resolved_modules)
        self.validator.validate_variables(resolved_modules)
        self.validator.validate_variable_types(resolved_modules)

        providers = self.capability_collector.collect_providers(
            resolved_modules
        )
        requirements = (
            self.capability_collector.collect_requirements(
                resolved_modules
            )
        )

        bindings = self.capability_binder.bind(
            providers,
            requirements,
        )

        return ResolvedProject(
            project=manifest.project,
            modules=resolved_modules,
            providers=providers,
            requirements=requirements,
            bindings=bindings,
        )

    def _resolve_modules(
        self,
        manifest: ProjectManifest,
    ) -> list[ResolvedModule]:
        """Load and merge every module selected by the project."""
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