from typing import Any 

from jinja2 import Template

from boilr_generator.core.project import ResolvedProject


class DockerComposeGenerator: 
    def generate(self, project: ResolvedProject) -> dict:
        compose = {
            "version": "3.9",
            "services": {},
            "volumes": {},
        }

        for module in project.ordered_modules():
            docker = module.manifest.docker

            if not docker: 
                continue

            for service_name, service in docker.services.items():
                compose["services"][service_name] = self._render_value(
                    service.root, 
                    module.variables,
                )
            
            for volume_name, volume_config in docker.volumes.items():
                compose["volumes"][volume_name] = volume_config
        
        if not compose["volumes"]:
            compose.pop("volumes")

            
        return compose
    
    def _render_value(self, value: Any, context: dict[str, Any]) -> Any:
        if isinstance(value, str):
            return Template(value).render(**context)
        
        if isinstance(value, list):
            return [self._render_value(item, context) for item in value]
        
        if isinstance(value, dict): 
            return {
                key: self._render_value(item, context)
                for key, item in value.items()
            }
        
        return value