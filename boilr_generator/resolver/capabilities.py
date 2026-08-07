"""Capability contract collection during project resolution."""

from boilr_generator.core.capabilities import (
    CapabilityProvider,
    CapabilityRequirement,
)
from boilr_generator.core.module import ResolvedModule
from boilr_generator.exceptions import TemplateRenderError
from boilr_generator.resolver.rendering import (
    NativeRenderFailure,
    render_native_value,
)


class CapabilityCollector:
    """Collect capability contracts from resolved modules."""

    def collect_providers(
        self,
        modules: list[ResolvedModule],
    ) -> list[CapabilityProvider]:
        """Collect and render every provided capability."""
        providers: list[CapabilityProvider] = []

        for module in modules:
            for index, provision in enumerate(
                module.manifest.provides
            ):
                field_path = (
                    f"modules.{module.key}."
                    f"provides[{index}].values"
                )

                try:
                    values = render_native_value(
                        provision.values,
                        module.variables,
                        field_path=field_path,
                    )
                except NativeRenderFailure as failure:
                    error = failure.error

                    raise TemplateRenderError(
                        (
                            "Unable to render capability provider "
                            f"value at '{failure.field_path}': "
                            f"{error}"
                        ),
                        module_key=module.key,
                        field_path=failure.field_path,
                        context={
                            "target": "capability_provider",
                            "capability": provision.capability,
                            "error_type": type(error).__name__,
                        },
                        suggestion=(
                            "Check the capability value template "
                            "and ensure every referenced variable "
                            "is declared."
                        ),
                    ) from error

                providers.append(
                    CapabilityProvider(
                        module_key=module.key,
                        capability=provision.capability,
                        values=values,
                    )
                )

        return providers

    def collect_requirements(
        self,
        modules: list[ResolvedModule],
    ) -> list[CapabilityRequirement]:
        """Collect every required capability."""
        requirements: list[CapabilityRequirement] = []

        for module in modules:
            for requirement in module.manifest.requires:
                requirements.append(
                    CapabilityRequirement(
                        module_key=module.key,
                        binding_key=requirement.binding_key,
                        capability=requirement.capability,
                        optional=requirement.optional,
                        unique=requirement.unique,
                        contract=dict(requirement.contract),
                    )
                )

        return requirements