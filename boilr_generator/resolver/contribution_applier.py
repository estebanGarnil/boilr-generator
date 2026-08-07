"""Application and merging of resolved contributions."""

from copy import deepcopy
from typing import Any

from boilr_generator.core.contributions import (
    Contribution,
    ExtensionPoint,
    ExtensionPointValue,
)
from boilr_generator.exceptions import (
    ContributionConflictError,
)


class ContributionApplier:
    """Apply contributions according to extension point strategies."""

    def apply(
        self,
        extension_points: list[ExtensionPoint],
        contributions: list[Contribution],
    ) -> list[ExtensionPointValue]:
        """Produce the final value of every extension point."""
        values: list[ExtensionPointValue] = []

        for extension_point in extension_points:
            matching_contributions = [
                contribution
                for contribution in contributions
                if (
                    contribution.target_module_key
                    == extension_point.module_key
                    and contribution.extension_point
                    == extension_point.key
                )
            ]

            value, contributors = self._apply_extension_point(
                extension_point,
                matching_contributions,
            )

            values.append(
                ExtensionPointValue(
                    module_key=extension_point.module_key,
                    extension_point=extension_point.key,
                    value=value,
                    contributor_module_keys=contributors,
                )
            )

        return values

    def _apply_extension_point(
        self,
        extension_point: ExtensionPoint,
        contributions: list[Contribution],
    ) -> tuple[Any, list[str]]:
        """Dispatch one extension point to its merge strategy."""
        strategy = extension_point.merge_strategy

        if strategy == "replace":
            return self._apply_replace(
                extension_point,
                contributions,
            )

        if strategy == "append":
            return self._apply_append(
                extension_point,
                contributions,
                unique=False,
            )

        if strategy == "append_unique":
            return self._apply_append(
                extension_point,
                contributions,
                unique=True,
            )

        if strategy == "deep_merge":
            return self._apply_deep_merge(
                extension_point,
                contributions,
            )

        raise ValueError(
            f"Unsupported contribution merge strategy: {strategy}"
        )

    def _apply_replace(
        self,
        extension_point: ExtensionPoint,
        contributions: list[Contribution],
    ) -> tuple[Any, list[str]]:
        """Accept one value or multiple identical values."""
        if not contributions:
            return deepcopy(extension_point.default), []

        first_contribution = contributions[0]
        value = deepcopy(first_contribution.value)
        contributors = [
            first_contribution.contributor_module_key
        ]

        for contribution in contributions[1:]:
            if contribution.value != value:
                self._raise_conflict(
                    extension_point=extension_point,
                    existing_value=value,
                    conflicting_value=contribution.value,
                    first_contributor=(
                        first_contribution.contributor_module_key
                    ),
                    conflicting_contributor=(
                        contribution.contributor_module_key
                    ),
                    value_path=extension_point.key,
                )

            contributors.append(
                contribution.contributor_module_key
            )

        return value, self._unique(contributors)

    def _apply_append(
        self,
        extension_point: ExtensionPoint,
        contributions: list[Contribution],
        *,
        unique: bool,
    ) -> tuple[list[Any], list[str]]:
        """Append list contributions, optionally removing duplicates."""
        value = deepcopy(extension_point.default)

        if value is None:
            value = []

        contributors: list[str] = []

        for contribution in contributions:
            for item in contribution.value:
                if unique and item in value:
                    continue

                value.append(deepcopy(item))

            contributors.append(
                contribution.contributor_module_key
            )

        return value, self._unique(contributors)

    def _apply_deep_merge(
        self,
        extension_point: ExtensionPoint,
        contributions: list[Contribution],
    ) -> tuple[dict[str, Any], list[str]]:
        """Merge dictionaries while rejecting conflicting leaves."""
        value = deepcopy(extension_point.default)

        if value is None:
            value = {}

        origins: dict[tuple[str, ...], str] = {}

        self._record_origins(
            value,
            path=(),
            origin="extension_point_default",
            origins=origins,
        )

        contributors: list[str] = []

        for contribution in contributions:
            self._merge_dict(
                target=value,
                incoming=contribution.value,
                path=(),
                origins=origins,
                contributor=(
                    contribution.contributor_module_key
                ),
                extension_point=extension_point,
            )

            contributors.append(
                contribution.contributor_module_key
            )

        return value, self._unique(contributors)

    def _merge_dict(
        self,
        *,
        target: dict[str, Any],
        incoming: dict[str, Any],
        path: tuple[str, ...],
        origins: dict[tuple[str, ...], str],
        contributor: str,
        extension_point: ExtensionPoint,
    ) -> None:
        """Recursively merge one contribution dictionary."""
        for key, incoming_value in incoming.items():
            current_path = (*path, key)

            if key not in target:
                target[key] = deepcopy(incoming_value)

                self._record_origins(
                    incoming_value,
                    path=current_path,
                    origin=contributor,
                    origins=origins,
                )
                continue

            existing_value = target[key]

            if (
                isinstance(existing_value, dict)
                and isinstance(incoming_value, dict)
            ):
                self._merge_dict(
                    target=existing_value,
                    incoming=incoming_value,
                    path=current_path,
                    origins=origins,
                    contributor=contributor,
                    extension_point=extension_point,
                )
                continue

            if existing_value == incoming_value:
                continue

            first_contributor = self._origin_for_path(
                origins,
                current_path,
            )

            self._raise_conflict(
                extension_point=extension_point,
                existing_value=existing_value,
                conflicting_value=incoming_value,
                first_contributor=first_contributor,
                conflicting_contributor=contributor,
                value_path=".".join(
                    (
                        extension_point.key,
                        *current_path,
                    )
                ),
            )

    def _record_origins(
        self,
        value: Any,
        *,
        path: tuple[str, ...],
        origin: str,
        origins: dict[tuple[str, ...], str],
    ) -> None:
        """Record the contributor owning each value path."""
        if isinstance(value, dict):
            for key, item in value.items():
                self._record_origins(
                    item,
                    path=(*path, key),
                    origin=origin,
                    origins=origins,
                )
            return

        origins[path] = origin

    def _origin_for_path(
        self,
        origins: dict[tuple[str, ...], str],
        path: tuple[str, ...],
    ) -> str:
        """Find the owner of a conflicting value path."""
        if path in origins:
            return origins[path]

        for candidate_path, origin in origins.items():
            if candidate_path[:len(path)] == path:
                return origin

        return "extension_point_default"

    def _raise_conflict(
        self,
        *,
        extension_point: ExtensionPoint,
        existing_value: Any,
        conflicting_value: Any,
        first_contributor: str,
        conflicting_contributor: str,
        value_path: str,
    ) -> None:
        """Raise a structured contribution conflict."""
        raise ContributionConflictError(
            (
                f"Conflicting contributions for extension point "
                f"'{extension_point.key}' at '{value_path}'."
            ),
            module_key=conflicting_contributor,
            field_path=(
                f"modules.{extension_point.module_key}."
                f"extension_points.{extension_point.key}"
            ),
            context={
                "target_module": extension_point.module_key,
                "extension_point": extension_point.key,
                "merge_strategy": (
                    extension_point.merge_strategy
                ),
                "value_path": value_path,
                "first_contributor": first_contributor,
                "conflicting_contributor": (
                    conflicting_contributor
                ),
                "existing_value": deepcopy(existing_value),
                "conflicting_value": deepcopy(
                    conflicting_value
                ),
            },
            suggestion=(
                "Make the contributions identical or choose a "
                "compatible merge strategy."
            ),
        )

    def _unique(
        self,
        values: list[str],
    ) -> list[str]:
        """Return strings without duplicates, preserving order."""
        return list(dict.fromkeys(values))