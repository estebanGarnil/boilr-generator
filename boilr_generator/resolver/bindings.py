"""Capability provider selection and binding creation."""

from copy import deepcopy

from boilr_generator.core.capabilities import (
    CapabilityBinding,
    CapabilityProvider,
    CapabilityRequirement,
)
from boilr_generator.exceptions import (
    AmbiguousProviderError,
    MissingCapabilityError,
)


class CapabilityBinder:
    """Bind capability requirements to matching providers."""

    def bind(
        self,
        providers: list[CapabilityProvider],
        requirements: list[CapabilityRequirement],
    ) -> list[CapabilityBinding]:
        """Resolve every requirement into zero or more bindings."""
        bindings: list[CapabilityBinding] = []

        for requirement in requirements:
            candidates = [
                provider
                for provider in providers
                if provider.capability == requirement.capability
            ]

            if not candidates:
                if requirement.optional:
                    continue

                raise MissingCapabilityError(
                    (
                        f"Module '{requirement.module_key}' requires "
                        f"capability '{requirement.capability}', but "
                        "no provider was found."
                    ),
                    module_key=requirement.module_key,
                    field_path=self._field_path(requirement),
                    context={
                        "capability": requirement.capability,
                        "binding_key": requirement.binding_key,
                        "available_capabilities": sorted(
                            {
                                provider.capability
                                for provider in providers
                            }
                        ),
                    },
                    suggestion=(
                        "Add a module providing capability "
                        f"'{requirement.capability}'."
                    ),
                )

            if requirement.unique and len(candidates) > 1:
                candidate_modules = [
                    candidate.module_key
                    for candidate in candidates
                ]

                raise AmbiguousProviderError(
                    (
                        f"Module '{requirement.module_key}' requires "
                        f"one provider for capability "
                        f"'{requirement.capability}', but "
                        f"{len(candidates)} providers were found."
                    ),
                    module_key=requirement.module_key,
                    field_path=self._field_path(requirement),
                    context={
                        "capability": requirement.capability,
                        "binding_key": requirement.binding_key,
                        "candidate_modules": candidate_modules,
                        "candidate_count": len(candidates),
                    },
                    suggestion=(
                        "Keep one matching provider or configure an "
                        "explicit provider selection."
                    ),
                )

            selected_providers = (
                candidates[:1]
                if requirement.unique
                else candidates
            )

            for provider in selected_providers:
                bindings.append(
                    self._create_binding(
                        requirement=requirement,
                        provider=provider,
                    )
                )

        return bindings

    def _create_binding(
        self,
        *,
        requirement: CapabilityRequirement,
        provider: CapabilityProvider,
    ) -> CapabilityBinding:
        """Create one independent resolved binding."""
        return CapabilityBinding(
            binding_key=requirement.binding_key,
            capability=requirement.capability,
            consumer_module_key=requirement.module_key,
            provider_module_key=provider.module_key,
            values=deepcopy(provider.values),
        )

    def _field_path(
        self,
        requirement: CapabilityRequirement,
    ) -> str:
        return (
            f"modules.{requirement.module_key}."
            f"requires.{requirement.binding_key}"
        )