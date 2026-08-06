"""Resolved project domain model."""

from pydantic import BaseModel, Field

from boilr_generator.core.capabilities import (
    CapabilityBinding,
    CapabilityProvider,
    CapabilityRequirement,
)
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
        """Return the legacy priority-based module order."""
        return sorted(
            self.modules,
            key=lambda module: module.priority,
        )

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