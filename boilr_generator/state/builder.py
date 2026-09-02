"""Build persistent state from a prepared generation plan."""

from collections.abc import Sequence
from pathlib import PurePosixPath
from typing import Protocol

from boilr_generator.core.project import ResolvedProject
from boilr_generator.manifest.schemas import ProjectManifest
from boilr_generator.state.schemas import (
    ProjectState,
    StateBinding,
    StateModule,
    StateProject,
    StateResource,
)
from boilr_generator.state.serialization import fingerprint_model


class PlannedStateFile(Protocol):
    """Filesystem-plan values required to build one state resource."""

    resource_id: str
    default_relative_path: str
    relative_destination_path: str
    action: str
    owner: str | None
    contributors: list[str]
    content_size: int
    content_sha256: str
    mode: int | None


def build_initial_project_state(
    *,
    manifest: ProjectManifest,
    resolved_project: ResolvedProject,
    files: Sequence[PlannedStateFile],
    generator_version: str,
) -> ProjectState:
    """Build the baseline created by a first successful generation."""
    if manifest.project != resolved_project.project:
        raise ValueError(
            "The project manifest and resolved project do not match."
        )

    unsupported_actions = sorted(
        {
            planned_file.action
            for planned_file in files
            if planned_file.action
            not in {
                "create",
                "overwrite",
                "skip",
            }
        }
    )

    if unsupported_actions:
        raise ValueError(
            "Unsupported planned file actions: "
            f"{', '.join(unsupported_actions)}."
        )

    return ProjectState(
        schema_version=1,
        generator_version=generator_version,
        project=StateProject(
            name=manifest.project.name,
            type=manifest.project.type,
            version=manifest.project.version,
            manifest_sha256=fingerprint_model(manifest),
        ),
        modules=tuple(
            StateModule(
                key=module.key,
                version=module.manifest.meta.version,
                origin="builtin",
                manifest_sha256=fingerprint_model(
                    module.manifest
                ),
                destination=PurePosixPath(
                    module.manifest.assembly.destination_root
                ).as_posix(),
            )
            for module in resolved_project.modules
        ),
        bindings=tuple(
            StateBinding(
                consumer_module=(
                    binding.consumer_module_key
                ),
                binding=binding.binding_key,
                capability=binding.capability,
                provider_module=(
                    binding.provider_module_key
                ),
            )
            for binding in resolved_project.bindings
        ),
        resources=tuple(
            StateResource(
                id=planned_file.resource_id,
                kind="file",
                default_path=(
                    planned_file.default_relative_path
                ),
                desired_path=(
                    planned_file.relative_destination_path
                ),
                materialized_path=(
                    planned_file.relative_destination_path
                ),
                management="generated",
                scope="shared",
                owner=planned_file.owner,
                contributors=tuple(
                    planned_file.contributors
                ),
                content_size=planned_file.content_size,
                content_sha256=(
                    planned_file.content_sha256
                ),
                mode=planned_file.mode,
                link_target=None,
            )
            for planned_file in files
            if planned_file.action != "skip"
        ),
    )