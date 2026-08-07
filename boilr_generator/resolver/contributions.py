"""Collection and validation of module contributions."""

from copy import deepcopy
from typing import Any

from boilr_generator.core.capabilities import (
    CapabilityBinding,
)
from boilr_generator.core.contributions import (
    Contribution,
    ExtensionPoint,
)
from boilr_generator.core.module import ResolvedModule
from boilr_generator.exceptions import (
    InvalidContributionError,
    TemplateRenderError,
    UnknownExtensionPointError,
)
from boilr_generator.resolver.rendering import (
    NativeRenderFailure,
    render_native_value,
)

TYPE_MAPPING: dict[str, type] = {
    "string": str,
    "int": int,
    "boolean": bool,
    "list": list,
    "dict": dict,
}


class ContributionCollector:
    """Collect extension points and resolve contribution targets."""

    def collect_extension_points(
        self,
        modules: list[ResolvedModule],
    ) -> list[ExtensionPoint]:
        """Collect every extension point exposed by modules."""
        extension_points: list[ExtensionPoint] = []

        for module in modules:
            for key, definition in (
                module.manifest.extension_points.items()
            ):
                extension_points.append(
                    ExtensionPoint(
                        module_key=module.key,
                        key=key,
                        value_type=definition.type,
                        merge_strategy=definition.merge,
                        default=deepcopy(definition.default),
                        required=definition.required,
                    )
                )

        return extension_points

    def collect_contributions(
        self,
        modules: list[ResolvedModule],
        bindings: list[CapabilityBinding],
        extension_points: list[ExtensionPoint],
    ) -> list[Contribution]:
        """Resolve, render, and validate every contribution."""
        contributions: list[Contribution] = []

        extension_point_lookup = {
            (
                extension_point.module_key,
                extension_point.key,
            ): extension_point
            for extension_point in extension_points
        }

        for module in modules:
            render_context = self._build_render_context(
                module,
                bindings,
            )

            for index, declaration in enumerate(
                module.manifest.contributions
            ):
                target_bindings = [
                    binding
                    for binding in bindings
                    if (
                        binding.consumer_module_key == module.key
                        and binding.binding_key
                        == declaration.target_binding
                    )
                ]

                if not target_bindings:
                    continue

                field_path = (
                    f"modules.{module.key}."
                    f"contributions[{index}]"
                )

                resolved_targets: list[
                    tuple[CapabilityBinding, ExtensionPoint]
                ] = []

                for binding in target_bindings:
                    lookup_key = (
                        binding.provider_module_key,
                        declaration.extension_point,
                    )
                    extension_point = (
                        extension_point_lookup.get(lookup_key)
                    )

                    if extension_point is None:
                        available_extension_points = sorted(
                            point.key
                            for point in extension_points
                            if point.module_key
                            == binding.provider_module_key
                        )

                        raise UnknownExtensionPointError(
                            (
                                f"Module "
                                f"'{binding.provider_module_key}' "
                                "does not expose extension point "
                                f"'{declaration.extension_point}'."
                            ),
                            module_key=module.key,
                            field_path=(
                                f"{field_path}.extension_point"
                            ),
                            context={
                                "target_module": (
                                    binding.provider_module_key
                                ),
                                "target_binding": (
                                    declaration.target_binding
                                ),
                                "extension_point": (
                                    declaration.extension_point
                                ),
                                "available_extension_points": (
                                    available_extension_points
                                ),
                            },
                            suggestion=(
                                "Use an extension point exposed "
                                "by the bound target module."
                            ),
                        )

                    resolved_targets.append(
                        (
                            binding,
                            extension_point,
                        )
                    )

                rendered_value = (
                    self._render_contribution_value(
                        declaration.value,
                        render_context,
                        module_key=module.key,
                        target_binding=(
                            declaration.target_binding
                        ),
                        extension_point=(
                            declaration.extension_point
                        ),
                        field_path=f"{field_path}.value",
                    )
                )

                for binding, extension_point in resolved_targets:
                    self._validate_contribution_type(
                        value=rendered_value,
                        extension_point=extension_point,
                        contributor_module_key=module.key,
                        field_path=f"{field_path}.value",
                    )

                    contributions.append(
                        Contribution(
                            contributor_module_key=module.key,
                            target_module_key=(
                                binding.provider_module_key
                            ),
                            target_binding=(
                                declaration.target_binding
                            ),
                            extension_point=(
                                declaration.extension_point
                            ),
                            value=deepcopy(rendered_value),
                        )
                    )

        return contributions

    def _build_render_context(
        self,
        module: ResolvedModule,
        bindings: list[CapabilityBinding],
    ) -> dict[str, Any]:
        """Build the pre-extension contributor context."""
        return {
            **deepcopy(module.variables),
            "options": deepcopy(module.options),
            "bindings": self._build_binding_context(
                module,
                bindings,
            ),
        }

    def _build_binding_context(
        self,
        module: ResolvedModule,
        bindings: list[CapabilityBinding],
    ) -> dict[str, Any]:
        """Build bindings using requirement uniqueness rules."""
        context: dict[str, Any] = {}

        for requirement in module.manifest.requires:
            matching_bindings = [
                binding
                for binding in bindings
                if (
                    binding.consumer_module_key == module.key
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

    def _render_contribution_value(
        self,
        value: Any,
        context: dict[str, Any],
        *,
        module_key: str,
        target_binding: str,
        extension_point: str,
        field_path: str,
    ) -> Any:
        """Render one contribution with contributor context."""
        try:
            return render_native_value(
                value,
                context,
                field_path=field_path,
            )
        except NativeRenderFailure as failure:
            error = failure.error

            raise TemplateRenderError(
                (
                    "Unable to render contribution value at "
                    f"'{failure.field_path}': {error}"
                ),
                module_key=module_key,
                field_path=failure.field_path,
                context={
                    "target": "contribution",
                    "target_binding": target_binding,
                    "extension_point": extension_point,
                    "error_type": type(error).__name__,
                },
                suggestion=(
                    "Check the contribution template and ensure "
                    "every referenced variable, option, and "
                    "binding is available."
                ),
            ) from error

    def _validate_contribution_type(
        self,
        *,
        value: Any,
        extension_point: ExtensionPoint,
        contributor_module_key: str,
        field_path: str,
    ) -> None:
        """Validate a contribution against its extension point."""
        expected_python_type = TYPE_MAPPING.get(
            extension_point.value_type
        )

        valid = (
            expected_python_type is not None
            and isinstance(value, expected_python_type)
        )

        if (
            expected_python_type is int
            and isinstance(value, bool)
        ):
            valid = False

        if valid:
            return

        raise InvalidContributionError(
            (
                "Contribution to extension point "
                f"'{extension_point.key}' must be of type "
                f"'{extension_point.value_type}', got "
                f"'{type(value).__name__}'."
            ),
            module_key=contributor_module_key,
            field_path=field_path,
            context={
                "target_module": extension_point.module_key,
                "extension_point": extension_point.key,
                "expected_type": extension_point.value_type,
                "actual_type": type(value).__name__,
            },
            suggestion=(
                "Provide a value of type "
                f"'{extension_point.value_type}'."
            ),
        )