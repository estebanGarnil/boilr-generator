"""Capability provider selection and binding creation."""

from copy import deepcopy

from boilr_generator.core.capabilities import (
    CapabilityBinding,
    CapabilityProvider,
    CapabilityRequirement,
)
from boilr_generator.exceptions import (
    AmbiguousProviderError,
    BindingError,
    MissingCapabilityError,
)

TYPE_MAPPING: dict[str, type] = {
    "string": str,
    "int": int,
    "boolean": bool,
    "list": list,
}


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
                self._validate_provider_contract(
                    requirement=requirement,
                    provider=provider,
                )

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

    def _validate_provider_contract(
        self,
        *,
        requirement: CapabilityRequirement,
        provider: CapabilityProvider,
    ) -> None:
        """Validate one provider against its consumer contract."""
        for field_name, expected_type in requirement.contract.items():
            field_path = (
                f"{self._field_path(requirement)}."
                f"contract.{field_name}"
            )

            if field_name not in provider.values:
                raise BindingError(
                    (
                        f"Provider '{provider.module_key}' for capability "
                        f"'{requirement.capability}' does not expose "
                        f"required field '{field_name}'."
                    ),
                    module_key=requirement.module_key,
                    field_path=field_path,
                    context={
                        "reason": "missing_field",
                        "capability": requirement.capability,
                        "binding_key": requirement.binding_key,
                        "provider_module": provider.module_key,
                        "field": field_name,
                        "expected_type": expected_type,
                    },
                    suggestion=(
                        f"Add field '{field_name}' to capability "
                        f"'{requirement.capability}' provided by module "
                        f"'{provider.module_key}'."
                    ),
                )

            value = provider.values[field_name]

            if self._matches_type(value, expected_type):
                continue

            raise BindingError(
                (
                    f"Field '{field_name}' provided by module "
                    f"'{provider.module_key}' for capability "
                    f"'{requirement.capability}' must be of type "
                    f"'{expected_type}', got "
                    f"'{type(value).__name__}'."
                ),
                module_key=requirement.module_key,
                field_path=field_path,
                context={
                    "reason": "invalid_type",
                    "capability": requirement.capability,
                    "binding_key": requirement.binding_key,
                    "provider_module": provider.module_key,
                    "field": field_name,
                    "expected_type": expected_type,
                    "actual_type": type(value).__name__,
                },
                suggestion=(
                    f"Expose field '{field_name}' as type "
                    f"'{expected_type}' from module "
                    f"'{provider.module_key}'."
                ),
            )

    def _matches_type(
        self,
        value: object,
        expected_type: str,
    ) -> bool:
        """Check types without accepting booleans as integers."""
        expected_python_type = TYPE_MAPPING.get(expected_type)

        if expected_python_type is None:
            return False

        if expected_python_type is int:
            return isinstance(value, int) and not isinstance(value, bool)

        return isinstance(value, expected_python_type)

    def _field_path(
        self,
        requirement: CapabilityRequirement,
    ) -> str:
        return (
            f"modules.{requirement.module_key}."
            f"requires.{requirement.binding_key}"
        )