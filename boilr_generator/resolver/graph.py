"""Dependency graph construction from capability bindings."""

from heapq import heappop, heappush

from boilr_generator.core.capabilities import (
    CapabilityBinding,
)
from boilr_generator.core.dependencies import (
    DependencyEdge,
    DependencyGraph,
)
from boilr_generator.core.module import ResolvedModule
from boilr_generator.exceptions import (
    BindingError,
    DependencyCycleError,
)


class DependencyGraphBuilder:
    """Build and validate module dependency graphs."""

    def build(
        self,
        modules: list[ResolvedModule],
        bindings: list[CapabilityBinding],
    ) -> DependencyGraph:
        """Build a directed graph and calculate its module order."""
        module_by_key = {
            module.key: module
            for module in modules
        }
        module_positions = {
            module.key: position
            for position, module in enumerate(modules)
        }

        edges = [
            self._create_edge(
                binding,
                module_by_key,
            )
            for binding in bindings
        ]

        adjacency: dict[str, set[str]] = {
            module.key: set()
            for module in modules
        }
        indegrees = {
            module.key: 0
            for module in modules
        }

        for edge in edges:
            provider_key = edge.provider_module_key
            consumer_key = edge.consumer_module_key

            if consumer_key in adjacency[provider_key]:
                continue

            adjacency[provider_key].add(consumer_key)
            indegrees[consumer_key] += 1

        ordered_module_keys = self._topological_sort(
            modules=modules,
            adjacency=adjacency,
            indegrees=indegrees,
            module_positions=module_positions,
        )

        return DependencyGraph(
            nodes=[
                module.key
                for module in modules
            ],
            edges=edges,
            ordered_module_keys=ordered_module_keys,
        )

    def _create_edge(
        self,
        binding: CapabilityBinding,
        module_by_key: dict[str, ResolvedModule],
    ) -> DependencyEdge:
        """Create one graph edge from a resolved binding."""
        missing_module_keys = [
            module_key
            for module_key in (
                binding.provider_module_key,
                binding.consumer_module_key,
            )
            if module_key not in module_by_key
        ]

        if missing_module_keys:
            raise BindingError(
                (
                    f"Binding '{binding.binding_key}' references "
                    "unknown modules."
                ),
                module_key=binding.consumer_module_key,
                field_path=(
                    f"bindings.{binding.consumer_module_key}."
                    f"{binding.binding_key}"
                ),
                context={
                    "binding_key": binding.binding_key,
                    "capability": binding.capability,
                    "missing_modules": missing_module_keys,
                },
                suggestion=(
                    "Ensure binding providers and consumers are "
                    "selected project modules."
                ),
            )

        return DependencyEdge(
            provider_module_key=binding.provider_module_key,
            consumer_module_key=binding.consumer_module_key,
            capability=binding.capability,
            binding_key=binding.binding_key,
        )

    def _topological_sort(
        self,
        *,
        modules: list[ResolvedModule],
        adjacency: dict[str, set[str]],
        indegrees: dict[str, int],
        module_positions: dict[str, int],
    ) -> list[str]:
        """Sort modules while respecting dependencies."""
        module_by_key = {
            module.key: module
            for module in modules
        }

        ready: list[tuple[int, int, str]] = []

        for module in modules:
            if indegrees[module.key] == 0:
                heappush(
                    ready,
                    (
                        module.priority,
                        module_positions[module.key],
                        module.key,
                    ),
                )

        ordered_module_keys: list[str] = []

        while ready:
            _, _, module_key = heappop(ready)
            ordered_module_keys.append(module_key)

            consumers = sorted(
                adjacency[module_key],
                key=lambda key: (
                    module_by_key[key].priority,
                    module_positions[key],
                    key,
                ),
            )

            for consumer_key in consumers:
                indegrees[consumer_key] -= 1

                if indegrees[consumer_key] == 0:
                    consumer = module_by_key[consumer_key]

                    heappush(
                        ready,
                        (
                            consumer.priority,
                            module_positions[consumer_key],
                            consumer_key,
                        ),
                    )

        if len(ordered_module_keys) != len(modules):
            cycle = self._find_cycle(
                adjacency=adjacency,
                indegrees=indegrees,
                module_by_key=module_by_key,
                module_positions=module_positions,
            )

            raise DependencyCycleError(
                (
                    "Dependency cycle detected: "
                    f"{' -> '.join(cycle)}."
                ),
                module_key=cycle[0],
                field_path="bindings",
                context={
                    "cycle": cycle,
                    "modules": list(
                        dict.fromkeys(cycle[:-1])
                    ),
                },
                suggestion=(
                    "Remove or redesign one of the capability "
                    "requirements involved in the cycle."
                ),
            )

        return ordered_module_keys

    def _find_cycle(
        self,
        *,
        adjacency: dict[str, set[str]],
        indegrees: dict[str, int],
        module_by_key: dict[str, ResolvedModule],
        module_positions: dict[str, int],
    ) -> list[str]:
        """Find one deterministic cycle in the unresolved graph."""
        unresolved = {
            module_key
            for module_key, indegree in indegrees.items()
            if indegree > 0
        }

        states = {
            module_key: 0
            for module_key in unresolved
        }
        path: list[str] = []

        def sort_key(module_key: str) -> tuple[int, int, str]:
            return (
                module_by_key[module_key].priority,
                module_positions[module_key],
                module_key,
            )

        def visit(module_key: str) -> list[str] | None:
            states[module_key] = 1
            path.append(module_key)

            for neighbor in sorted(
                adjacency[module_key],
                key=sort_key,
            ):
                if neighbor not in unresolved:
                    continue

                if states[neighbor] == 0:
                    cycle = visit(neighbor)

                    if cycle is not None:
                        return cycle

                elif states[neighbor] == 1:
                    cycle_start = path.index(neighbor)
                    return [
                        *path[cycle_start:],
                        neighbor,
                    ]

            path.pop()
            states[module_key] = 2
            return None

        for module_key in sorted(
            unresolved,
            key=sort_key,
        ):
            if states[module_key] != 0:
                continue

            cycle = visit(module_key)

            if cycle is not None:
                return cycle

        return []