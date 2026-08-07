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
    UnknownExtensionPointError,
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
                    )
                )

        return extension_points

    def collect_contributions(
        self,
        modules: list[ResolvedModule],
        bindings: list[CapabilityBinding],
        extension_points: list[ExtensionPoint],
    ) -> list[Contribution]:
        """Resolve and validate every declared contribution."""
        contributions: list[Contribution] = []

        extension_point_lookup = {
            (extension_point.module_key, extension_point.key):
            extension_point
            for extension_point in extension_points
        }

        for module in modules:
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

                for binding in target_bindings:
                    lookup_key = (
                        binding.provider_module_key,
                        declaration.extension_point,
                    )
                    extension_point = (
                        extension_point_lookup.get(lookup_key)
                    )

                    field_path = (
                        f"modules.{module.key}."
                        f"contributions[{index}]"
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
                                f"Module '{binding.provider_module_key}' "
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
                                "Use an extension point exposed by the "
                                "bound target module."
                            ),
                        )

                    self._validate_contribution_type(
                        value=declaration.value,
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
                            value=deepcopy(declaration.value),
                        )
                    )

        return contributions

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
                f"Contribution to extension point "
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
                f"Provide a value of type "
                f"'{extension_point.value_type}'."
            ),
        )