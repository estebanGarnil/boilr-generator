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
        output_path = Path(output_path)

        if clean and output_path.exists():
            shutil.rmtree(output_path)

        output_path.mkdir(parents=True, exist_ok=True)

        resolved_project = self.resolver.resolve(manifest)

        self.file_generator.copy_sources(resolved_project, output_path)
        self.file_generator.render_sources(resolved_project, output_path)

        self._write_docker_compose(resolved_project, output_path)
        self._write_env_file(resolved_project, output_path)

        return resolved_project

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