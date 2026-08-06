"""Command-line interface for the Boilr generator."""

import json
from collections import defaultdict
from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console
from rich.markup import escape
from rich.panel import Panel
from rich.table import Table
from rich.tree import Tree

from boilr_generator.exceptions import BoilrError
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
    """Build a generator using the packaged module registry."""
    registry = ModuleRegistry(get_builtin_modules_path())
    return ProjectGenerator(registry)


def section_width(max_width: int = 100) -> int:
    """Calculate a readable width for CLI sections."""
    available_width = console.size.width - 4
    return min(max_width, max(60, available_width))


def render_section(
    renderable,
    title: str,
    border_style: str = "bright_black",
) -> None:
    """Render one bordered CLI section."""
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


def shorten_path(
    path: str | Path,
    max_length: int = 75,
) -> str:
    """Shorten long paths while preserving their final component."""
    value = str(path)

    if len(value) <= max_length:
        return value

    return "..." + value[-max_length:]


def render_boilr_error(error: BoilrError) -> None:
    """Render one expected Boilr error without a traceback."""
    table = Table.grid(padding=(0, 2))
    table.add_column(style="bold red")
    table.add_column()

    table.add_row(
        "Message",
        escape(error.message),
    )
    table.add_row(
        "Code",
        escape(error.code),
    )

    if error.module_key is not None:
        table.add_row(
            "Module",
            escape(error.module_key),
        )

    if error.field_path is not None:
        table.add_row(
            "Field",
            escape(error.field_path),
        )

    if error.context:
        context = json.dumps(
            error.context,
            indent=2,
            ensure_ascii=False,
            default=str,
        )

        table.add_row(
            "Context",
            escape(context),
        )

    if error.suggestion is not None:
        table.add_row(
            "Suggestion",
            escape(error.suggestion),
        )

    render_section(
        table,
        f"Boilr error ({escape(error.code)})",
        border_style="red",
    )


def render_plan_overview(
    plan_dict: dict,
    title: str,
) -> None:
    """Render the main project information from a generation plan."""
    project = plan_dict["resolved_project"]

    table = Table.grid(padding=(0, 2))
    table.add_column(style="bold")
    table.add_column()

    table.add_row("Project", escape(project["name"]))
    table.add_row("Type", escape(project["type"]))
    table.add_row("Version", escape(project["version"]))
    table.add_row(
        "Modules",
        escape(", ".join(project["modules"])),
    )
    table.add_row(
        "Output",
        escape(shorten_path(plan_dict["output_path"])),
    )

    render_section(
        table,
        title,
        border_style="green",
    )


def render_summary(summary: dict) -> None:
    """Render generation plan counters."""
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
        (
            "[yellow]"
            f"{summary.get('files_to_overwrite', 0)}"
            "[/yellow]"
        ),
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
    """Warn when a generation will overwrite existing files."""
    files_to_overwrite = summary.get(
        "files_to_overwrite",
        0,
    )

    if files_to_overwrite <= 0:
        return

    console.print(
        f"[yellow]Warning:[/yellow] "
        f"[cyan]{files_to_overwrite}[/cyan] "
        "file(s) will be overwritten."
    )


def render_files_tree(
    files: list[dict],
    limit_per_action: int = 8,
) -> None:
    """Render planned files grouped by module and action."""
    grouped_files: dict[
        str,
        dict[str, list[dict]],
    ] = defaultdict(lambda: defaultdict(list))

    for file in files:
        module = file["module"] or "project"
        action = file["action"]
        grouped_files[module][action].append(file)

    tree = Tree(
        "[bold]Files[/bold]",
        guide_style="bright_black",
    )

    action_styles = {
        "create": "green",
        "overwrite": "yellow",
        "skip": "dim",
    }

    action_order = [
        "create",
        "overwrite",
        "skip",
    ]

    for module_name, actions in grouped_files.items():
        module_node = tree.add(
            f"[bold]{escape(module_name)}[/bold]"
        )

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
                destination = file[
                    "relative_destination_path"
                ]
                action_node.add(escape(destination))

            remaining_files = (
                len(action_files) - len(visible_files)
            )

            if remaining_files > 0:
                action_node.add(
                    f"[dim]... {remaining_files} more "
                    "file(s). Use --json to inspect "
                    "the full plan.[/dim]"
                )

    render_section(
        tree,
        "Planned files",
        border_style="bright_black",
    )


@app.command()
def dry_run(
    manifest_path: Annotated[
        Path,
        typer.Argument(
            help="Path to the project manifest file.",
        ),
    ],
    output_path: Annotated[
        Path,
        typer.Argument(
            help=(
                "Directory where the project would be generated."
            ),
        ),
    ],
    info: Annotated[
        bool,
        typer.Option(
            "--info",
            help="Show detailed generation plan.",
        ),
    ] = False,
    json_output: Annotated[
        bool,
        typer.Option(
            "--json",
            help="Print the complete generation plan as JSON.",
        ),
    ] = False,
    debug: Annotated[
        bool,
        typer.Option(
            "--debug",
            help=(
                "Show the complete traceback when an error occurs."
            ),
        ),
    ] = False,
) -> None:
    """Preview the files and configuration that would be generated."""
    try:
        manifest = load_project_manifest_from_yaml(
            str(manifest_path)
        )
        generator = build_generator()

        plan = generator.plan(
            manifest,
            output_path,
        )
        plan_dict = plan.to_dict()

        if json_output:
            console.print_json(data=plan_dict)
            return

        render_plan_overview(
            plan_dict,
            "Boilr dry run",
        )
        render_summary(plan.summary)
        render_overwrite_warning(plan.summary)

        console.print()

        if info:
            render_files_tree(plan_dict["files"])
        else:
            console.print(
                "[dim]Run with --info to show planned files.[/dim]"
            )
    except BoilrError as error:
        if debug:
            raise

        render_boilr_error(error)
        raise typer.Exit(code=1) from None


@app.command()
def generate(
    manifest_path: Annotated[
        Path,
        typer.Argument(
            help="Path to the project manifest file.",
        ),
    ],
    output_path: Annotated[
        Path,
        typer.Argument(
            help=(
                "Directory where the project will be generated."
            ),
        ),
    ],
    info: Annotated[
        bool,
        typer.Option(
            "--info",
            help=(
                "Show the generation plan before writing files."
            ),
        ),
    ] = False,
    clean: Annotated[
        bool,
        typer.Option(
            "--clean",
            help=(
                "Clean the output directory before generating "
                "the project."
            ),
        ),
    ] = False,
    debug: Annotated[
        bool,
        typer.Option(
            "--debug",
            help=(
                "Show the complete traceback when an error occurs."
            ),
        ),
    ] = False,
) -> None:
    """Generate a project from a Boilr manifest."""
    try:
        manifest = load_project_manifest_from_yaml(
            str(manifest_path)
        )
        generator = build_generator()

        plan = generator.plan(
            manifest,
            output_path,
        )
        plan_dict = plan.to_dict()

        if info:
            render_plan_overview(
                plan_dict,
                "Boilr generate",
            )
            render_summary(plan.summary)
            render_overwrite_warning(plan.summary)

            console.print()
            render_files_tree(plan_dict["files"])

        generator.execute(
            plan,
            clean=clean,
        )

        console.print()
        console.print(
            "[green]Project generated successfully in:[/green] "
            f"{escape(str(output_path))}"
        )
    except BoilrError as error:
        if debug:
            raise

        render_boilr_error(error)
        raise typer.Exit(code=1) from None


if __name__ == "__main__":
    app()