"""Read-only planning of generated-project module transitions."""

from __future__ import annotations

from collections import Counter
from dataclasses import asdict, dataclass, field
from heapq import heappop, heappush
from typing import TYPE_CHECKING, Literal

from boilr_generator.core.module_lifecycle import (
    ProjectModuleLifecycleGraph,
    build_project_module_lifecycle_graph,
)
from boilr_generator.state.schemas import (
    ProjectState,
    StateBinding,
    StateModule,
)

if TYPE_CHECKING:
    from boilr_generator.core.generation_plan import (
        GenerationPlan,
    )

ModuleTransitionAction = Literal[
    "add",
    "update",
    "retain",
    "remove",
]
ModuleTransitionConflictReason = Literal[
    "candidate_cycle",
    "removal_cycle",
]

_MODULE_COMPARISON_FIELDS = (
    "version",
    "origin",
    "manifest_sha256",
    "destination",
)
_BINDING_COMPARISON_FIELDS = (
    "capability",
    "provider_module",
)


@dataclass(frozen=True, slots=True)
class ModuleTransition:
    """One module transition between stored and desired state."""

    module_key: str
    action: ModuleTransitionAction
    current_version: str | None
    target_version: str | None
    changed_fields: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, object]:
        """Serialize one deterministic module transition."""
        data = asdict(self)
        data["changed_fields"] = list(
            self.changed_fields
        )
        return data


@dataclass(frozen=True, slots=True)
class BindingTransition:
    """One capability-binding transition between states."""

    consumer_module: str
    binding: str
    action: ModuleTransitionAction
    current_provider_module: str | None
    target_provider_module: str | None
    current_capability: str | None
    target_capability: str | None
    changed_fields: tuple[str, ...] = ()

    @property
    def identity(self) -> tuple[str, str]:
        """Return the stable identity of the binding."""
        return self.consumer_module, self.binding

    def to_dict(self) -> dict[str, object]:
        """Serialize one deterministic binding transition."""
        data = asdict(self)
        data["changed_fields"] = list(
            self.changed_fields
        )
        return data


@dataclass(frozen=True, slots=True)
class ModuleTransitionConflict:
    """One lifecycle conflict blocking module changes."""

    reason: ModuleTransitionConflictReason
    module_keys: tuple[str, ...]

    def to_dict(self) -> dict[str, object]:
        """Serialize one deterministic lifecycle conflict."""
        return {
            "reason": self.reason,
            "module_keys": list(self.module_keys),
        }


@dataclass(frozen=True, slots=True)
class ProjectModuleTransitionPlan:
    """Complete read-only contract for module changes."""

    current_state: ProjectState = field(repr=False)
    desired_state: ProjectState = field(repr=False)
    candidate_graph: ProjectModuleLifecycleGraph = field(
        repr=False
    )
    modules: tuple[ModuleTransition, ...]
    bindings: tuple[BindingTransition, ...]
    activation_order: tuple[str, ...]
    removal_order: tuple[str, ...]
    conflicts: tuple[
        ModuleTransitionConflict,
        ...,
    ] = ()

    @property
    def can_execute(self) -> bool:
        """Return whether every transition can be ordered."""
        return not self.conflicts

    @property
    def has_changes(self) -> bool:
        """Return whether modules or bindings change."""
        return any(
            transition.action != "retain"
            for transition in (
                *self.modules,
                *self.bindings,
            )
        )

    @property
    def summary(self) -> dict[str, int]:
        """Return deterministic transition counters."""
        module_counts = Counter(
            transition.action
            for transition in self.modules
        )
        binding_counts = Counter(
            transition.action
            for transition in self.bindings
        )

        return {
            "modules_count": len(self.modules),
            "modules_to_add": module_counts["add"],
            "modules_to_update": (
                module_counts["update"]
            ),
            "modules_to_retain": (
                module_counts["retain"]
            ),
            "modules_to_remove": (
                module_counts["remove"]
            ),
            "bindings_count": len(self.bindings),
            "bindings_to_add": binding_counts["add"],
            "bindings_to_update": (
                binding_counts["update"]
            ),
            "bindings_to_retain": (
                binding_counts["retain"]
            ),
            "bindings_to_remove": (
                binding_counts["remove"]
            ),
            "conflicts_count": len(self.conflicts),
        }

    def to_dict(self) -> dict[str, object]:
        """Serialize the complete transition contract."""
        return {
            "modules": [
                transition.to_dict()
                for transition in self.modules
            ],
            "bindings": [
                transition.to_dict()
                for transition in self.bindings
            ],
            "activation_order": list(
                self.activation_order
            ),
            "removal_order": list(
                self.removal_order
            ),
            "conflicts": [
                conflict.to_dict()
                for conflict in self.conflicts
            ],
            "summary": self.summary,
            "can_execute": self.can_execute,
            "has_changes": self.has_changes,
        }


