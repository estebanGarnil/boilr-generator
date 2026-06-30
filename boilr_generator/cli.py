from pathlib import Path

import typer
from rich import box
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.tree import Tree

from boilr_generator.generation import ProjectGenerator
from boilr_generator.manifest import load_project_manifest_from_yaml
from boilr_generator.modules.registry import ModuleRegistry


app = typer.Typer(
    no_args_is_help=True,
    rich_markup_mode="rich",
    help="Boilr project generator CLI.",
)

console = Console()

TEMPLATES_DIR = Path("templates")



def build_generator() -> ProjectGenerator:
    registry = ModuleRegistry(str(TEMPLATES_DIR))
    return ProjectGenerator(registry)


def render_summary(summary: dict) -> None:
    table = Table(
        title="Generation summary",
        box=box.ROUNDED,
        show_header=True,
        header_style="bold",
    )

    table.add_column("Item")
    table.add_column("Value", justify="right")

    labels = {
        "modules_count": "Modules",
        "files_count": "Total files",
        "files_to_create": "Files to create",
        "files_to_overwrite": "Files to overwrite",
        "files_to_skip": "Files to skip",
        "docker_services_count": "Docker services",
        "env_variables_count": "Environment variables",
    }

    for key, label in labels.items():
        table.add_row(label, str(summary.get(key, 0)))

    console.print(table)


def render_project_info(plan: dict) -> None:
    project = plan["resolved_project"]

    table = Table(box=box.SIMPLE, show_header=False)
    table.add_column("Field", style="bold")
    table.add_column("Value")

    table.add_row("Name", project["name"])
    table.add_row("Type", project["type"])
    table.add_row("Version", project["version"])
    table.add_row("Modules", ", ".join(project["modules"]))
    table.add_row("Output directory", plan["output_path"])

    console.print(
        Panel(
            table,
            title="[bold]Resolved project[/bold]",
            border_style="green",
        )
    )


def render_files(files: list[dict]) -> None:
    table = Table(
        title="Planned files",
        box=box.ROUNDED,
        show_lines=False,
    )

    table.add_column("Action", style="bold")
    table.add_column("Operation")
    table.add_column("Module")
    table.add_column("Destination")

    action_styles = {
        "create": "green",
        "overwrite": "yellow",
        "skip": "dim",
    }

    for file in files:
        action = file["action"]
        style = action_styles.get(action, "white")

        table.add_row(
            f"[{style}]{action}[/{style}]",
            file["operation"],
            file["module"] or "-",
            file["relative_destination_path"],
        )

    console.print(table)


def render_configuration(plan: dict) -> None:
    tree = Tree("[bold]Generated configuration[/bold]")

    docker_node = tree.add("[cyan]Docker services[/cyan]")
    for service in plan["docker_services"]:
        docker_node.add(service)

    env_node = tree.add("[magenta]Environment variables[/magenta]")
    for variable in plan["env_variables"]:
        env_node.add(variable)

    console.print(tree)


def render_overwrite_warning(summary: dict) -> None:
    files_to_overwrite = summary.get("files_to_overwrite", 0)

    if files_to_overwrite > 0:
        console.print(
            f"[yellow]Warning:[/yellow] "
            f"{files_to_overwrite} file(s) will be overwritten."
        )


@app.command()
def dry_run(
    manifest_path: Path = typer.Argument(
        ...,
        help="Path to the project manifest file.",
    ),
    output_path: Path = typer.Argument(
        ...,
        help="Directory where the project would be generated.",
    ),
    info: bool = typer.Option(
        False,
        "--info",
        help="Show detailed generation plan.",
    ),
    json_output: bool = typer.Option(
        False,
        "--json",
        help="Print the complete generation plan as JSON.",
    ),
) -> None:
    """
    Preview the files and configuration that would be generated.
    """
    manifest = load_project_manifest_from_yaml(str(manifest_path))
    generator = build_generator()

    plan = generator.plan(manifest, output_path)
    plan_dict = plan.to_dict()

    if json_output:
        console.print_json(data=plan_dict)
        return

    render_project_info(plan_dict)
    render_summary(plan.summary)
    render_overwrite_warning(plan.summary)

    if info:
        render_configuration(plan_dict)
        render_files(plan_dict["files"])


@app.command()
def generate(
    manifest_path: Path = typer.Argument(
        ...,
        help="Path to the project manifest file.",
    ),
    output_path: Path = typer.Argument(
        ...,
        help="Directory where the project will be generated.",
    ),
    info: bool = typer.Option(
        False,
        "--info",
        help="Show the generation plan before writing files.",
    ),
    clean: bool = typer.Option(
        False,
        "--clean",
        help="Clean the output directory before generating the project.",
    ),
) -> None:
    """
    Generate a project from a Boilr manifest.
    """
    manifest = load_project_manifest_from_yaml(str(manifest_path))
    generator = build_generator()

    plan = generator.plan(manifest, output_path)
    plan_dict = plan.to_dict()

    if info:
        render_project_info(plan_dict)
        render_summary(plan.summary)
        render_overwrite_warning(plan.summary)

    generator.execute(plan, clean=clean)

    console.print(
        f"[green]Project generated successfully in:[/green] {output_path}"
    )


if __name__ == "__main__":
    app()