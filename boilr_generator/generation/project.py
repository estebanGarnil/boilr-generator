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
            for source in module.manifest.sources.copy_sources:
                files.append(
                    PlannedFile(
                        path=output_path / source.to,
                        action="overwrite" if (output_path / source.to).exists() else "create",
                    )
                )
            
            for source in module.manifest.sources.render: 
                files.append(
                    PlannedFile(
                        path=output_path / source.to,
                        action ="overwrite" if (output_path / source.to).exists() else "create",
                    )
                )
        
        files.append(
            PlannedFile(
                path=output_path / "docker-compose.yml",
                action="overwrite" if (output_path / "docker-compose.yml").exists() else "create"
            )
        )

        files.append(
            PlannedFile(
                path=output_path / ".env", 
                action="overwrite" if (output_path / ".env").exists() else "create"
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