def _changed_fields(
    current: StateModule | StateBinding,
    desired: StateModule | StateBinding,
    fields: tuple[str, ...],
) -> tuple[str, ...]:
    """Return deterministically ordered changed fields."""
    return tuple(
        field_name
        for field_name in fields
        if (
            getattr(current, field_name)
            != getattr(desired, field_name)
        )
    )


def _classify_modules(
    current_state: ProjectState,
    desired_state: ProjectState,
) -> tuple[ModuleTransition, ...]:
    """Classify every stored or desired module."""
    current_by_key = {
        module.key: module
        for module in current_state.modules
    }
    desired_by_key = {
        module.key: module
        for module in desired_state.modules
    }
    transitions: list[ModuleTransition] = []

    for module_key in sorted(
        set(current_by_key)
        | set(desired_by_key)
    ):
        current = current_by_key.get(module_key)
        desired = desired_by_key.get(module_key)

        if current is None and desired is not None:
            transitions.append(
                ModuleTransition(
                    module_key=module_key,
                    action="add",
                    current_version=None,
                    target_version=desired.version,
                )
            )
            continue

        if current is not None and desired is None:
            transitions.append(
                ModuleTransition(
                    module_key=module_key,
                    action="remove",
                    current_version=current.version,
                    target_version=None,
                )
            )
            continue

        if current is None or desired is None:
            raise AssertionError(
                "Module transition classification "
                "is incomplete."
            )

        changed_fields = _changed_fields(
            current,
            desired,
            _MODULE_COMPARISON_FIELDS,
        )

        transitions.append(
            ModuleTransition(
                module_key=module_key,
                action=(
                    "update"
                    if changed_fields
                    else "retain"
                ),
                current_version=current.version,
                target_version=desired.version,
                changed_fields=changed_fields,
            )
        )

    return tuple(transitions)


def _classify_bindings(
    current_state: ProjectState,
    desired_state: ProjectState,
) -> tuple[BindingTransition, ...]:
    """Classify every stored or desired binding."""
    current_by_identity = {
        binding.identity: binding
        for binding in current_state.bindings
    }
    desired_by_identity = {
        binding.identity: binding
        for binding in desired_state.bindings
    }
    transitions: list[BindingTransition] = []

    for identity in sorted(
        set(current_by_identity)
        | set(desired_by_identity)
    ):
        current = current_by_identity.get(identity)
        desired = desired_by_identity.get(identity)

        if current is None and desired is not None:
            transitions.append(
                BindingTransition(
                    consumer_module=(
                        desired.consumer_module
                    ),
                    binding=desired.binding,
                    action="add",
                    current_provider_module=None,
                    target_provider_module=(
                        desired.provider_module
                    ),
                    current_capability=None,
                    target_capability=(
                        desired.capability
                    ),
                )
            )
            continue

        if current is not None and desired is None:
            transitions.append(
                BindingTransition(
                    consumer_module=(
                        current.consumer_module
                    ),
                    binding=current.binding,
                    action="remove",
                    current_provider_module=(
                        current.provider_module
                    ),
                    target_provider_module=None,
                    current_capability=(
                        current.capability
                    ),
                    target_capability=None,
                )
            )
            continue

        if current is None or desired is None:
            raise AssertionError(
                "Binding transition classification "
                "is incomplete."
            )

        changed_fields = _changed_fields(
            current,
            desired,
            _BINDING_COMPARISON_FIELDS,
        )

        transitions.append(
            BindingTransition(
                consumer_module=(
                    current.consumer_module
                ),
                binding=current.binding,
                action=(
                    "update"
                    if changed_fields
                    else "retain"
                ),
                current_provider_module=(
                    current.provider_module
                ),
                target_provider_module=(
                    desired.provider_module
                ),
                current_capability=(
                    current.capability
                ),
                target_capability=(
                    desired.capability
                ),
                changed_fields=changed_fields,
            )
        )

    return tuple(transitions)


def _cycle_module_keys(
    dependencies: dict[str, set[str]],
) -> tuple[str, ...]:
    """Return exactly the modules participating in a cycle."""
    cycle_modules: set[str] = set()

    for start in sorted(dependencies):
        visited: set[str] = set()
        pending = list(dependencies[start])

        while pending:
            current = pending.pop()

            if current == start:
                cycle_modules.add(start)
                break

            if current in visited:
                continue

            visited.add(current)
            pending.extend(
                dependencies[current]
            )

    return tuple(sorted(cycle_modules))


