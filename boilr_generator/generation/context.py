"""Shared Jinja context construction for module generation."""

from copy import deepcopy
from typing import Any

from boilr_generator.core.module import ResolvedModule
from boilr_generator.core.project import ResolvedProject


def build_module_context(
    project: ResolvedProject,
    module: ResolvedModule,
) -> dict[str, Any]:
    """Build the complete generation context for one module."""
    return {
        **module.variables,
        "options": deepcopy(module.options),
        "dependencies": deepcopy(
            module.manifest.dependencies
        ),
        "bindings": project.binding_context_for(module.key),
        "extensions": project.extension_context_for(module.key),
    }