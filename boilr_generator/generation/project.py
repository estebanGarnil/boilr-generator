"""Project generation planning and execution."""

import shutil
from pathlib import Path
from typing import Any

import yaml

from boilr_generator.core.generation_plan import (
    GenerationPlan,
    PlannedFile,
    PlannedRemoval,
)
from boilr_generator.exceptions import (
    FileConflictError,
    SourceNotFoundError,
)
from boilr_generator.generation.context import (
    build_module_context,
)
from boilr_generator.generation.docker import DockerComposeGenerator
from boilr_generator.generation.env import EnvGenerator
from boilr_generator.generation.files import FileGenerator
from boilr_generator.manifest.schemas import ProjectManifest
from boilr_generator.modules.registry import ModuleRegistry
from boilr_generator.modules.schemas import CopySource, RenderSource
from boilr_generator.resolver import Resolver


class ProjectGenerator:
    """Plan and execute project generation."""

    def __init__(self, registry: ModuleRegistry) -> None:
        self.registry = registry
        self.resolver = Resolver(registry)
        self.file_generator = FileGenerator()
        self.docker_generator = DockerComposeGenerator()
        self.env_generator = EnvGenerator()

    def plan(
        self,
        manifest: ProjectManifest,
        output_path: str | Path,
        clean: bool = False,
    ) -> GenerationPlan:
        """Create a generation plan without writing files."""
        output_path = Path(output_path)
        resolved_project = self.resolver.resolve(manifest)

        files: list[PlannedFile] = []
        removals: list[PlannedRemoval] = []

        for module in resolved_project.ordered_modules():
            module_key = module.manifest.meta.key
            module_path = self.registry.get_path(module_key)

            render_context = build_module_context(
                resolved_project,
                module,
            )

            for index, source in enumerate(
                module.manifest.sources.copy_sources
            ):
                copy_files, copy_removals = (
                    self._plan_copy_source(
                        module_key=module_key,
                        module_path=module_path,
                        source=source,
                        output_path=output_path,
                        field_path=(
                            f"modules.{module_key}.sources."
                            f"copy[{index}].from"
                        ),
                        clean=clean,
                    )
                )

                files.extend(copy_files)
                removals.extend(copy_removals)

            for index, source in enumerate(
                module.manifest.sources.render
            ):
                files.append(
                    self._plan_render_source(
                        module_key=module_key,
                        module_path=module_path,
                        source=source,
                        output_path=output_path,
                        field_path=(
                            f"modules.{module_key}.sources."
                            f"render[{index}].from"
                        ),
                        context=render_context,
                    )
                )

        docker_compose = self.docker_generator.generate(
            resolved_project
        )
        env = self.env_generator.generate(resolved_project)

        files.append(
            self._plan_generated_file(
                relative_path="docker-compose.yml",
                output_path=output_path,
                content=self._serialize_yaml(
                    docker_compose
                ),
            )
        )
        files.append(
            self._plan_generated_file(
                relative_path=".env",
                output_path=output_path,
                content=self._serialize_env(env),
            )
        )

        if clean:
            for planned_file in files:
                planned_file.action = "create"

        self._validate_file_conflicts(files)

        return GenerationPlan(
            resolved_project=resolved_project,
            output_path=output_path,
            files=files,
            docker_services=list(
                docker_compose.get("services", {}).keys()
            ),
            env_variables=list(env.keys()),
            clean_output=clean,
            removals=removals,
        )

    def execute(
        self,
        plan: GenerationPlan,
    ) -> None:
        """Apply a complete plan without recalculating outputs."""
        self._validate_file_conflicts(plan.files)

        output_path = plan.output_path

        if plan.clean_output and output_path.exists():
            shutil.rmtree(output_path)
        else:
            for removal in plan.removals:
                self._execute_removal(
                    removal=removal,
                    output_path=output_path,
                )

        output_path.mkdir(
            parents=True,
            exist_ok=True,
        )

        for planned_file in plan.files:
            if planned_file.action == "skip":
                continue

            destination_path = (
                planned_file.destination_path
            )
            destination_path.parent.mkdir(
                parents=True,
                exist_ok=True,
            )
            destination_path.write_bytes(
                planned_file.content
            )

            if planned_file.mode is not None:
                destination_path.chmod(
                    planned_file.mode
                )

    def _execute_removal(
        self,
        *,
        removal: PlannedRemoval,
        output_path: Path,
    ) -> None:
        """Apply one safe removal from the prepared plan."""
        self._validate_removal_path(
            path=removal.path,
            output_path=output_path,
            module_key=removal.module,
        )

        if not removal.path.exists():
            return

        if removal.path.is_dir():
            shutil.rmtree(removal.path)
        else:
            removal.path.unlink()

    def _serialize_yaml(
        self,
        data: dict[str, Any],
    ) -> bytes:
        """Serialize generated YAML into stable UTF-8 bytes."""
        return yaml.safe_dump(
            data,
            sort_keys=False,
            allow_unicode=True,
        ).encode("utf-8")

    def _serialize_env(
        self,
        env: dict[str, Any],
    ) -> bytes:
        """Serialize environment variables into UTF-8 bytes."""
        lines = [
            f"{key}={value}"
            for key, value in env.items()
        ]

        content = "\n".join(lines)

        if content:
            content += "\n"

        return content.encode("utf-8")

    def _plan_generated_file(
        self,
        relative_path: str,
        output_path: Path,
        content: bytes,
    ) -> PlannedFile:
        destination_path = output_path / relative_path

        return self._build_planned_file(
            source_path=None,
            destination_path=destination_path,
            output_path=output_path,
            operation="generate",
            module=None,
            strategy="overwrite",
            content=content,
        )

    def _plan_render_source(
        self,
        module_key: str,
        module_path: Path,
        source: RenderSource,
        output_path: Path,
        field_path: str,
        context: dict[str, Any],
    ) -> PlannedFile:
        source_path = module_path / source.from_
        destination_path = output_path / source.to

        rendered_content = (
            self.file_generator.render_template_content(
                template_path=source_path,
                destination_path=destination_path,
                context=context,
                module_key=module_key,
                field_path=field_path,
            )
        )

        return self._build_planned_file(
            source_path=source_path,
            destination_path=destination_path,
            output_path=output_path,
            operation="render",
            module=module_key,
            strategy="overwrite",
            content=rendered_content.encode("utf-8"),
        )

    def _plan_copy_source(
        self,
        module_key: str,
        module_path: Path,
        source: CopySource,
        output_path: Path,
        field_path: str,
        clean: bool,
    ) -> tuple[list[PlannedFile], list[PlannedRemoval]]:
        """Plan one copy source and its replacement removals."""
        source_path = module_path / source.from_
        destination_root = output_path / source.to

        if not source_path.exists():
            raise SourceNotFoundError(
                f"Source path not found: {source_path}",
                module_key=module_key,
                field_path=field_path,
                context={
                    "source_path": str(source_path),
                    "source_kind": "copy",
                },
                suggestion=(
                    "Check the source path declared in the module "
                    "manifest and ensure the referenced file or "
                    "directory is packaged."
                ),
            )

        source_files: list[tuple[Path, Path]] = []

        if source_path.is_file():
            source_files.append(
                (
                    source_path,
                    destination_root,
                )
            )
        else:
            for file_path in sorted(
                source_path.rglob("*")
            ):
                if not file_path.is_file():
                    continue

                relative_source_path = (
                    file_path.relative_to(source_path)
                )
                destination_path = (
                    destination_root
                    / relative_source_path
                )

                source_files.append(
                    (
                        file_path,
                        destination_path,
                    )
                )

        removals: list[PlannedRemoval] = []
        action_override: str | None = None

        if clean:
            action_override = "create"
        elif destination_root.exists():
            if source.strategy == "skip":
                action_override = "skip"

            elif source.strategy == "replace":
                action_override = "create"
                removals.append(
                    self._build_planned_removal(
                        path=destination_root,
                        output_path=output_path,
                        module_key=module_key,
                    )
                )

        planned_files = [
            self._build_planned_file(
                source_path=file_path,
                destination_path=destination_path,
                output_path=output_path,
                operation="copy",
                module=module_key,
                strategy=source.strategy,
                content=file_path.read_bytes(),
                mode=file_path.stat().st_mode & 0o777,
                action_override=action_override,
            )
            for file_path, destination_path in source_files
        ]

        return planned_files, removals

    def _build_planned_removal(
        self,
        *,
        path: Path,
        output_path: Path,
        module_key: str,
    ) -> PlannedRemoval:
        """Build a safe removal contained by the output path."""
        relative_path = self._validate_removal_path(
            path=path,
            output_path=output_path,
            module_key=module_key,
        )

        return PlannedRemoval(
            path=path,
            relative_path=relative_path,
            module=module_key,
            reason="replace",
        )

    def _validate_removal_path(
        self,
        *,
        path: Path,
        output_path: Path,
        module_key: str | None,
    ) -> str:
        """Reject removal of or outside the output directory."""
        resolved_output = output_path.resolve()
        resolved_path = path.resolve()

        try:
            relative_path = resolved_path.relative_to(
                resolved_output
            )
        except ValueError:
            relative_path = None

        if (
            relative_path is None
            or relative_path == Path(".")
        ):
            displayed_path = str(path)

            raise FileConflictError(
                (
                    "Unsafe planned removal outside the project "
                    f"output: '{displayed_path}'."
                ),
                module_key=module_key,
                field_path="generation.removals",
                context={
                    "reason": "unsafe_removal",
                    "removal_path": displayed_path,
                    "output_path": str(output_path),
                },
                suggestion=(
                    "Choose a copy destination located strictly "
                    "inside the project output directory."
                ),
            )

        return str(relative_path)

    def _build_planned_file(
        self,
        source_path: Path | None,
        destination_path: Path,
        output_path: Path,
        operation: str,
        module: str | None,
        strategy: str,
        content: bytes,
        mode: int | None = None,
        action_override: str | None = None,
    ) -> PlannedFile:
        action = (
            action_override
            if action_override is not None
            else self._get_planned_action(
                destination_path=destination_path,
                strategy=strategy,
            )
        )

        return PlannedFile(
            source_path=source_path,
            destination_path=destination_path,
            relative_destination_path=str(
                destination_path.relative_to(output_path)
            ),
            operation=operation,
            action=action,
            module=module,
            content=content,
            mode=mode,
        )

    def _get_planned_action(
        self,
        destination_path: Path,
        strategy: str,
    ) -> str:
        if not destination_path.exists():
            return "create"

        if strategy == "skip":
            return "skip"

        return "overwrite"

    def _validate_file_conflicts(
        self,
        files: list[PlannedFile],
    ) -> None:
        """Reject multiple operations targeting the same destination."""
        destinations: dict[Path, PlannedFile] = {}

        for planned_file in files:
            destination_key = planned_file.destination_path.resolve()
            existing_file = destinations.get(destination_key)

            if existing_file is None:
                destinations[destination_key] = planned_file
                continue

            relative_path = planned_file.relative_destination_path
            first_origin = existing_file.module or "project"
            conflicting_origin = planned_file.module or "project"

            raise FileConflictError(
                (
                    "Multiple generation operations target the same "
                    f"destination: '{relative_path}'."
                ),
                module_key=(
                    planned_file.module
                    or existing_file.module
                ),
                field_path=(
                    f"generation.files[{relative_path}]"
                ),
                context={
                    "destination": relative_path,
                    "first_module": first_origin,
                    "conflicting_module": conflicting_origin,
                    "first_operation": existing_file.operation,
                    "conflicting_operation": (
                        planned_file.operation
                    ),
                },
                suggestion=(
                    "Change one of the destination paths so that every "
                    "generated file has a single owner."
                ),
            )