def _removed_module_order(
    current_state: ProjectState,
    removed_module_keys: set[str],
) -> tuple[
    tuple[str, ...],
    tuple[str, ...],
]:
    """Order removals using stored capability bindings."""
    dependencies = {
        module_key: set()
        for module_key in removed_module_keys
    }

    for binding in current_state.bindings:
        consumer = binding.consumer_module
        provider = binding.provider_module

        if (
            consumer in removed_module_keys
            and provider in removed_module_keys
            and consumer != provider
        ):
            dependencies[consumer].add(provider)

    cycle_modules = _cycle_module_keys(
        dependencies
    )

    if cycle_modules:
        return (), cycle_modules

    incoming_dependents = {
        module_key: 0
        for module_key in removed_module_keys
    }

    for module_dependencies in (
        dependencies.values()
    ):
        for dependency in module_dependencies:
            incoming_dependents[dependency] += 1

    ready = sorted(
        module_key
        for module_key, count
        in incoming_dependents.items()
        if count == 0
    )
    removal_order: list[str] = []

    while ready:
        module_key = heappop(ready)
        removal_order.append(module_key)

        for dependency in sorted(
            dependencies[module_key]
        ):
            incoming_dependents[dependency] -= 1

            if (
                incoming_dependents[dependency]
                == 0
            ):
                heappush(ready, dependency)

    return tuple(removal_order), ()


def _validate_candidate_graph(
    desired_state: ProjectState,
    graph: ProjectModuleLifecycleGraph,
) -> None:
    """Ensure desired state and resolved graph agree."""
    desired_modules = {
        module.key: module
        for module in desired_state.modules
    }

    if (
        set(desired_modules)
        != set(graph.module_keys)
    ):
        raise ValueError(
            "The candidate lifecycle graph does not "
            "match the desired project modules."
        )

    if (
        set(graph.resolution_order)
        != set(graph.module_keys)
    ):
        raise ValueError(
            "The candidate lifecycle resolution "
            "order is incomplete."
        )

    mismatched_versions = sorted(
        module_key
        for module_key, module
        in desired_modules.items()
        if (
            graph.node_for(module_key).version
            != module.version
        )
    )

    if mismatched_versions:
        raise ValueError(
            "The candidate lifecycle graph has stale "
            "module versions: "
            f"{', '.join(mismatched_versions)}."
        )


def build_project_module_transition_plan(
    candidate_plan: GenerationPlan,
    current_state: ProjectState,
) -> ProjectModuleTransitionPlan:
    """Classify and order module changes without mutation."""
    if candidate_plan.clean_output:
        raise ValueError(
            "Module transitions cannot be planned "
            "from a clean generation plan."
        )

    desired_state = candidate_plan.desired_state

    if desired_state is None:
        raise ValueError(
            "Module transitions require a candidate "
            "desired state."
        )

    current_identity = (
        current_state.project.name,
        current_state.project.type,
    )
    desired_identity = (
        desired_state.project.name,
        desired_state.project.type,
    )

    if current_identity != desired_identity:
        raise ValueError(
            "The candidate plan targets a "
            "different project."
        )

    candidate_graph = (
        build_project_module_lifecycle_graph(
            candidate_plan.resolved_project
        )
    )

    _validate_candidate_graph(
        desired_state,
        candidate_graph,
    )

    modules = _classify_modules(
        current_state,
        desired_state,
    )
    bindings = _classify_bindings(
        current_state,
        desired_state,
    )

    activation_keys = {
        transition.module_key
        for transition in modules
        if transition.action in {
            "add",
            "update",
        }
    }
    removed_module_keys = {
        transition.module_key
        for transition in modules
        if transition.action == "remove"
    }

    activation_order = tuple(
        module_key
        for module_key
        in candidate_graph.resolution_order
        if module_key in activation_keys
    )

    (
        removal_order,
        removal_cycle,
    ) = _removed_module_order(
        current_state,
        removed_module_keys,
    )

    conflicts: list[
        ModuleTransitionConflict
    ] = []

    if candidate_graph.cycle_module_keys:
        conflicts.append(
            ModuleTransitionConflict(
                reason="candidate_cycle",
                module_keys=(
                    candidate_graph.cycle_module_keys
                ),
            )
        )

    if removal_cycle:
        conflicts.append(
            ModuleTransitionConflict(
                reason="removal_cycle",
                module_keys=removal_cycle,
            )
        )

    return ProjectModuleTransitionPlan(
        current_state=current_state,
        desired_state=desired_state,
        candidate_graph=candidate_graph,
        modules=modules,
        bindings=bindings,
        activation_order=activation_order,
        removal_order=removal_order,
        conflicts=tuple(conflicts),
    )