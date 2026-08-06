"""Capability contract collection during project resolution."""

from typing import Any

from jinja2 import StrictUndefined, Undefined
from jinja2.exceptions import TemplateError
from jinja2.nativetypes import NativeEnvironment

from boilr_generator.core.capabilities import (
    CapabilityProvider,
    CapabilityRequirement,
)
from boilr_generator.core.module import ResolvedModule
from boilr_generator.exceptions import TemplateRenderError

JINJA_ENVIRONMENT = NativeEnvironment(
    autoescape=False,
    undefined=StrictUndefined,
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
                    f"modules.{module.key}.provides[{index}].values"
                )

                values = self._render_value(
                    provision.values,
                    module.variables,
                    module_key=module.key,
                    capability=provision.capability,
                    field_path=field_path,
                )

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
                    )
                )

        return requirements

    def _render_value(
        self,
        value: Any,
        context: dict[str, Any],
        *,
        module_key: str,
        capability: str,
        field_path: str,
    ) -> Any:
        """Render capability values recursively using native Jinja."""
        if isinstance(value, str):
            try:
                template = JINJA_ENVIRONMENT.from_string(value)
                rendered_value = template.render(**context)

                if isinstance(rendered_value, Undefined):
                    str(rendered_value)

                return rendered_value
            except TemplateError as error:
                raise TemplateRenderError(
                    (
                        "Unable to render capability provider "
                        f"value at '{field_path}': {error}"
                    ),
                    module_key=module_key,
                    field_path=field_path,
                    context={
                        "target": "capability_provider",
                        "capability": capability,
                        "error_type": type(error).__name__,
                    },
                    suggestion=(
                        "Check the capability value template and "
                        "ensure every referenced variable is declared."
                    ),
                ) from error

        if isinstance(value, list):
            return [
                self._render_value(
                    item,
                    context,
                    module_key=module_key,
                    capability=capability,
                    field_path=f"{field_path}[{index}]",
                )
                for index, item in enumerate(value)
            ]

        if isinstance(value, dict):
            return {
                key: self._render_value(
                    item,
                    context,
                    module_key=module_key,
                    capability=capability,
                    field_path=f"{field_path}.{key}",
                )
                for key, item in value.items()
            }

        return value