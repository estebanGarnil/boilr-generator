"""Read-only lifecycle graph for resolved project modules."""

from collections.abc import Iterable
from dataclasses import dataclass
from heapq import heappop, heappush
from typing import Literal

from boilr_generator.core.project import ResolvedProject

ModuleLifecycleRelationKind = Literal[
    "capability_binding",
    "extension_contribution",
]


@dataclass(frozen=True, slots=True)
class ModuleLifecycleRelation:
    """One reason why a module depends on another module."""

    dependent_module: str
    dependency_module: str
    kind: ModuleLifecycleRelationKind
    binding: str
    capability: str | None = None
    extension_point: str | None = None

    @property
    def identity(self) -> tuple[str, ...]:
        """Return a stable identity for ordering and deduplication."""
        return (
            self.dependent_module,
            self.dependency_module,
            self.kind,
            self.binding,
            self.capability or "",
            self.extension_point or "",
        )

    def to_dict(self) -> dict[str, object]:
        """Serialize the relation into JSON-compatible data."""
        return {
            "dependent_module": self.dependent_module,
            "dependency_module": self.dependency_module,
            "kind": self.kind,
            "binding": self.binding,
            "capability": self.capability,
            "extension_point": self.extension_point,
        }


@dataclass(frozen=True, slots=True)
class ModuleLifecycleNode:
    """Lifecycle metadata for one resolved module."""

    key: str
    version: str
    module_type: str
    provided_capabilities: tuple[str, ...]
    required_capabilities: tuple[str, ...]
    direct_dependencies: tuple[str, ...]
    direct_dependents: tuple[str, ...]

    def to_dict(self) -> dict[str, object]:
        """Serialize the node into JSON-compatible data."""
        return {
            "key": self.key,
            "version": self.version,
            "module_type": self.module_type,
            "provided_capabilities": list(
                self.provided_capabilities
            ),
            "required_capabilities": list(
                self.required_capabilities
            ),
            "direct_dependencies": list(
                self.direct_dependencies
            ),
            "direct_dependents": list(
                self.direct_dependents
            ),
        }


@dataclass(frozen=True, slots=True)
class ProjectModuleLifecycleGraph:
    """Deterministic dependency graph for module lifecycle."""

    nodes: tuple[ModuleLifecycleNode, ...]
    relations: tuple[ModuleLifecycleRelation, ...]
    resolution_order: tuple[str, ...]

    @property
    def module_keys(self) -> tuple[str, ...]:
        """Return every module key in stable order."""
        return tuple(node.key for node in self.nodes)

    def node_for(
        self,
        module_key: str,
    ) -> ModuleLifecycleNode:
        """Return lifecycle metadata for one known module."""
        for node in self.nodes:
            if node.key == module_key:
                return node

        raise ValueError(
            f"Unknown project module: '{module_key}'."
        )

    def dependencies_of(
        self,
        module_key: str,
        *,
        transitive: bool = False,
    ) -> tuple[str, ...]:
        """Return direct or transitive dependencies."""
        return self._related_modules(
            module_key,
            attribute="direct_dependencies",
            transitive=transitive,
        )

    def dependents_of(
        self,
        module_key: str,
        *,
        transitive: bool = False,
    ) -> tuple[str, ...]:
        """Return direct or transitive dependents."""
        return self._related_modules(
            module_key,
            attribute="direct_dependents",
            transitive=transitive,
        )

    def _related_modules(
        self,
        module_key: str,
        *,
        attribute: Literal[
            "direct_dependencies",
            "direct_dependents",
        ],
        transitive: bool,
    ) -> tuple[str, ...]:
        node = self.node_for(module_key)
        direct = tuple(getattr(node, attribute))

        if not transitive:
            return direct

        related: set[str] = set()
        pending = list(direct)

        while pending:
            current = pending.pop()

            if current in related:
                continue

            related.add(current)
            pending.extend(
                getattr(
                    self.node_for(current),
                    attribute,
                )
            )

        related.discard(module_key)
        return tuple(sorted(related))

    @property
    def cycle_module_keys(self) -> tuple[str, ...]:
        """Return exactly the modules participating in a cycle."""
        cycle_modules: set[str] = set()

        for start in self.module_keys:
            visited: set[str] = set()
            pending = list(
                self.dependencies_of(start)
            )

            while pending:
                current = pending.pop()

                if current == start:
                    cycle_modules.add(start)
                    break

                if current in visited:
                    continue

                visited.add(current)
                pending.extend(
                    self.dependencies_of(current)
                )

        return tuple(sorted(cycle_modules))

    @property
    def has_cycles(self) -> bool:
        """Return whether the graph contains a cycle."""
        return bool(self.cycle_module_keys)

    def removal_blockers(
        self,
        module_keys: Iterable[str] | str,
    ) -> tuple[str, ...]:
        """Return dependents left outside a removal set."""
        selected = self._normalize_module_keys(
            module_keys
        )
        blockers: set[str] = set()

        for module_key in selected:
            blockers.update(
                set(
                    self.dependents_of(
                        module_key,
                        transitive=True,
                    )
                )
                - selected
            )

        return tuple(sorted(blockers))

    def removal_order(
        self,
        module_keys: Iterable[str] | str | None = None,
    ) -> tuple[str, ...]:
        """Order a closed set with dependents removed first."""
        selected = (
            set(self.module_keys)
            if module_keys is None
            else self._normalize_module_keys(
                module_keys
            )
        )

        blockers = self.removal_blockers(selected)

        if blockers:
            raise ValueError(
                "Cannot remove modules while dependents "
                f"remain: {', '.join(blockers)}."
            )

        cycle_modules = (
            set(self.cycle_module_keys)
            & selected
        )

        if cycle_modules:
            raise ValueError(
                "Cannot determine a safe removal order "
                "for cyclic modules: "
                f"{', '.join(sorted(cycle_modules))}."
            )

        incoming_dependents = {
            module_key: 0
            for module_key in selected
        }

        for dependent_module in selected:
            for dependency_module in (
                self.dependencies_of(
                    dependent_module
                )
            ):
                if dependency_module in selected:
                    incoming_dependents[
                        dependency_module
                    ] += 1

        ready = [
            module_key
            for module_key, count
            in incoming_dependents.items()
            if count == 0
        ]
        ready.sort()

        removal_order: list[str] = []

        while ready:
            module_key = heappop(ready)
            removal_order.append(module_key)

            for dependency_module in (
                self.dependencies_of(module_key)
            ):
                if dependency_module not in selected:
                    continue

                incoming_dependents[
                    dependency_module
                ] -= 1

                if (
                    incoming_dependents[
                        dependency_module
                    ]
                    == 0
                ):
                    heappush(
                        ready,
                        dependency_module,
                    )

        if len(removal_order) != len(selected):
            raise ValueError(
                "Cannot determine a safe module "
                "removal order."
            )

        return tuple(removal_order)

    def _normalize_module_keys(
        self,
        module_keys: Iterable[str] | str,
    ) -> set[str]:
        selected = (
            {module_keys}
            if isinstance(module_keys, str)
            else set(module_keys)
        )
        unknown = selected - set(self.module_keys)

        if unknown:
            raise ValueError(
                "Unknown project modules: "
                f"{', '.join(sorted(unknown))}."
            )

        return selected

    def to_dict(self) -> dict[str, object]:
        """Serialize the complete graph deterministically."""
        return {
            "nodes": [
                node.to_dict()
                for node in self.nodes
            ],
            "relations": [
                relation.to_dict()
                for relation in self.relations
            ],
            "resolution_order": list(
                self.resolution_order
            ),
            "has_cycles": self.has_cycles,
            "cycle_module_keys": list(
                self.cycle_module_keys
            ),
            "removal_order": (
                None
                if self.has_cycles
                else list(self.removal_order())
            ),
        }


