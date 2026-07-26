from collections import defaultdict
from pathlib import Path

import typer
from rich.console import Console
from rich.markup import escape
from rich.panel import Panel
from rich.table import Table
from rich.tree import Tree

from boilr_generator.generation import ProjectGenerator
from boilr_generator.manifest import load_project_manifest_from_yaml
from boilr_generator.modules.registry import ModuleRegistry
from boilr_generator.paths import get_builtin_modules_path


app = typer.Typer(
    no_args_is_help=True,
    rich_markup_mode="rich",
    help="Boilr project generator CLI.",
)

console = Console()

def build_generator() -> ProjectGenerator:
    registry = ModuleRegistry(get_builtin_modules_path())
    return ProjectGenerator(registry)


def section_width(max_width: int = 100) -> int:
    available_width = console.size.width - 4
    return min(max_width, max(60, available_width))


def render_section(renderable, title: str, border_style: str = "bright_black") -> None:
    console.print(
        Panel(
            renderable,
            title=f"[bold]{title}[/bold]",
            border_style=border_style,
            expand=False,
            width=section_width(),
            padding=(1, 2),
        )
    )


def shorten_path(path: str | Path, max_length: int = 75) -> str:
    value = str(path)

    if len(value) <= max_length:
        return value

    return "..." + value[-max_length:]


def render_plan_overview(plan_dict: dict, title: str) -> None:
    project = plan_dict["resolved_project"]

    table = Table.grid(padding=(0, 2))
    table.add_column(style="bold")
    table.add_column()

    table.add_row("Project", escape(project["name"]))
    table.add_row("Type", escape(project["type"]))
    table.add_row("Version", escape(project["version"]))
    table.add_row("Modules", escape(", ".join(project["modules"])))
    table.add_row("Output", escape(shorten_path(plan_dict["output_path"])))

    render_section(table, title, border_style="green")


def render_summary(summary: dict) -> None:
    table = Table.grid(padding=(0, 4))
    table.add_column(style="bold")
    table.add_column(justify="right")
    table.add_column(style="bold")
    table.add_column(justify="right")

    table.add_row(
        "Files",
        str(summary.get("files_count", 0)),
        "Create",
        f"[green]{summary.get('files_to_create', 0)}[/green]",
    )

    table.add_row(
        "Overwrite",
        f"[yellow]{summary.get('files_to_overwrite', 0)}[/yellow]",
        "Skip",
        f"[dim]{summary.get('files_to_skip', 0)}[/dim]",
    )

    table.add_row(
        "Docker",
        str(summary.get("docker_services_count", 0)),
        "Env",
        str(summary.get("env_variables_count", 0)),
    )

    render_section(table, "Summary")


def render_overwrite_warning(summary: dict) -> None:
    files_to_overwrite = summary.get("files_to_overwrite", 0)

    if files_to_overwrite <= 0:
        return

    console.print(
        f"[yellow]Warning:[/yellow] "
        f"[cyan]{files_to_overwrite}[/cyan] file(s) will be overwritten."
    )


def render_files_tree(files: list[dict], limit_per_action: int = 8) -> None:
    grouped_files: dict[str, dict[str, list[dict]]] = defaultdict(
        lambda: defaultdict(list)
    )

    for file in files:
        module = file["module"] or "project"
        action = file["action"]
        grouped_files[module][action].append(file)

    tree = Tree("[bold]Files[/bold]", guide_style="bright_black")

    action_styles = {
        "create": "green",
        "overwrite": "yellow",
        "skip": "dim",
    }

    action_order = ["create", "overwrite", "skip"]

    for module_name, actions in grouped_files.items():
        module_node = tree.add(f"[bold]{escape(module_name)}[/bold]")

        for action in action_order:
            action_files = actions.get(action, [])

            if not action_files:
                continue

            style = action_styles.get(action, "white")
            action_node = module_node.add(
                f"[{style}]{action}[/] "
                f"[dim]({len(action_files)} file(s))[/dim]"
            )

            visible_files = action_files[:limit_per_action]

            for file in visible_files:
                destination = file["relative_destination_path"]
                action_node.add(escape(destination))

            remaining_files = len(action_files) - len(visible_files)

            if remaining_files > 0:
                action_node.add(
                    f"[dim]... {remaining_files} more file(s). "
                    f"Use --json to inspect the full plan.[/dim]"
                )

    render_section(tree, "Planned files", border_style="bright_black")


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

    render_plan_overview(plan_dict, "Boilr dry run")
    render_summary(plan.summary)
    render_overwrite_warning(plan.summary)

    console.print()

    if info:
        render_files_tree(plan_dict["files"])
    else:
        console.print("[dim]Run with --info to show planned files.[/dim]")


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
        render_plan_overview(plan_dict, "Boilr generate")
        render_summary(plan.summary)
        render_overwrite_warning(plan.summary)

        console.print()
        render_files_tree(plan_dict["files"])

    generator.execute(plan, clean=clean)

    console.print()
    console.print(
        f"[green]Project generated successfully in:[/green] "
        f"{escape(str(output_path))}"
    )


if __name__ == "__main__":
    app()