"""Public domain models exposed by the Boilr core."""

from boilr_generator.core.capabilities import (
    CapabilityBinding,
    CapabilityProvider,
    CapabilityRequirement,
)
from boilr_generator.core.contributions import (
    Contribution,
    ExtensionPoint,
)
from boilr_generator.core.dependencies import (
    DependencyEdge,
    DependencyGraph,
)
from boilr_generator.core.module import ResolvedModule
from boilr_generator.core.project import ResolvedProject

__all__ = [
    "CapabilityBinding",
    "CapabilityProvider",
    "CapabilityRequirement",
    "ResolvedModule",
    "ResolvedProject",
    "DependencyEdge",
    "DependencyGraph",
    "Contribution",
    "ExtensionPoint",
]