def build_project_module_lifecycle_graph(
    resolved_project: ResolvedProject,
) -> ProjectModuleLifecycleGraph:
    """Build a read-only graph from a resolved project."""
    module_by_key = {
        module.key: module
        for module in resolved_project.modules
    }
    known_modules = set(module_by_key)

    relations_by_identity: dict[
        tuple[str, ...],
        ModuleLifecycleRelation,
    ] = {}

    def add_relation(
        relation: ModuleLifecycleRelation,
    ) -> None:
        referenced_modules = {
            relation.dependent_module,
            relation.dependency_module,
        }
        unknown_modules = (
            referenced_modules - known_modules
        )

        if unknown_modules:
            raise ValueError(
                "Lifecycle relationships reference "
                "unknown modules: "
                f"{', '.join(sorted(unknown_modules))}."
            )

        if (
            relation.dependent_module
            == relation.dependency_module
        ):
            return

        relations_by_identity[
            relation.identity
        ] = relation

    for binding in resolved_project.bindings:
        add_relation(
            ModuleLifecycleRelation(
                dependent_module=(
                    binding.consumer_module_key
                ),
                dependency_module=(
                    binding.provider_module_key
                ),
                kind="capability_binding",
                binding=binding.binding_key,
                capability=binding.capability,
            )
        )

    for contribution in (
        resolved_project.contributions
    ):
        add_relation(
            ModuleLifecycleRelation(
                dependent_module=(
                    contribution.contributor_module_key
                ),
                dependency_module=(
                    contribution.target_module_key
                ),
                kind="extension_contribution",
                binding=contribution.target_binding,
                extension_point=(
                    contribution.extension_point
                ),
            )
        )

    relations = tuple(
        sorted(
            relations_by_identity.values(),
            key=lambda relation: (
                relation.identity
            ),
        )
    )

    dependencies_by_module = {
        module_key: set()
        for module_key in known_modules
    }
    dependents_by_module = {
        module_key: set()
        for module_key in known_modules
    }

    for relation in relations:
        dependencies_by_module[
            relation.dependent_module
        ].add(
            relation.dependency_module
        )
        dependents_by_module[
            relation.dependency_module
        ].add(
            relation.dependent_module
        )

    nodes = tuple(
        ModuleLifecycleNode(
            key=module_key,
            version=module.manifest.meta.version,
            module_type=module.type,
            provided_capabilities=tuple(
                sorted(
                    {
                        provider.capability
                        for provider
                        in resolved_project.providers
                        if (
                            provider.module_key
                            == module_key
                        )
                    }
                )
            ),
            required_capabilities=tuple(
                sorted(
                    {
                        requirement.capability
                        for requirement
                        in resolved_project.requirements
                        if (
                            requirement.module_key
                            == module_key
                        )
                    }
                )
            ),
            direct_dependencies=tuple(
                sorted(
                    dependencies_by_module[
                        module_key
                    ]
                )
            ),
            direct_dependents=tuple(
                sorted(
                    dependents_by_module[
                        module_key
                    ]
                )
            ),
        )
        for module_key, module
        in sorted(module_by_key.items())
    )

    return ProjectModuleLifecycleGraph(
        nodes=nodes,
        relations=relations,
        resolution_order=tuple(
            module.key
            for module
            in resolved_project.ordered_modules()
        ),
    )