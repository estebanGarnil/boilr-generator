from pathlib import Path 
import shutil
from jinja2 import Template

from boilr_generator.core.project import ResolvedProject


class FileGenerator: 
    def copy_sources(self, project: ResolvedProject, output_path: str | Path) -> None: 
        output_path = Path(output_path)

        for module in project.ordered_modules():
            for source in module.manifest.sources.copy_sources:
                source_path = module.resolve_source_path(source.from_)
                destination_path = output_path / source.to 

                self._copy_source(
                    source_path=source_path,
                    destination_path=destination_path, 
                    strategy=source.strategy
                )
    
    def _copy_source(
            self, 
            source_path: Path, 
            destination_path: Path, 
            strategy: str,
    ) -> None: 
        if not source_path.exists():
            raise FileNotFoundError(f"Source path not found: {source_path}")
        
        if destination_path.exists():
            if strategy == "skip":
                return 
            
            if strategy == "replace":
                if destination_path.is_dir():
                    shutil.rmtree(destination_path)
                else:
                    destination_path.unlink()
            
            if strategy == "merge":
                pass

        if source_path.is_dir():
            shutil.copytree(
                source_path, 
                destination_path, 
                dirs_exist_ok=(strategy == "merge"),
            )
        else: 
            destination_path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source_path, destination_path)
    
    def render_sources(self, project: ResolvedProject, output_path: str | Path) -> None:
        output_path = Path(output_path)

        for module in project.ordered_modules():
            for source in module.manifest.sources.render: 
                template_path = module.resolve_source_path(source.from_)
                destination_path = output_path / source.to 

                self._render_template(
                    template_path=template_path,
                    destination_path=destination_path,
                    context={
                        **module.variables,
                        "options": module.options,
                        "dependencies": getattr(module.manifest, "dependencies", {}),
                    },
                )

    def _render_template(
            self, template_path: Path, 
            destination_path: Path, 
            context: dict,
    ) -> None: 
        if not template_path.exists():
            raise FileNotFoundError(f"Template not found: {template_path}")
        
        destination_path.parent.mkdir(parents=True, exist_ok=True)

        template_content = template_path.read_text(encoding="utf-8")
        rendered_content = Template(template_content).render(**context)

        destination_path.write_text(rendered_content, encoding="utf-8")