from pathlib import Path
import json

import typer
from rich import box
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.tree import Tree

from boilr_generator.generation import ProjectGenerator
from boilr_generator.manifest import load_project_manifest_from_yaml
from boilr_generator.modules.registry import ModuleRegistry


app = typer.Typer(no_args_is_help=True, rich_markup_mode="rich")
console = Console()


def render_summary(summary: dict) -> None:
    table = Table(box=box.ROUNDED, show_header=True, header_style="bold")
    table.add_column("Élément")
    table.add_column("Valeur", justify="right")

    labels = {
        "modules_count": "Modules",
        "files_count": "Fichiers total",
        "files_to_create": "Fichiers à créer",
        "files_to_overwrite": "Fichiers à écraser",
        "files_to_skip": "Fichiers ignorés",
        "docker_services_count": "Services Docker",
        "env_variables_count": "Variables .env",
    }

    for key, label in labels.items():
        table.add_row(label, str(summary.get(key, 0)))

    console.print(table)


def render_project_info(info: dict) -> None:
    project = info["resolved_project"]

    table = Table(box=box.SIMPLE, show_header=False)
    table.add_column("Champ", style="bold")
    table.add_column("Valeur")

    table.add_row("Nom", project["name"])
    table.add_row("Type", project["type"])
    table.add_row("Version", project["version"])
    table.add_row("Modules", ", ".join(project["modules"]))
    table.add_row("Output", info["output_path"])

    console.print(
        Panel(
            table,
            title="[bold]Projet résolu[/bold]",
            border_style="green",
        )
    )


def render_files(files: list[dict]) -> None:
    table = Table(
        title="Fichiers planifiés",
        box=box.ROUNDED,
        show_lines=False,
    )

    table.add_column("Action", style="bold")
    table.add_column("Opération")
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


def render_docker_and_env(info: dict) -> None:
    tree = Tree("[bold]Configuration générée[/bold]")

    docker_node = tree.add("[cyan]Docker services[/cyan]")
    for service in info["docker_services"]:
        docker_node.add(service)

    env_node = tree.add("[magenta]Variables d'environnement[/magenta]")
    for variable in info["env_variables"]:
        env_node.add(variable)

    console.print(tree)


@app.command()
def dry_run(
    manifest_path: Path,
    info: bool = typer.Option(
        False,
        "--info",
        help="Affiche les détails complets du plan.",
    ),
    json_output: bool = typer.Option(
        False,
        "--json",
        help="Affiche le plan complet au format JSON.",
    ),
) -> None:
    registry = ModuleRegistry("templates")
    manifest = load_project_manifest_from_yaml(str(manifest_path))

    generator = ProjectGenerator(registry)

    plan = generator.plan(
        manifest,
        "C:/Users/esteb/Documents/developpement/test_projet_generation",
    )

    plan_dict = plan.to_dict()

    if json_output:
        console.print_json(data=plan_dict)
        return

    render_project_info(plan_dict)
    render_summary(plan.summary)

    if plan.summary["files_to_overwrite"] > 0:
        console.print(
            f"[yellow]Warning:[/yellow] "
            f"{plan.summary['files_to_overwrite']} fichier(s) seront écrasés."
        )

    if info:
        render_docker_and_env(plan_dict)
        render_files(plan_dict["files"])

if __name__ == "__main__":
    app()