from pathlib import Path
import shutil
from typing import Any

import yaml

from boilr_generator.core.project import ResolvedProject
from boilr_generator.generation.docker import DockerComposeGenerator
from boilr_generator.generation.env import EnvGenerator
from boilr_generator.generation.files import FileGenerator
from boilr_generator.manifest.schemas import ProjectManifest
from boilr_generator.modules.registry import ModuleRegistry
from boilr_generator.resolver import Resolver
from boilr_generator.core.generation_plan import GenerationPlan, PlannedFile
from boilr_generator.modules.schemas import CopySource, RenderSource


class ProjectGenerator:
    def __init__(self, registry: ModuleRegistry) -> None:
        self.registry = registry
        self.resolver = Resolver(registry)
        self.file_generator = FileGenerator()
        self.docker_generator = DockerComposeGenerator()
        self.env_generator = EnvGenerator()

    def generate(
        self,
        manifest: ProjectManifest,
        output_path: str | Path,
        clean: bool = False,
    ) -> ResolvedProject:
        plan = self.plan(manifest, output_path)
        self.execute(plan, clean=clean)

        return plan.resolved_project

    def plan(
        self, 
        manifest: ProjectManifest, 
        output_path: str | Path,
    ) -> GenerationPlan:
        output_path = Path(output_path)
        resolved_project = self.resolver.resolve(manifest)

        files: list[PlannedFile] = []

        for module in resolved_project.ordered_modules():
            module_path = self.registry.get_path(module.manifest.meta.key)

            for source in module.manifest.sources.copy_sources:
                files.extend(
                    self._plan_copy_source(
                        module_key=module.manifest.meta.key, 
                        module_path=module_path, 
                        source=source,
                        output_path=output_path,
                    )
                )
            
            
            for source in module.manifest.sources.render: 
                files.append(
                    self._plan_render_source(
                        module_key=module.manifest.meta.key,
                        module_path=module_path,
                        source=source,
                        output_path=output_path,
                    )
                )
        
        files.append(
            self._plan_generated_file(
                relative_path="docker-compose.yml",
                output_path=output_path,
            )
        )
        files.append(
            self._plan_generated_file(
                relative_path=".env",
                output_path=output_path,
            )
        )

        docker_compose = self.docker_generator.generate(resolved_project)
        env = self.env_generator.generate(resolved_project)

        return GenerationPlan(
            resolved_project=resolved_project,
            output_path=output_path, 
            files=files, 
            docker_services=list(docker_compose.get("services", {}).keys()),
            env_variables=list(env.keys())
        )

    def execute(
        self, 
        plan: GenerationPlan, 
        clean: bool = False,
    ) -> None:
        output_path = plan.output_path

        if clean and output_path.exists():
            shutil.rmtree(output_path)
        
        output_path.mkdir(parents=True, exist_ok=True)

        resolved_project = plan.resolved_project

        self.file_generator.copy_sources(resolved_project, output_path)
        self.file_generator.render_sources(resolved_project, output_path)

        self._write_docker_compose(resolved_project, output_path)
        self._write_env_file(resolved_project, output_path)

    def _write_docker_compose(
        self,
        project: ResolvedProject,
        output_path: Path,
    ) -> None:
        compose = self.docker_generator.generate(project)

        self._write_yaml(
            path=output_path / "docker-compose.yml",
            data=compose,
        )

    def _write_env_file(
        self,
        project: ResolvedProject,
        output_path: Path,
    ) -> None:
        env = self.env_generator.generate(project)

        lines = [
            f"{key}={value}"
            for key, value in env.items()
        ]

        content = "\n".join(lines)

        if content:
            content += "\n"

        (output_path / ".env").write_text(content, encoding="utf-8")

    def _write_yaml(
        self,
        path: Path,
        data: dict[str, Any],
    ) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)

        with path.open("w", encoding="utf-8") as file:
            yaml.safe_dump(
                data,
                file,
                sort_keys=False,
                allow_unicode=True,
            )

    def _plan_generated_file(
        self, 
        relative_path: str, 
        output_path: Path,
    ) -> PlannedFile: 
        destination_path = output_path / relative_path

        return self._build_planned_file(
            source_path=None, 
            destination_path=destination_path,
            output_path=output_path,
            operation="generate", 
            module=None, 
            strategy="overwrite",
        )
        
    def _plan_render_source(
        self, 
        module_key: str,
        module_path: Path, 
        source: RenderSource, 
        output_path: Path,
    ) -> PlannedFile: 
        source_path = module_path / source.from_
        destination_path = output_path / source.to

        return self._build_planned_file(
            source_path=source_path,
            destination_path=destination_path,
            output_path=output_path,
            operation="render",
            module=module_key,
            strategy="overwrite",
        )

    def _plan_copy_source(
            self, 
            module_key: str, 
            module_path: Path, 
            source: CopySource, 
            output_path: Path, 
    ) -> list[PlannedFile]:
        source_path = module_path / source.from_ 
        destination_root = output_path / source.to

        if source_path.is_file():
            return [
                self._build_planned_file(
                    source_path=source_path, 
                    destination_path=destination_root, 
                    output_path=output_path,
                    operation="copy",
                    module=module_key,
                    strategy=source.strategy,
                )
            ]
        
        planned_files: list[PlannedFile] = []

        for file_path in source_path.rglob("*"):
            if not file_path.is_file():
                continue
        
            relative_source_path = file_path.relative_to(source_path)
            destination_path = destination_root / relative_source_path

            planned_files.append(
                self._build_planned_file(
                    source_path=file_path, 
                    destination_path=destination_path,
                    output_path=output_path,
                    operation="copy",
                    module=module_key, 
                    strategy=source.strategy,
                )
            )

        return planned_files

    def _build_planned_file(
            self, 
            source_path: Path | None, 
            destination_path: Path, 
            output_path: Path, 
            operation: str, 
            module: str | None, 
            strategy: str,
    ) -> PlannedFile: 
        action = self._get_planned_action(
            destination_path=destination_path,
            strategy=strategy,
        )

        return PlannedFile(
            source_path=source_path, 
            destination_path=destination_path, 
            relative_destination_path=str(destination_path.relative_to(output_path)),
            operation=operation, 
            action=action, 
            module=module,
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