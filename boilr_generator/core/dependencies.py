"""Domain models for module dependency resolution."""

from pydantic import BaseModel, Field


class DependencyEdge(BaseModel):
    """Directed dependency from a provider to a consumer."""

    provider_module_key: str = Field(min_length=1)
    consumer_module_key: str = Field(min_length=1)
    capability: str = Field(min_length=1)
    binding_key: str = Field(min_length=1)


class DependencyGraph(BaseModel):
    """Resolved module dependency graph."""

    nodes: list[str] = Field(default_factory=list)
    edges: list[DependencyEdge] = Field(default_factory=list)
    ordered_module_keys: list[str] = Field(default_factory=list)

    def dependencies_for(
        self,
        module_key: str,
    ) -> list[str]:
        """Return direct dependencies of one consumer module."""
        return list(
            dict.fromkeys(
                edge.provider_module_key
                for edge in self.edges
                if edge.consumer_module_key == module_key
            )
        )

    def dependents_for(
        self,
        module_key: str,
    ) -> list[str]:
        """Return direct consumers of one provider module."""
        return list(
            dict.fromkeys(
                edge.consumer_module_key
                for edge in self.edges
                if edge.provider_module_key == module_key
            )
        )