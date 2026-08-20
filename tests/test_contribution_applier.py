import pytest
from boilr_generator.core import (
    Contribution,
    ExtensionPoint,
)
from boilr_generator.exceptions import (
    ContributionConflictError,
    InvalidContributionError,
)
from boilr_generator.resolver.contribution_applier import (
    ContributionApplier,
)


def make_extension_point(
    *,
    value_type="list",
    merge_strategy="append_unique",
    default=None,
    required=False,
):
    return ExtensionPoint(
        module_key="django",
        key="example.point",
        value_type=value_type,
        merge_strategy=merge_strategy,
        default=default,
        required=required,
    )


def make_contribution(
    contributor,
    value,
):
    return Contribution(
        contributor_module_key=contributor,
        target_module_key="django",
        target_binding="backend",
        extension_point="example.point",
        value=value,
    )


def test_applier_exposes_extension_point_default():
    extension_point = make_extension_point(
        default=["base"],
    )

    values = ContributionApplier().apply(
        [extension_point],
        [],
    )

    assert len(values) == 1
    assert values[0].value == ["base"]
    assert values[0].contributor_module_keys == []


def test_applier_appends_list_contributions():
    extension_point = make_extension_point(
        merge_strategy="append",
        default=[],
    )

    contributions = [
        make_contribution("module_a", ["first"]),
        make_contribution(
            "module_b",
            ["first", "second"],
        ),
    ]

    values = ContributionApplier().apply(
        [extension_point],
        contributions,
    )

    assert values[0].value == [
        "first",
        "first",
        "second",
    ]


def test_applier_appends_unique_list_contributions():
    extension_point = make_extension_point(
        merge_strategy="append_unique",
        default=["base"],
    )

    contributions = [
        make_contribution(
            "module_a",
            ["base", "first"],
        ),
        make_contribution(
            "module_b",
            ["first", "second"],
        ),
    ]

    values = ContributionApplier().apply(
        [extension_point],
        contributions,
    )

    assert values[0].value == [
        "base",
        "first",
        "second",
    ]
    assert values[0].contributor_module_keys == [
        "module_a",
        "module_b",
    ]


def test_applier_accepts_identical_replace_contributions():
    extension_point = make_extension_point(
        value_type="string",
        merge_strategy="replace",
        default="default",
    )

    contributions = [
        make_contribution("module_a", "configured"),
        make_contribution("module_b", "configured"),
    ]

    values = ContributionApplier().apply(
        [extension_point],
        contributions,
    )

    assert values[0].value == "configured"
    assert values[0].contributor_module_keys == [
        "module_a",
        "module_b",
    ]


def test_applier_rejects_conflicting_replace_values():
    extension_point = make_extension_point(
        value_type="string",
        merge_strategy="replace",
    )

    contributions = [
        make_contribution("module_a", "first"),
        make_contribution("module_b", "second"),
    ]

    with pytest.raises(
        ContributionConflictError
    ) as error_info:
        ContributionApplier().apply(
            [extension_point],
            contributions,
        )

    error = error_info.value

    assert error.code == "contribution_conflict"
    assert error.module_key == "module_b"
    assert error.field_path == (
        "modules.django.extension_points.example.point"
    )
    assert error.context == {
        "target_module": "django",
        "extension_point": "example.point",
        "merge_strategy": "replace",
        "value_path": "example.point",
        "first_contributor": "module_a",
        "conflicting_contributor": "module_b",
        "existing_value": "first",
        "conflicting_value": "second",
    }
    assert error.suggestion is not None


def test_applier_deep_merges_non_conflicting_values():
    extension_point = make_extension_point(
        value_type="dict",
        merge_strategy="deep_merge",
        default={
            "pool": {
                "size": 5,
            }
        },
    )

    contributions = [
        make_contribution(
            "module_a",
            {
                "pool": {
                    "timeout": 30,
                }
            },
        ),
        make_contribution(
            "module_b",
            {
                "ssl": True,
            },
        ),
    ]

    values = ContributionApplier().apply(
        [extension_point],
        contributions,
    )

    assert values[0].value == {
        "pool": {
            "size": 5,
            "timeout": 30,
        },
        "ssl": True,
    }


def test_applier_rejects_deep_merge_conflicts():
    extension_point = make_extension_point(
        value_type="dict",
        merge_strategy="deep_merge",
        default={},
    )

    contributions = [
        make_contribution(
            "module_a",
            {
                "pool": {
                    "size": 5,
                }
            },
        ),
        make_contribution(
            "module_b",
            {
                "pool": {
                    "size": 10,
                }
            },
        ),
    ]

    with pytest.raises(
        ContributionConflictError
    ) as error_info:
        ContributionApplier().apply(
            [extension_point],
            contributions,
        )

    error = error_info.value

    assert error.code == "contribution_conflict"
    assert error.module_key == "module_b"
    assert error.field_path == (
        "modules.django.extension_points.example.point"
    )
    assert error.context == {
        "target_module": "django",
        "extension_point": "example.point",
        "merge_strategy": "deep_merge",
        "value_path": "example.point.pool.size",
        "first_contributor": "module_a",
        "conflicting_contributor": "module_b",
        "existing_value": 5,
        "conflicting_value": 10,
    }
    assert error.suggestion is not None

def test_applier_rejects_missing_required_contribution():
    extension_point = make_extension_point(
        value_type="string",
        merge_strategy="replace",
        required=True,
    )

    with pytest.raises(
        InvalidContributionError
    ) as error_info:
        ContributionApplier().apply(
            [extension_point],
            [],
        )

    error = error_info.value

    assert error.code == "invalid_contribution"
    assert error.module_key == "django"
    assert error.context["reason"] == (
        "missing_required_contribution"
    )
    assert error.context["extension_point"] == (
        "example.point"
    )