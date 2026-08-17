"""Capability provider selection and binding creation."""

from collections.abc import Mapping
from copy import deepcopy

from packaging.specifiers import (
    InvalidSpecifier,
    SpecifierSet,
)
from packaging.version import InvalidVersion, Version

from boilr_generator.core.capabilities import (
    CapabilityBinding,
    CapabilityProvider,
    CapabilityProviderSelection,
    CapabilityRequirement,
)
from boilr_generator.exceptions import (
    AmbiguousProviderError,
    BindingError,
    MissingCapabilityError,
    ProviderSelectionError,
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
        *,
        provider_selections: Mapping[
            str,
            Mapping[
                str,
                CapabilityProviderSelection,
            ],
        ]
        | None = None,
        selected_module_keys: set[str] | None = None,
    ) -> list[CapabilityBinding]:
        """Resolve every requirement into zero or more bindings."""
        bindings: list[CapabilityBinding] = []
        selections = provider_selections or {}

        available_module_keys = (
            set(selected_module_keys)
            if selected_module_keys is not None
            else {
                provider.module_key
                for provider in providers
            }
        )

        self._validate_provider_selections(
            requirements=requirements,
            provider_selections=selections,
        )

        for requirement in requirements:
            candidates = [
                provider
                for provider in providers
                if provider.capability == requirement.capability
            ]

            selection = selections.get(
                requirement.module_key,
                {},
            ).get(requirement.binding_key)

            if selection is not None:
                candidates = self._select_explicit_provider(
                    requirement=requirement,
                    provider_module_key=(
                        selection.provider_module_key
                    ),
                    candidates=candidates,
                    providers=providers,
                    selected_module_keys=available_module_keys,
                )

                for candidate in candidates:
                    self._validate_provider_version(
                        requirement=requirement,
                        provider=candidate,
                        version_specifier=(
                            selection.version_specifier
                        ),
                    )

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

    def _validate_provider_selections(
        self,
        *,
        requirements: list[CapabilityRequirement],
        provider_selections: Mapping[
            str,
            Mapping[
                str,
                CapabilityProviderSelection,
            ],
        ],
    ) -> None:
        """Reject selections targeting undeclared bindings."""
        bindings_by_module: dict[str, set[str]] = {}

        for requirement in requirements:
            bindings_by_module.setdefault(
                requirement.module_key,
                set(),
            ).add(requirement.binding_key)

        for module_key, selections in (
            provider_selections.items()
        ):
            available_bindings = bindings_by_module.get(
                module_key,
                set(),
            )

            for binding_key, selection in selections.items():
                if binding_key in available_bindings:
                    continue

                raise ProviderSelectionError(
                    (
                        f"Module '{module_key}' selects a provider "
                        f"for unknown binding '{binding_key}'."
                    ),
                    module_key=module_key,
                    field_path=(
                        f"modules.{module_key}."
                        f"bindings.{binding_key}"
                    ),
                    context={
                        "reason": "unknown_binding",
                        "binding_key": binding_key,
                        "provider_module": (
                            selection.provider_module_key
                        ),
                        "available_bindings": sorted(
                            available_bindings
                        ),
                    },
                    suggestion=(
                        "Remove this selection or use a binding "
                        "declared by the consumer module."
                    ),
                )

    def _select_explicit_provider(
        self,
        *,
        requirement: CapabilityRequirement,
        provider_module_key: str,
        candidates: list[CapabilityProvider],
        providers: list[CapabilityProvider],
        selected_module_keys: set[str],
    ) -> list[CapabilityProvider]:
        """Select and validate one explicitly requested provider."""
        selection_path = (
            f"modules.{requirement.module_key}."
            f"bindings.{requirement.binding_key}"
        )

        if provider_module_key not in selected_module_keys:
            raise ProviderSelectionError(
                (
                    f"Provider module '{provider_module_key}' selected "
                    f"by module '{requirement.module_key}' is not "
                    "part of the project."
                ),
                module_key=requirement.module_key,
                field_path=selection_path,
                context={
                    "reason": "provider_not_selected",
                    "binding_key": requirement.binding_key,
                    "capability": requirement.capability,
                    "provider_module": provider_module_key,
                    "selected_modules": sorted(
                        selected_module_keys
                    ),
                },
                suggestion=(
                    f"Add module '{provider_module_key}' to the "
                    "project or select another provider."
                ),
            )

        selected_candidates = [
            candidate
            for candidate in candidates
            if candidate.module_key == provider_module_key
        ]

        if selected_candidates:
            return selected_candidates

        provided_capabilities = sorted(
            {
                provider.capability
                for provider in providers
                if provider.module_key
                == provider_module_key
            }
        )

        raise ProviderSelectionError(
            (
                f"Module '{provider_module_key}' does not provide "
                f"capability '{requirement.capability}' required "
                f"by module '{requirement.module_key}'."
            ),
            module_key=requirement.module_key,
            field_path=selection_path,
            context={
                "reason": "capability_mismatch",
                "binding_key": requirement.binding_key,
                "capability": requirement.capability,
                "provider_module": provider_module_key,
                "provided_capabilities": provided_capabilities,
            },
            suggestion=(
                "Select a module providing capability "
                f"'{requirement.capability}'."
            ),
        )

    def _validate_provider_version(
        self,
        *,
        requirement: CapabilityRequirement,
        provider: CapabilityProvider,
        version_specifier: str | None,
    ) -> None:
        """Validate a provider version against the selection."""
        if version_specifier is None:
            return

        field_path = (
            f"modules.{requirement.module_key}."
            f"bindings.{requirement.binding_key}.version"
        )

        try:
            accepted_versions = SpecifierSet(
                version_specifier
            )
        except InvalidSpecifier as error:
            raise ProviderSelectionError(
                (
                    f"Version constraint '{version_specifier}' "
                    "is invalid."
                ),
                module_key=requirement.module_key,
                field_path=field_path,
                context={
                    "reason": "invalid_version_constraint",
                    "binding_key": requirement.binding_key,
                    "provider_module": provider.module_key,
                    "version_constraint": version_specifier,
                },
                suggestion=(
                    "Use a valid PEP 440 constraint, such as "
                    "'>=16,<18'."
                ),
            ) from error

        try:
            provider_version = Version(provider.version)
        except InvalidVersion as error:
            raise ProviderSelectionError(
                (
                    f"Provider '{provider.module_key}' declares "
                    f"invalid version '{provider.version}'."
                ),
                module_key=requirement.module_key,
                field_path=field_path,
                context={
                    "reason": "invalid_provider_version",
                    "binding_key": requirement.binding_key,
                    "provider_module": provider.module_key,
                    "provider_version": provider.version,
                    "version_constraint": version_specifier,
                },
                suggestion=(
                    "Correct the provider module version so that "
                    "it follows PEP 440."
                ),
            ) from error

        if provider_version in accepted_versions:
            return

        raise ProviderSelectionError(
            (
                f"Provider '{provider.module_key}' version "
                f"'{provider.version}' does not satisfy "
                f"constraint '{version_specifier}'."
            ),
            module_key=requirement.module_key,
            field_path=field_path,
            context={
                "reason": "version_mismatch",
                "binding_key": requirement.binding_key,
                "capability": requirement.capability,
                "provider_module": provider.module_key,
                "provider_version": provider.version,
                "version_constraint": version_specifier,
            },
            suggestion=(
                "Select a compatible provider version or change "
                "the requested version constraint."
            ),
        )

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