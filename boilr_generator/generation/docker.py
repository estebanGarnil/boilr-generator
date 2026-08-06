"""Docker Compose configuration generation."""

from typing import Any

from jinja2 import Environment, StrictUndefined
from jinja2.exceptions import TemplateError

from boilr_generator.core.project import ResolvedProject
from boilr_generator.exceptions import (
    DockerConflictError,
    TemplateRenderError,
)

JINJA_ENVIRONMENT = Environment(
    autoescape=False,
    undefined=StrictUndefined,
)


class DockerComposeGenerator:
    """Generate a Docker Compose configuration from resolved modules."""

    def generate(
        self,
        project: ResolvedProject,
    ) -> dict[str, Any]:
        """Generate and merge Docker contributions."""
        compose: dict[str, Any] = {
            "version": "3.9",
            "services": {},
            "volumes": {},
        }

        service_origins: dict[str, str] = {}
        volume_origins: dict[str, str] = {}

        for module in project.ordered_modules():
            docker = module.manifest.docker

            if docker is None:
                continue

            for service_name, service in docker.services.items():
                field_path = (
                    f"modules.{module.key}.docker.services.{service_name}"
                )
                rendered_service = self._render_value(
                    service.root,
                    module.variables,
                    module_key=module.key,
                    field_path=field_path,
                )

                existing_service = compose["services"].get(service_name)

                if (
                    existing_service is not None
                    and existing_service != rendered_service
                ):
                    raise DockerConflictError(
                        (
                            f"Docker service '{service_name}' is defined "
                            "with conflicting configurations by modules "
                            f"'{service_origins[service_name]}' and "
                            f"'{module.key}'."
                        ),
                        module_key=module.key,
                        field_path=field_path,
                        context={
                            "service": service_name,
                            "first_module": service_origins[service_name],
                            "conflicting_module": module.key,
                        },
                        suggestion=(
                            f"Rename service '{service_name}' or make both "
                            "module definitions identical."
                        ),
                    )

                if existing_service is None:
                    compose["services"][service_name] = rendered_service
                    service_origins[service_name] = module.key

            for volume_name, volume_config in docker.volumes.items():
                field_path = (
                    f"modules.{module.key}.docker.volumes.{volume_name}"
                )
                rendered_volume = self._render_value(
                    volume_config,
                    module.variables,
                    module_key=module.key,
                    field_path=field_path,
                )

                existing_volume = compose["volumes"].get(volume_name)

                if (
                    existing_volume is not None
                    and existing_volume != rendered_volume
                ):
                    raise DockerConflictError(
                        (
                            f"Docker volume '{volume_name}' is defined "
                            "with conflicting configurations by modules "
                            f"'{volume_origins[volume_name]}' and "
                            f"'{module.key}'."
                        ),
                        module_key=module.key,
                        field_path=field_path,
                        context={
                            "volume": volume_name,
                            "first_module": volume_origins[volume_name],
                            "conflicting_module": module.key,
                        },
                        suggestion=(
                            f"Rename volume '{volume_name}' or make both "
                            "module definitions identical."
                        ),
                    )

                if existing_volume is None:
                    compose["volumes"][volume_name] = rendered_volume
                    volume_origins[volume_name] = module.key

        if not compose["volumes"]:
            compose.pop("volumes")

        return compose

    def _render_value(
        self,
        value: Any,
        context: dict[str, Any],
        *,
        module_key: str,
        field_path: str,
    ) -> Any:
        """Render strings recursively inside a Docker configuration."""
        if isinstance(value, str):
            return self._render_string(
                value,
                context,
                module_key=module_key,
                field_path=field_path,
            )

        if isinstance(value, list):
            return [
                self._render_value(
                    item,
                    context,
                    module_key=module_key,
                    field_path=f"{field_path}[{index}]",
                )
                for index, item in enumerate(value)
            ]

        if isinstance(value, dict):
            return {
                key: self._render_value(
                    item,
                    context,
                    module_key=module_key,
                    field_path=f"{field_path}.{key}",
                )
                for key, item in value.items()
            }

        return value

    def _render_string(
        self,
        value: str,
        context: dict[str, Any],
        *,
        module_key: str,
        field_path: str,
    ) -> str:
        """Render one Docker configuration value using strict Jinja."""
        try:
            template = JINJA_ENVIRONMENT.from_string(value)
            return template.render(**context)
        except TemplateError as error:
            raise TemplateRenderError(
                (
                    f"Unable to render Docker value at "
                    f"'{field_path}': {error}"
                ),
                module_key=module_key,
                field_path=field_path,
                context={
                    "target": "docker",
                    "error_type": type(error).__name__,
                },
                suggestion=(
                    "Check the template syntax and ensure every referenced "
                    "variable is declared by the module."
                ),
            ) from error