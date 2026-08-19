"""Project generation planning and execution."""

import shutil
from pathlib import Path, PurePosixPath
from typing import Any, NoReturn

import yaml

from boilr_generator.core.generation_plan import (
    GenerationPlan,
    PlannedDirectory,
    PlannedFile,
    PlannedPathState,
    PlannedRemoval,
    RemovalReason,
)
from boilr_generator.exceptions import (
    FileConflictError,
    OutputDirectoryError,
    SourceNotFoundError,
    SourceReadError,
    StaleGenerationPlanError,
    UnsafePathError,
)
from boilr_generator.generation.context import (
    build_module_context,
)
from boilr_generator.generation.docker import DockerComposeGenerator
from boilr_generator.generation.env import EnvGenerator
from boilr_generator.generation.files import FileGenerator
from boilr_generator.generation.filesystem import (
    capture_output_state,
    find_changed_output_paths,
)
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

        if clean:
            self._validate_clean_output_path(output_path)

        resolved_project = self.resolver.resolve(manifest)
        initial_output_state = capture_output_state(
            output_path
        )

        files: list[PlannedFile] = []
        removals = (
            self._plan_removals_from_state(
                states=initial_output_state,
                reason="clean",
                module_key=None,
            )
            if clean
            else []
        )

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
                        initial_output_state=(
                            initial_output_state
                        ),
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

        directories = self._plan_directories(
            output_path=output_path,
            initial_output_state=initial_output_state,
            removals=removals,
            files=files,
        )

        return GenerationPlan(
            resolved_project=resolved_project,
            output_path=output_path,
            initial_output_state=initial_output_state,
            directories=directories,
            files=files,
            docker_services=list(
                docker_compose.get("services", {}).keys()
            ),
            env_variables=list(env.keys()),
            clean_output=clean,
            removals=removals,
        )

    def _plan_removals_from_state(
        self,
        *,
        states: list[PlannedPathState],
        reason: RemovalReason,
        module_key: str | None,
    ) -> list[PlannedRemoval]:
        """Build exact removals ordered deepest first."""
        existing_states = [
            state
            for state in states
            if state.exists
        ]

        ordered_states = sorted(
            existing_states,
            key=lambda state: (
                -len(
                    PurePosixPath(
                        state.relative_path
                    ).parts
                ),
                state.relative_path,
            ),
        )

        return [
            PlannedRemoval(
                path=state.path,
                relative_path=state.relative_path,
                module=module_key,
                reason=reason,
                kind=state.kind,
            )
            for state in ordered_states
        ]

    def _plan_replace_removals(
        self,
        *,
        destination_root: Path,
        output_path: Path,
        initial_output_state: list[PlannedPathState],
        module_key: str,
    ) -> list[PlannedRemoval]:
        """Plan one exact replacement subtree."""
        self._validate_removal_path(
            path=destination_root,
            output_path=output_path,
            module_key=module_key,
        )

        subtree_states = [
            state
            for state in initial_output_state
            if (
                state.exists
                and (
                    state.path == destination_root
                    or destination_root
                    in state.path.parents
                )
            )
        ]

        return self._plan_removals_from_state(
            states=subtree_states,
            reason="replace",
            module_key=module_key,
        )

    def _plan_directories(
        self,
        *,
        output_path: Path,
        initial_output_state: list[PlannedPathState],
        removals: list[PlannedRemoval],
        files: list[PlannedFile],
    ) -> list[PlannedDirectory]:
        """Plan exact directory creations in parent-first order."""
        required_directories: dict[
            Path,
            str | None,
        ] = {
            output_path: None,
        }

        for planned_file in files:
            if planned_file.action == "skip":
                continue

            parent = planned_file.destination_path.parent

            while parent != output_path:
                required_directories.setdefault(
                    parent,
                    planned_file.module,
                )
                parent = parent.parent

        initial_state_by_path = {
            state.path: state
            for state in initial_output_state
        }
        removal_paths = {
            removal.path
            for removal in removals
        }

        directories: list[PlannedDirectory] = []

        for directory_path, module_key in (
            required_directories.items()
        ):
            relative_path = (
                "."
                if directory_path == output_path
                else directory_path.relative_to(
                    output_path
                ).as_posix()
            )

            if directory_path in removal_paths:
                directories.append(
                    PlannedDirectory(
                        path=directory_path,
                        relative_path=relative_path,
                        reason=(
                            "output"
                            if directory_path
                            == output_path
                            else "parent"
                        ),
                        module=module_key,
                    )
                )
                continue

            current_state = initial_state_by_path.get(
                directory_path
            )

            if (
                current_state is None
                or not current_state.exists
            ):
                directories.append(
                    PlannedDirectory(
                        path=directory_path,
                        relative_path=relative_path,
                        reason=(
                            "output"
                            if directory_path
                            == output_path
                            else "parent"
                        ),
                        module=module_key,
                    )
                )
                continue

            if current_state.kind == "directory":
                continue

            raise FileConflictError(
                (
                    "A required directory path is occupied "
                    f"by a {current_state.kind}: "
                    f"'{relative_path}'."
                ),
                module_key=module_key,
                field_path=(
                    "generation.directories"
                    f"[{relative_path}]"
                ),
                context={
                    "reason": "directory_path_conflict",
                    "path": str(directory_path),
                    "relative_path": relative_path,
                    "existing_kind": current_state.kind,
                },
                suggestion=(
                    "Remove or rename the conflicting path, "
                    "or choose another generation destination."
                ),
            )

        return sorted(
            directories,
            key=lambda directory: (
                len(
                    PurePosixPath(
                        directory.relative_path
                    ).parts
                ),
                directory.relative_path,
            ),
        )

    def _validate_clean_output_path(
        self,
        output_path: Path,
    ) -> None:
        """Reject dangerous clean output directories."""
        try:
            resolved_output = output_path.resolve()
        except OSError as error:
            raise OutputDirectoryError(
                (
                    "Unable to resolve the output directory "
                    f"before cleaning: '{output_path}'."
                ),
                field_path="generation.output_path",
                context={
                    "reason": "path_resolution_failed",
                    "output_path": str(output_path),
                    "error_type": type(error).__name__,
                },
                suggestion=(
                    "Choose an accessible dedicated output "
                    "directory."
                ),
            ) from error

        if output_path.is_symlink():
            self._raise_unsafe_clean_output(
                output_path=output_path,
                resolved_output=resolved_output,
                reason="output_is_symbolic_link",
            )

        if (
            output_path.exists()
            and not output_path.is_dir()
        ):
            self._raise_unsafe_clean_output(
                output_path=output_path,
                resolved_output=resolved_output,
                reason="output_is_not_directory",
            )

        filesystem_root = Path(
            resolved_output.anchor
        ).resolve()

        protected_paths = [
            (
                "filesystem_root",
                filesystem_root,
            ),
            (
                "home_directory",
                Path.home().resolve(),
            ),
            (
                "current_working_directory",
                Path.cwd().resolve(),
            ),
        ]

        for protected_reason, protected_path in (
            protected_paths
        ):
            if resolved_output == protected_path:
                self._raise_unsafe_clean_output(
                    output_path=output_path,
                    resolved_output=resolved_output,
                    reason=protected_reason,
                    protected_path=protected_path,
                )

            if resolved_output in protected_path.parents:
                self._raise_unsafe_clean_output(
                    output_path=output_path,
                    resolved_output=resolved_output,
                    reason=(
                        f"ancestor_of_{protected_reason}"
                    ),
                    protected_path=protected_path,
                )

    def _raise_unsafe_clean_output(
        self,
        *,
        output_path: Path,
        resolved_output: Path,
        reason: str,
        protected_path: Path | None = None,
    ) -> None:
        """Raise a structured unsafe-clean error."""
        context = {
            "reason": reason,
            "output_path": str(output_path),
            "resolved_output_path": str(
                resolved_output
            ),
        }

        if protected_path is not None:
            context["protected_path"] = str(
                protected_path
            )

        raise OutputDirectoryError(
            (
                "Refusing to clean unsafe output directory: "
                f"'{output_path}'."
            ),
            field_path="generation.output_path",
            context=context,
            suggestion=(
                "Choose a dedicated project directory that is "
                "not a system, home, current, or parent directory."
            ),
        )

    def execute(
        self,
        plan: GenerationPlan,
    ) -> None:
        """Apply a complete plan without recalculating outputs."""
        output_path = plan.output_path
        self._validate_initial_output_state(plan)

        self._validate_file_conflicts(plan.files)

        if plan.clean_output:
            self._validate_clean_output_path(output_path)

        for planned_file in plan.files:
            self._validate_destination_path(
                path=planned_file.destination_path,
                output_path=output_path,
                module_key=planned_file.module,
                field_path=(
                    "generation.files."
                    f"{planned_file.relative_destination_path}"
                ),
            )

        for removal in plan.removals:
            self._validate_removal_path(
                path=removal.path,
                output_path=output_path,
                module_key=removal.module,
                allow_output_root=(
                    removal.reason == "clean"
                ),
            )

        if plan.clean_output and output_path.exists():
            self._remove_clean_output(output_path)
        else:
            for removal in plan.removals:
                self._execute_removal(
                    removal=removal,
                    output_path=output_path,
                )

        self._create_output_directory(
            path=output_path,
            module_key=None,
            field_path="generation.output_path",
            operation="create_output_directory",
        )

        for planned_file in plan.files:
            if planned_file.action == "skip":
                continue

            self._write_planned_file(planned_file)

    @staticmethod
    def _validate_initial_output_state(
        plan: GenerationPlan,
    ) -> None:
        """Reject a plan whose initial state is missing or stale."""
        if not plan.initial_output_state:
            raise StaleGenerationPlanError(
                (
                    "Cannot execute a generation plan without "
                    "a captured initial output state."
                ),
                field_path=(
                    "generation.initial_output_state"
                ),
                context={
                    "reason": (
                        "missing_initial_output_state"
                    ),
                    "output_path": str(
                        plan.output_path
                    ),
                },
                suggestion=(
                    "Create a new plan immediately before "
                    "executing it."
                ),
            )

        actual_output_state = capture_output_state(
            plan.output_path
        )
        changed_paths = find_changed_output_paths(
            plan.initial_output_state,
            actual_output_state,
        )

        if not changed_paths:
            return

        raise StaleGenerationPlanError(
            (
                "Cannot execute the generation plan because "
                "the output filesystem changed after planning."
            ),
            field_path="generation.initial_output_state",
            context={
                "reason": "output_state_changed",
                "output_path": str(plan.output_path),
                "changed_paths": changed_paths,
                "expected_paths_count": len(
                    plan.initial_output_state
                ),
                "actual_paths_count": len(
                    actual_output_state
                ),
            },
            suggestion=(
                "Create a new plan from the current output "
                "state before executing it."
            ),
        )

    def _remove_clean_output(
        self,
        output_path: Path,
    ) -> None:
        """Remove a validated output directory."""
        try:
            shutil.rmtree(output_path)
        except OSError as error:
            self._raise_output_error(
                path=output_path,
                module_key=None,
                field_path="generation.output_path",
                operation="clean_output",
                error=error,
            )

    def _create_output_directory(
        self,
        *,
        path: Path,
        module_key: str | None,
        field_path: str,
        operation: str,
    ) -> None:
        """Create one output directory."""
        try:
            path.mkdir(
                parents=True,
                exist_ok=True,
            )
        except OSError as error:
            self._raise_output_error(
                path=path,
                module_key=module_key,
                field_path=field_path,
                operation=operation,
                error=error,
            )

    def _write_planned_file(
        self,
        planned_file: PlannedFile,
    ) -> None:
        """Write one planned file with structured errors."""
        destination_path = planned_file.destination_path
        field_path = (
            "generation.files."
            f"{planned_file.relative_destination_path}"
        )

        self._create_output_directory(
            path=destination_path.parent,
            module_key=planned_file.module,
            field_path=field_path,
            operation="create_parent_directory",
        )

        try:
            destination_path.write_bytes(
                planned_file.content
            )
        except OSError as error:
            self._raise_output_error(
                path=destination_path,
                module_key=planned_file.module,
                field_path=field_path,
                operation="write_file",
                error=error,
            )

        if planned_file.mode is None:
            return

        try:
            destination_path.chmod(
                planned_file.mode
            )
        except OSError as error:
            self._raise_output_error(
                path=destination_path,
                module_key=planned_file.module,
                field_path=field_path,
                operation="set_file_mode",
                error=error,
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

        field_path = (
            "generation.removals."
            f"{removal.relative_path}"
        )

        try:
            if (
                removal.path.is_symlink()
                or not removal.path.is_dir()
            ):
                removal.path.unlink()
            else:
                shutil.rmtree(removal.path)
        except FileNotFoundError:
            return
        except OSError as error:
            self._raise_output_error(
                path=removal.path,
                module_key=removal.module,
                field_path=field_path,
                operation="remove_path",
                error=error,
            )

    def _raise_output_error(
        self,
        *,
        path: Path,
        module_key: str | None,
        field_path: str,
        operation: str,
        error: OSError,
    ) -> NoReturn:
        """Raise a structured output filesystem error."""
        context = {
            "operation": operation,
            "path": str(path),
            "error_type": type(error).__name__,
        }

        if error.errno is not None:
            context["errno"] = error.errno

        raise OutputDirectoryError(
            (
                f"Output operation '{operation}' failed "
                f"for '{path}': {error}"
            ),
            module_key=module_key,
            field_path=field_path,
            context=context,
            suggestion=(
                "Check directory permissions, available disk "
                "space, and whether another process is using "
                "the destination."
            ),
        ) from error


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

        destination_field_path = (
            f"{field_path.rsplit('.', 1)[0]}.to"
        )

        self._validate_source_path(
            path=source_path,
            module_path=module_path,
            module_key=module_key,
            field_path=field_path,
        )
        self._validate_destination_path(
            path=destination_path,
            output_path=output_path,
            module_key=module_key,
            field_path=destination_field_path,
        )

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
        initial_output_state: (
            list[PlannedPathState] | None
        ) = None,
    ) -> tuple[list[PlannedFile], list[PlannedRemoval]]:
        """Plan one copy source and its replacement removals."""
        source_path = module_path / source.from_
        destination_root = output_path / source.to

        destination_field_path = (
            f"{field_path.rsplit('.', 1)[0]}.to"
        )

        self._validate_source_path(
            path=source_path,
            module_path=module_path,
            module_key=module_key,
            field_path=field_path,
        )
        self._validate_destination_path(
            path=destination_root,
            output_path=output_path,
            module_key=module_key,
            field_path=destination_field_path,
            allow_output_root=True,
        )

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
            try:
                source_entries = sorted(
                    source_path.rglob("*")
                )
            except OSError as error:
                self._raise_source_read_error(
                    path=source_path,
                    module_key=module_key,
                    field_path=field_path,
                    operation="list_directory",
                    error=error,
                )

            for file_path in source_entries:
                if not file_path.is_file():
                    continue

                self._validate_source_path(
                    path=file_path,
                    module_path=module_path,
                    module_key=module_key,
                    field_path=field_path,
                )

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

        if initial_output_state is None:
            initial_output_state = capture_output_state(
                output_path
            )

        destination_state = next(
            (
                state
                for state in initial_output_state
                if state.path == destination_root
            ),
            None,
        )
        destination_exists = (
            destination_state is not None
            and destination_state.exists
        )

        removals: list[PlannedRemoval] = []
        action_override: str | None = None

        if clean:
            action_override = "create"
        elif destination_exists:
            if source.strategy == "skip":
                action_override = "skip"

            elif source.strategy == "replace":
                action_override = "create"
                removals.extend(
                    self._plan_replace_removals(
                        destination_root=(
                            destination_root
                        ),
                        output_path=output_path,
                        initial_output_state=(
                            initial_output_state
                        ),
                        module_key=module_key,
                    )
                )

        planned_files: list[PlannedFile] = []

        for file_path, destination_path in source_files:
            content, mode = self._read_copy_source(
                path=file_path,
                module_key=module_key,
                field_path=field_path,
            )

            planned_files.append(
                self._build_planned_file(
                    source_path=file_path,
                    destination_path=destination_path,
                    output_path=output_path,
                    operation="copy",
                    module=module_key,
                    strategy=source.strategy,
                    content=content,
                    mode=mode,
                    action_override=action_override,
                )
            )

        return planned_files, removals

    def _read_copy_source(
        self,
        *,
        path: Path,
        module_key: str,
        field_path: str,
    ) -> tuple[bytes, int]:
        """Read one copy source and its permission mode."""
        try:
            content = path.read_bytes()
            mode = path.stat().st_mode & 0o777
        except OSError as error:
            self._raise_source_read_error(
                path=path,
                module_key=module_key,
                field_path=field_path,
                operation="read_copy_source",
                error=error,
            )

        return content, mode

    def _raise_source_read_error(
        self,
        *,
        path: Path,
        module_key: str,
        field_path: str,
        operation: str,
        error: OSError,
    ) -> NoReturn:
        """Raise a structured source filesystem error."""
        context = {
            "reason": "source_read_failed",
            "source_kind": "copy",
            "source_path": str(path),
            "operation": operation,
            "error_type": type(error).__name__,
        }

        if error.errno is not None:
            context["errno"] = error.errno

        raise SourceReadError(
            f"Unable to read source '{path}': {error}",
            module_key=module_key,
            field_path=field_path,
            context=context,
            suggestion=(
                "Check that the source exists and that its "
                "contents and metadata are readable."
            ),
        ) from error

    def _validate_source_path(
        self,
        *,
        path: Path,
        module_path: Path,
        module_key: str,
        field_path: str,
    ) -> str:
        """Require a source to remain inside its module."""
        return self._validate_contained_path(
            path=path,
            allowed_root=module_path,
            module_key=module_key,
            field_path=field_path,
            path_kind="source",
            allow_root=True,
        )

    def _validate_destination_path(
        self,
        *,
        path: Path,
        output_path: Path,
        module_key: str | None,
        field_path: str,
        allow_output_root: bool = False,
    ) -> str:
        """Require a destination to remain inside the output."""
        return self._validate_contained_path(
            path=path,
            allowed_root=output_path,
            module_key=module_key,
            field_path=field_path,
            path_kind="destination",
            allow_root=allow_output_root,
        )

    def _validate_contained_path(
        self,
        *,
        path: Path,
        allowed_root: Path,
        module_key: str | None,
        field_path: str,
        path_kind: str,
        allow_root: bool,
    ) -> str:
        """Validate lexical paths and resolved symbolic links."""
        resolved_root = allowed_root.resolve()
        resolved_path = path.resolve()

        try:
            relative_path = resolved_path.relative_to(
                resolved_root
            )
        except ValueError:
            relative_path = None

        if (
            relative_path is None
            or (
                relative_path == Path(".")
                and not allow_root
            )
        ):
            root_description = (
                "module directory"
                if path_kind == "source"
                else "project output directory"
            )

            raise UnsafePathError(
                (
                    f"Unsafe {path_kind} path outside the "
                    f"{root_description}: '{path}'."
                ),
                module_key=module_key,
                field_path=field_path,
                context={
                    "reason": f"unsafe_{path_kind}",
                    "path_kind": path_kind,
                    f"{path_kind}_path": str(path),
                    "resolved_path": str(resolved_path),
                    "allowed_root": str(resolved_root),
                },
                suggestion=(
                    f"Choose a {path_kind} path located inside "
                    f"the {root_description}."
                ),
            )

        return str(relative_path)

    def _validate_removal_path(
        self,
        *,
        path: Path,
        output_path: Path,
        module_key: str | None,
        allow_output_root: bool = False,
    ) -> str:
        """Reject removal of or outside the output directory."""
        return self._validate_contained_path(
            path=path,
            allowed_root=output_path,
            module_key=module_key,
            field_path="generation.removals",
            path_kind="removal",
            allow_root=allow_output_root,
        )

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
        relative_destination_path = (
            self._validate_destination_path(
                path=destination_path,
                output_path=output_path,
                module_key=module,
                field_path="generation.files",
            )
        )

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
            relative_destination_path=relative_destination_path,
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
