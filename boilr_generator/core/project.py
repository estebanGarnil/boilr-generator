"""Resolved project domain model."""

from copy import deepcopy
from typing import Any

from pydantic import BaseModel, Field

from boilr_generator.core.capabilities import (
    CapabilityBinding,
    CapabilityProvider,
    CapabilityRequirement,
)
from boilr_generator.core.contributions import (
    Contribution,
    ExtensionPoint,
)
from boilr_generator.core.dependencies import DependencyGraph
from boilr_generator.core.module import ResolvedModule
from boilr_generator.manifest.schemas import ProjectInfo


class ResolvedProject(BaseModel):
    """Represents a completely resolved project."""

    project: ProjectInfo
    modules: list[ResolvedModule] = Field(default_factory=list)
    providers: list[CapabilityProvider] = Field(
        default_factory=list
    )
    requirements: list[CapabilityRequirement] = Field(
        default_factory=list
    )
    bindings: list[CapabilityBinding] = Field(
        default_factory=list
    )
    dependency_graph: DependencyGraph = Field(
        default_factory=DependencyGraph
    )
    extension_points: list[ExtensionPoint] = Field(
        default_factory=list
    )
    contributions: list[Contribution] = Field(
        default_factory=list
    )

    def get_module(
        self,
        key: str,
    ) -> ResolvedModule | None:
        return next(
            (
                module
                for module in self.modules
                if module.key == key
            ),
            None,
        )

    def has_module(self, key: str) -> bool:
        return self.get_module(key) is not None

    def list_module_keys(self) -> list[str]:
        return [
            module.key
            for module in self.modules
        ]

    def list_modules_by_type(
        self,
        module_type: str,
    ) -> list[ResolvedModule]:
        return [
            module
            for module in self.modules
            if module.type == module_type
        ]

    def ordered_modules(self) -> list[ResolvedModule]:
        """Return modules in resolved dependency order."""
        ordered_keys = self.dependency_graph.ordered_module_keys
        module_by_key = {
            module.key: module
            for module in self.modules
        }

        graph_contains_every_module = (
            len(ordered_keys) == len(self.modules)
            and set(ordered_keys) == set(module_by_key)
        )

        if graph_contains_every_module:
            return [
                module_by_key[module_key]
                for module_key in ordered_keys
            ]

        return sorted(
            self.modules,
            key=lambda module: module.priority,
        )

    def extension_point_for(
        self,
        module_key: str,
        key: str,
    ) -> ExtensionPoint | None:
        """Return one extension point exposed by a module."""
        return next(
            (
                extension_point
                for extension_point in self.extension_points
                if (
                    extension_point.module_key == module_key
                    and extension_point.key == key
                )
            ),
            None,
        )

    def contributions_for_target(
        self,
        module_key: str,
        extension_point: str | None = None,
    ) -> list[Contribution]:
        """Return contributions targeting one module."""
        return [
            contribution
            for contribution in self.contributions
            if (
                contribution.target_module_key == module_key
                and (
                    extension_point is None
                    or contribution.extension_point
                    == extension_point
                )
            )
        ]

    def providers_for(
        self,
        capability: str,
    ) -> list[CapabilityProvider]:
        """Return every provider for one capability."""
        return [
            provider
            for provider in self.providers
            if provider.capability == capability
        ]

    def requirements_for(
        self,
        capability: str,
    ) -> list[CapabilityRequirement]:
        """Return every requirement for one capability."""
        return [
            requirement
            for requirement in self.requirements
            if requirement.capability == capability
        ]

    def bindings_for_consumer(
        self,
        module_key: str,
    ) -> list[CapabilityBinding]:
        """Return every binding consumed by one module."""
        return [
            binding
            for binding in self.bindings
            if binding.consumer_module_key == module_key
        ]

    def bindings_for_provider(
        self,
        module_key: str,
    ) -> list[CapabilityBinding]:
        """Return every binding supplied by one module."""
        return [
            binding
            for binding in self.bindings
            if binding.provider_module_key == module_key
        ]

    def binding_context_for(
        self,
        module_key: str,
    ) -> dict[str, Any]:
        """Build the Jinja binding context for one consumer."""
        context: dict[str, Any] = {}

        module_requirements = [
            requirement
            for requirement in self.requirements
            if requirement.module_key == module_key
        ]

        for requirement in module_requirements:
            matching_bindings = [
                binding
                for binding in self.bindings
                if (
                    binding.consumer_module_key == module_key
                    and binding.binding_key
                    == requirement.binding_key
                    and binding.capability
                    == requirement.capability
                )
            ]

            if not matching_bindings:
                continue

            if requirement.unique:
                context[requirement.binding_key] = deepcopy(
                    matching_bindings[0].values
                )
            else:
                context[requirement.binding_key] = [
                    deepcopy(binding.values)
                    for binding in matching_bindings
                ]

        return context
