from typing import Any

from jinja2 import Template

from boilr_generator.core.project import ResolvedProject


class EnvGenerator:
    def generate(self, project: ResolvedProject) -> dict[str, str]:
        env: dict[str, str] = {}

        for module in project.ordered_modules():
            exports = module.manifest.exports

            if not exports or not exports.env:
                continue

            for key, value in exports.env.root.items():
                rendered_value = self._render_value(value, module.variables)
                env[key] = rendered_value
        
        return env
    
    def _render_value(self, value: Any, context: dict[str, Any]) -> str:
        if isinstance(value, str):
            return Template(value).render(**context)

        return str(value)