"""Project generation planning and execution."""

from importlib.metadata import version
from pathlib import Path, PurePosixPath
from typing import Any, Literal, NoReturn

import yaml

from boilr_generator.core.generation_plan import (
    GenerationPlan,
    PlannedDirectory,
    PlannedFile,
    PlannedPathState,
    PlannedRemoval,
    ProjectUpdatePlan,
    RemovalReason,
)
from boilr_generator.core.project import ResolvedProject
from boilr_generator.exceptions import (
    FileConflictError,
    OutputDirectoryError,
    SourceNotFoundError,
    SourceReadError,
    StaleGenerationPlanError,
    StateTransactionError,
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
    is_reserved_state_path,
)
from boilr_generator.generation.update import (
    plan_empty_container_removals,
)
from boilr_generator.manifest.schemas import ProjectManifest
from boilr_generator.modules.registry import ModuleRegistry
from boilr_generator.modules.schemas import (
    CopySource,
    RenderSource,
    ResourceInputs,
)
from boilr_generator.resolver import Resolver
from boilr_generator.state import (
    ProjectState,
    build_initial_project_state,
)
from boilr_generator.state.storage import (
    STATE_DIRECTORY_NAME,
    ProjectStateStorage,
)


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
                        resolved_project=resolved_project,
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
                resource_id="core:docker-compose",
                relative_path="docker-compose.yml",
                output_path=output_path,
                contributors=(
                    self._core_resource_contributors(
                        resolved_project,
                        resource="docker",
                    )
                ),
                content=self._serialize_yaml(
                    docker_compose
                ),
            )
        )
        files.append(
            self._plan_generated_file(
                resource_id="core:environment",
                relative_path=".env",
                output_path=output_path,
                contributors=(
                    self._core_resource_contributors(
                        resolved_project,
                        resource="environment",
                    )
                ),
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
        desired_state = build_initial_project_state(
            manifest=manifest,
            resolved_project=resolved_project,
            files=files,
            generator_version=version("boilr"),
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
            desired_state=desired_state,
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
            if (
                state.exists
                and state.relative_path != "."
            )
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
        """Execute one validated generation plan."""
        output_path = plan.output_path
        desired_state = plan.desired_state

        state_storage = (
            ProjectStateStorage(output_path)
            if desired_state is not None
            else None
        )

        self._validate_initial_output_state(plan)
        self._validate_file_conflicts(plan.files)

        if plan.clean_output:
            self._validate_clean_output_path(
                output_path
            )

        for directory in plan.directories:
            self._validate_destination_path(
                output_path=output_path,
                path=directory.path,
                module_key=directory.module,
                field_path=(
                    "generation.directories"
                    f"[{directory.relative_path}]"
                ),
                allow_output_root=(
                    directory.reason == "output"
                ),
            )

        for planned_file in plan.files:
            self._validate_destination_path(
                output_path=output_path,
                path=planned_file.destination_path,
                module_key=planned_file.module,
                field_path=(
                    "generation.files"
                    f"[{planned_file.relative_destination_path}]"
                ),
            )

        for removal in plan.removals:
            self._validate_removal_path(
                output_path=output_path,
                path=removal.path,
                module_key=removal.module,
                allow_output_root=(
                    removal.reason == "clean"
                ),
            )

        if (
            state_storage is not None
            and desired_state is not None
        ):
            self._begin_state_transaction(
                storage=state_storage,
                state=desired_state,
            )

        for removal in plan.removals:
            self._execute_removal(removal)

        for directory in plan.directories:
            if (
                state_storage is not None
                and directory.path == output_path
            ):
                continue

            self._create_planned_directory(
                directory
            )

        for planned_file in plan.files:
            if planned_file.action == "skip":
                continue

            self._write_planned_file(
                planned_file
            )

        if (
            state_storage is not None
            and desired_state is not None
        ):
            self._commit_state_transaction(
                storage=state_storage,
                state=desired_state,
            )

    def execute_update(
        self,
        update_plan: ProjectUpdatePlan,
    ) -> None:
        """Execute one precomputed safe project update."""
        execution_plan = (
            self._validate_update_execution_contract(
                update_plan
            )
        )
        storage = ProjectStateStorage(
            execution_plan.output_path
        )

        self._validate_update_state_baseline(
            update_plan=update_plan,
            storage=storage,
        )
        self._validate_initial_output_state(
            execution_plan
        )

        if not update_plan.has_changes:
            return

        self.execute(execution_plan)

    @staticmethod
    def _validate_update_execution_contract(
        update_plan: ProjectUpdatePlan,
    ) -> GenerationPlan:
        """Reject incomplete, conflicting, or altered update plans."""
        if update_plan.conflicts:
            raise FileConflictError(
                (
                    "Cannot execute the project update while "
                    "resource conflicts remain."
                ),
                field_path="generation.update.conflicts",
                context={
                    "reason": "update_conflicts",
                    "conflicts": [
                        conflict.to_dict()
                        for conflict
                        in update_plan.conflicts
                    ],
                },
                suggestion=(
                    "Resolve or reconcile every reported "
                    "resource conflict, then create a new "
                    "update plan."
                ),
            )

        execution_plan = update_plan.execution_plan

        if execution_plan is None:
            raise StaleGenerationPlanError(
                (
                    "Cannot execute a project update without "
                    "a materialized execution plan."
                ),
                field_path=(
                    "generation.update.execution_plan"
                ),
                context={
                    "reason": (
                        "missing_update_execution_plan"
                    ),
                    "output_path": str(
                        update_plan.candidate_plan.output_path
                    ),
                },
                suggestion=(
                    "Create a new project update plan before "
                    "executing it."
                ),
            )

        contract_errors: list[str] = []
        candidate_plan = update_plan.candidate_plan

        if candidate_plan.clean_output:
            contract_errors.append(
                "candidate_plan_is_clean"
            )

        if execution_plan.clean_output:
            contract_errors.append(
                "execution_plan_is_clean"
            )

        if (
            execution_plan.output_path
            != candidate_plan.output_path
        ):
            contract_errors.append(
                "output_path_mismatch"
            )

        if (
            execution_plan.resolved_project
            != candidate_plan.resolved_project
        ):
            contract_errors.append(
                "resolved_project_mismatch"
            )

        if (
            execution_plan.initial_output_state
            != candidate_plan.initial_output_state
        ):
            contract_errors.append(
                "initial_output_state_mismatch"
            )

        if (
            execution_plan.desired_state
            != update_plan.desired_state
        ):
            contract_errors.append(
                "desired_state_mismatch"
            )

        change_ids = [
            change.resource_id
            for change in update_plan.changes
        ]

        if len(change_ids) != len(set(change_ids)):
            contract_errors.append(
                "duplicate_update_changes"
            )

        expected_file_actions = {
            "create": "create",
            "replace": "overwrite",
            "relocate": "create",
        }
        expected_file_operations: list[
            tuple[str, str, str]
        ] = []

        for change in update_plan.changes:
            file_action = expected_file_actions.get(
                change.action
            )

            if file_action is None:
                continue

            if change.target_path is None:
                contract_errors.append(
                    "missing_change_target:"
                    f"{change.resource_id}"
                )
                continue

            expected_file_operations.append(
                (
                    change.resource_id,
                    file_action,
                    change.target_path,
                )
            )

        actual_file_operations = [
            (
                planned_file.resource_id,
                planned_file.action,
                planned_file.relative_destination_path,
            )
            for planned_file in execution_plan.files
        ]

        if sorted(expected_file_operations) != sorted(
            actual_file_operations
        ):
            contract_errors.append(
                "file_operations_mismatch"
            )

        current_resources = {
            resource.id: resource
            for resource
            in update_plan.current_state.resources
        }
        desired_resources = {
            resource.id: resource
            for resource
            in update_plan.desired_state.resources
        }
        output_path = execution_plan.output_path
        expected_resource_removals: list[
            PlannedRemoval
        ] = []

        for change in update_plan.changes:
            if change.action not in {
                "remove",
                "relocate",
            }:
                continue

            current_resource = (
                current_resources.get(
                    change.resource_id
                )
            )

            if (
                current_resource is None
                or change.current_path is None
            ):
                contract_errors.append(
                    "missing_removal_source:"
                    f"{change.resource_id}"
                )
                continue

            expected_resource_removals.append(
                PlannedRemoval(
                    path=output_path.joinpath(
                        *PurePosixPath(
                            change.current_path
                        ).parts
                    ),
                    relative_path=(
                        change.current_path
                    ),
                    kind=current_resource.kind,
                    module=current_resource.owner,
                    reason="replace",
                )
            )

        expected_planned_removals = (
            plan_empty_container_removals(
                initial_output_state=(
                    candidate_plan
                    .initial_output_state
                ),
                removals=(
                    expected_resource_removals
                ),
                desired_state=(
                    update_plan.desired_state
                ),
            )
        )

        expected_removals = [
            (
                removal.relative_path,
                removal.kind,
                removal.module,
                removal.reason,
            )
            for removal
            in expected_planned_removals
        ]
        actual_removals = [
            (
                removal.relative_path,
                removal.kind,
                removal.module,
                removal.reason,
            )
            for removal
            in execution_plan.removals
        ]

        expected_removals.sort(
            key=lambda removal: removal[0]
        )
        actual_removals.sort(
            key=lambda removal: removal[0]
        )

        if expected_removals != actual_removals:
            contract_errors.append(
                "removal_operations_mismatch"
            )

        output_path = execution_plan.output_path

        for planned_file in execution_plan.files:
            resource = desired_resources.get(
                planned_file.resource_id
            )

            if resource is None:
                contract_errors.append(
                    "unknown_file_resource:"
                    f"{planned_file.resource_id}"
                )
                continue

            expected_destination = output_path.joinpath(
                *PurePosixPath(
                    planned_file.relative_destination_path
                ).parts
            )

            if (
                planned_file.destination_path
                != expected_destination
            ):
                contract_errors.append(
                    "file_destination_mismatch:"
                    f"{planned_file.resource_id}"
                )

            if (
                resource.kind != "file"
                or resource.default_path
                != planned_file.default_relative_path
                or resource.materialized_path
                != planned_file.relative_destination_path
                or resource.owner
                != planned_file.owner
                or resource.contributors
                != tuple(planned_file.contributors)
                or resource.content_size
                != planned_file.content_size
                or resource.content_sha256
                != planned_file.content_sha256
                or resource.mode
                != planned_file.mode
            ):
                contract_errors.append(
                    "file_metadata_mismatch:"
                    f"{planned_file.resource_id}"
                )

        expected_removal_paths = {
            removal.relative_path
            for removal in execution_plan.removals
        }

        if len(expected_removal_paths) != len(
            execution_plan.removals
        ):
            contract_errors.append(
                "duplicate_removal_paths"
            )

        for removal in execution_plan.removals:
            expected_path = output_path.joinpath(
                *PurePosixPath(
                    removal.relative_path
                ).parts
            )

            if removal.path != expected_path:
                contract_errors.append(
                    "removal_path_mismatch:"
                    f"{removal.relative_path}"
                )

        allowed_directory_paths: set[Path] = set()

        for planned_file in execution_plan.files:
            parent = planned_file.destination_path.parent

            while True:
                allowed_directory_paths.add(parent)

                if parent == output_path:
                    break

                if output_path not in parent.parents:
                    contract_errors.append(
                        "file_outside_output:"
                        f"{planned_file.resource_id}"
                    )
                    break

                parent = parent.parent

        directory_paths = [
            directory.path
            for directory in execution_plan.directories
        ]

        if len(directory_paths) != len(
            set(directory_paths)
        ):
            contract_errors.append(
                "duplicate_directory_paths"
            )

        for directory in execution_plan.directories:
            if directory.path not in (
                allowed_directory_paths
            ):
                contract_errors.append(
                    "unrelated_directory:"
                    f"{directory.relative_path}"
                )

            expected_relative_path = (
                "."
                if directory.path == output_path
                else directory.path.relative_to(
                    output_path
                ).as_posix()
                if output_path in directory.path.parents
                else None
            )

            if (
                expected_relative_path is None
                or directory.relative_path
                != expected_relative_path
            ):
                contract_errors.append(
                    "directory_path_mismatch:"
                    f"{directory.relative_path}"
                )

            expected_reason = (
                "output"
                if directory.path == output_path
                else "parent"
            )

            if directory.reason != expected_reason:
                contract_errors.append(
                    "directory_reason_mismatch:"
                    f"{directory.relative_path}"
                )

        if contract_errors:
            raise StaleGenerationPlanError(
                (
                    "Cannot execute the project update because "
                    "its materialized contract is invalid."
                ),
                field_path=(
                    "generation.update.execution_plan"
                ),
                context={
                    "reason": (
                        "invalid_update_execution_plan"
                    ),
                    "output_path": str(output_path),
                    "errors": sorted(
                        set(contract_errors)
                    ),
                },
                suggestion=(
                    "Discard the altered plan and create a new "
                    "project update plan."
                ),
            )

        return execution_plan

    @staticmethod
    def _validate_update_state_baseline(
        *,
        update_plan: ProjectUpdatePlan,
        storage: ProjectStateStorage,
    ) -> None:
        """Require the committed state used during planning."""
        pending_path = storage.pending_state_path

        if (
            pending_path.exists()
            or pending_path.is_symlink()
        ):
            raise StateTransactionError(
                (
                    "A pending project state transaction "
                    "already exists."
                ),
                field_path="generation.update.state",
                context={
                    "reason": "pending_state_exists",
                    "state_path": str(
                        storage.state_path
                    ),
                    "pending_state_path": str(
                        pending_path
                    ),
                },
                suggestion=(
                    "Inspect and recover the pending "
                    "transaction before updating the project."
                ),
            )

        actual_state = storage.read()

        if actual_state is None:
            raise StaleGenerationPlanError(
                (
                    "Cannot execute the project update because "
                    "the committed project state is missing."
                ),
                field_path="generation.update.state",
                context={
                    "reason": "project_state_missing",
                    "state_path": str(
                        storage.state_path
                    ),
                },
                suggestion=(
                    "Restore the project state or generate the "
                    "project again before updating it."
                ),
            )

        if actual_state == update_plan.current_state:
            return

        raise StaleGenerationPlanError(
            (
                "Cannot execute the project update because "
                "the committed project state changed after "
                "planning."
            ),
            field_path="generation.update.state",
            context={
                "reason": "project_state_changed",
                "state_path": str(
                    storage.state_path
                ),
                "expected_generator_version": (
                    update_plan.current_state.generator_version
                ),
                "actual_generator_version": (
                    actual_state.generator_version
                ),
                "expected_manifest_sha256": (
                    update_plan.current_state.project
                    .manifest_sha256
                ),
                "actual_manifest_sha256": (
                    actual_state.project.manifest_sha256
                ),
            },
            suggestion=(
                "Create a new update plan from the current "
                "committed project state."
            ),
        )

    @staticmethod
    def _begin_state_transaction(
        *,
        storage: ProjectStateStorage,
        state: ProjectState,
    ) -> None:
        """Write the pending state before filesystem mutations."""
        try:
            storage.begin(state)
        except FileExistsError as error:
            pending_exists = (
                storage.pending_state_path.exists()
                or storage.pending_state_path.is_symlink()
            )

            if pending_exists:
                raise StateTransactionError(
                    (
                        "A pending project state transaction "
                        "already exists."
                    ),
                    field_path="generation.state",
                    context={
                        "reason": "pending_state_exists",
                        "state_path": str(
                            storage.state_path
                        ),
                        "pending_state_path": str(
                            storage.pending_state_path
                        ),
                    },
                    suggestion=(
                        "Inspect and recover the pending "
                        "transaction before generating again."
                    ),
                ) from error

            raise StateTransactionError(
                "Could not write the pending project state.",
                field_path="generation.state",
                context={
                    "reason": "pending_state_write_failed",
                    "state_path": str(
                        storage.state_path
                    ),
                    "pending_state_path": str(
                        storage.pending_state_path
                    ),
                    "error_type": type(error).__name__,
                    "errno": error.errno,
                },
                suggestion=(
                    "Check the output directory permissions "
                    "and filesystem state."
                ),
            ) from error
        except OSError as error:
            raise StateTransactionError(
                "Could not write the pending project state.",
                field_path="generation.state",
                context={
                    "reason": "pending_state_write_failed",
                    "state_path": str(
                        storage.state_path
                    ),
                    "pending_state_path": str(
                        storage.pending_state_path
                    ),
                    "error_type": type(error).__name__,
                    "errno": error.errno,
                },
                suggestion=(
                    "Check the output directory permissions "
                    "and filesystem state."
                ),
            ) from error

    @staticmethod
    def _commit_state_transaction(
        *,
        storage: ProjectStateStorage,
        state: ProjectState,
    ) -> None:
        """Atomically promote the pending state."""
        try:
            storage.commit(state)
        except FileNotFoundError as error:
            raise StateTransactionError(
                "The pending project state is missing.",
                field_path="generation.state",
                context={
                    "reason": "pending_state_missing",
                    "state_path": str(
                        storage.state_path
                    ),
                    "pending_state_path": str(
                        storage.pending_state_path
                    ),
                    "error_type": type(error).__name__,
                    "errno": error.errno,
                },
                suggestion=(
                    "Regenerate the project from a clean "
                    "transaction."
                ),
            ) from error
        except ValueError as error:
            raise StateTransactionError(
                (
                    "The pending project state does not match "
                    "the generation plan."
                ),
                field_path="generation.state",
                context={
                    "reason": "pending_state_mismatch",
                    "state_path": str(
                        storage.state_path
                    ),
                    "pending_state_path": str(
                        storage.pending_state_path
                    ),
                    "error_type": type(error).__name__,
                },
                suggestion=(
                    "Inspect the pending state before retrying "
                    "the generation."
                ),
            ) from error
        except OSError as error:
            raise StateTransactionError(
                "Could not commit the project state.",
                field_path="generation.state",
                context={
                    "reason": "state_commit_failed",
                    "state_path": str(
                        storage.state_path
                    ),
                    "pending_state_path": str(
                        storage.pending_state_path
                    ),
                    "error_type": type(error).__name__,
                    "errno": error.errno,
                },
                suggestion=(
                    "Keep the pending state and resolve the "
                    "filesystem error before retrying."
                ),
            ) from error

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

    def _create_planned_directory(
        self,
        directory: PlannedDirectory,
    ) -> None:
        """Create exactly one directory from the plan."""
        field_path = (
            "generation.directories."
            f"{directory.relative_path}"
        )

        try:
            directory.path.mkdir()
        except OSError as error:
            self._raise_output_error(
                path=directory.path,
                module_key=directory.module,
                field_path=field_path,
                operation="create_directory",
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
        removal: PlannedRemoval,
    ) -> None:
        """Remove exactly one path using its planned kind."""
        field_path = (
            "generation.removals."
            f"{removal.relative_path}"
        )

        try:
            if removal.kind == "directory":
                removal.path.rmdir()
            else:
                removal.path.unlink()
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

    def _contributors_for_inputs(
        self,
        project: ResolvedProject,
        *,
        owner: str,
        inputs: ResourceInputs,
    ) -> list[str]:
        """Resolve modules that influence one generated resource."""
        contributors = {owner}
        used_bindings = set(inputs.bindings)

        contributors.update(
            binding.provider_module_key
            for binding in project.bindings_for_consumer(owner)
            if binding.binding_key in used_bindings
        )

        for extension_point in inputs.extension_points:
            value = project.extension_value_for(
                owner,
                extension_point,
            )

            if value is not None:
                contributors.update(
                    value.contributor_module_keys
                )

        return sorted(contributors)

    def _core_resource_contributors(
        self,
        project: ResolvedProject,
        *,
        resource: Literal[
            "docker",
            "environment",
        ],
    ) -> list[str]:
        """Resolve contributors to one core aggregate resource."""
        contributors: set[str] = set()

        for module in project.ordered_modules():
            if resource == "docker":
                docker = module.manifest.docker

                if docker is None or not (
                    docker.services
                    or docker.volumes
                ):
                    continue

                inputs = docker.uses
            else:
                exports = module.manifest.exports

                if (
                    exports is None
                    or exports.env is None
                    or not exports.env.root
                ):
                    continue

                inputs = exports.uses

            contributors.update(
                self._contributors_for_inputs(
                    project,
                    owner=module.key,
                    inputs=inputs,
                )
            )

        return sorted(contributors)

    def _plan_generated_file(
        self,
        resource_id: str,
        relative_path: str,
        output_path: Path,
        contributors: list[str],
        content: bytes,
    ) -> PlannedFile:
        destination_path = output_path / relative_path

        return self._build_planned_file(
            source_path=None,
            destination_path=destination_path,
            output_path=output_path,
            resource_id=resource_id,
            default_relative_path=(
                PurePosixPath(relative_path).as_posix()
            ),
            operation="generate",
            module=None,
            contributors=contributors,
            strategy="overwrite",
            content=content,
        )

    def _plan_render_source(
        self,
        resolved_project: ResolvedProject,
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
            resource_id=(
                f"module:{module_key}:render:{source.id}"
            ),
            default_relative_path=(
                PurePosixPath(source.to).as_posix()
            ),
            operation="render",
            module=module_key,
            contributors=(
                self._contributors_for_inputs(
                    resolved_project,
                    owner=module_key,
                    inputs=source.uses,
                )
            ),
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

        source_files: list[
            tuple[Path, Path, str | None]
        ] = []

        if source_path.is_file():
            source_files.append(
                (
                    source_path,
                    destination_root,
                    None,
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
                        relative_source_path.as_posix(),
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

        for (
            file_path,
            destination_path,
            relative_source_path,
        ) in source_files:
            content, mode = self._read_copy_source(
                path=file_path,
                module_key=module_key,
                field_path=field_path,
            )

            resource_id = (
                f"module:{module_key}:copy:{source.id}"
            )
            default_relative_path = PurePosixPath(
                source.to
            )

            if relative_source_path is not None:
                resource_id = (
                    f"{resource_id}:"
                    f"{relative_source_path}"
                )
                default_relative_path /= PurePosixPath(
                    relative_source_path
                )

            planned_files.append(
                self._build_planned_file(
                    source_path=file_path,
                    destination_path=destination_path,
                    output_path=output_path,
                    resource_id=resource_id,
                    default_relative_path=(
                        default_relative_path.as_posix()
                    ),
                    operation="copy",
                    module=module_key,
                    contributors=[module_key],
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

        try:
            lexical_relative_path = path.relative_to(
                allowed_root
            )
        except ValueError:
            lexical_relative_path = None

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

        if (
            path_kind in {"destination", "removal"}
            and (
                (
                    lexical_relative_path is not None
                    and is_reserved_state_path(
                        lexical_relative_path
                    )
                )
                or is_reserved_state_path(
                    relative_path
                )
            )
        ):
            raise UnsafePathError(
                (
                    "Reserved Boilr state path cannot be "
                    f"used as a {path_kind}: '{path}'."
                ),
                module_key=module_key,
                field_path=field_path,
                context={
                    "reason": "reserved_state_path",
                    "path_kind": path_kind,
                    f"{path_kind}_path": str(path),
                    "resolved_path": str(
                        resolved_path
                    ),
                    "allowed_root": str(
                        resolved_root
                    ),
                    "relative_path": (
                        relative_path.as_posix()
                    ),
                    "reserved_root": (
                        STATE_DIRECTORY_NAME
                    ),
                },
                suggestion=(
                    "Choose a path outside the reserved "
                    f"'{STATE_DIRECTORY_NAME}' directory."
                ),
            )

        return relative_path.as_posix()

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
        resource_id: str,
        default_relative_path: str,
        operation: str,
        module: str | None,
        contributors: list[str],
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
            resource_id=resource_id,
            default_relative_path=default_relative_path,
            operation=operation,
            action=action,
            module=module,
            contributors=contributors,
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
