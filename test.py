from pprint import pprint

from boilr_generator.generation import ProjectGenerator
from boilr_generator.manifest import load_project_manifest_from_yaml
from boilr_generator.modules.registry import ModuleRegistry

registry = ModuleRegistry("templates")

manifest = load_project_manifest_from_yaml("project.yml")

generator = ProjectGenerator(registry)

plan = generator.plan(
    manifest=manifest,
    output_path="output/my_app",
)

pprint(plan.to_dict())
# print("\n=== SUMMARY ===")
# pprint(plan.summary)

# print("\n=== DOCKER SERVICES ===")
# pprint(plan.docker_services)

# print("\n=== ENV VARIABLES ===")
# pprint(plan.env_variables)

# print("\n=== FILES ===")

# for file in plan.files:
#     print(
#         f"[{file.action.upper():10}] "
#         f"[{file.operation.upper():8}] "
#         f"{file.relative_destination_path}"
#     )