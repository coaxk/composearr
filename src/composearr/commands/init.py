"""Init command — generate compose files from best-practice templates."""

from __future__ import annotations

from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table
from rich import box

console = Console()


def init_command(
    template: str | None = typer.Argument(None, help="Template name (e.g., 'sonarr')"),
    output: Path | None = typer.Option(
        None,
        "--output", "-o",
        help="Output directory (default: ./<template>)",
    ),
    list_all: bool = typer.Option(
        False,
        "--list", "-l",
        help="List all available templates",
    ),
) -> None:
    """Generate a compose file from a best-practice template.

    Creates a production-ready compose file for common self-hosted apps.
    Everything ComposeArr checks for — baked in from the start!

    Examples:
        composearr init sonarr
        composearr init nginx --output ~/docker/nginx
        composearr init --list
    """
    from composearr.templates.engine import TemplateEngine

    engine = TemplateEngine()
    templates = engine.list_templates()

    if not templates:
        console.print("[red]No templates available[/]")
        raise typer.Exit(1)

    # List mode
    if list_all or template is None:
        _show_template_list(templates)

        if list_all:
            return

        # Interactive selection
        from InquirerPy import inquirer
        from InquirerPy.base.control import Choice

        choices = [
            Choice(value=name, name=f"{name:<15s} — {meta.description}")
            for name, meta in sorted(templates.items())
        ]
        choices.append(Choice(value="_cancel", name="✖  Cancel"))

        template = inquirer.select(
            message="Select a template:",
            choices=choices,
        ).execute()

        if template == "_cancel":
            return

    # Validate template exists
    meta = engine.get_template(template)
    if meta is None:
        available = ", ".join(sorted(templates.keys()))
        console.print(f"[red]Template '{template}' not found[/]")
        console.print(f"[dim]Available: {available}[/]")
        raise typer.Exit(1)

    # Default output directory
    if output is None:
        output = Path.cwd() / template

    # Show what we're about to generate
    console.print()
    console.print(f"  [cyan]Template:[/]  {template} — {meta.description}")
    console.print(f"  [cyan]Category:[/] {meta.category}")
    console.print(f"  [cyan]Output:[/]   {output}")
    console.print()

    # Show ports and volumes info
    if meta.ports:
        console.print(f"  [dim]Ports:[/]")
        for p in meta.ports:
            console.print(f"    [dim]{p.get('host', '?')}:{p.get('container', '?')} — {p.get('description', '')}[/]")
        console.print()

    if meta.volumes_info:
        console.print(f"  [dim]Volumes:[/]")
        for v in meta.volumes_info:
            console.print(f"    [dim]{v.get('name', '?')} — {v.get('description', '')}[/]")
        console.print()

    # Collect variables
    from InquirerPy import inquirer

    variables: dict[str, str] = {}
    if meta.env_vars:
        console.print(f"  [cyan]Configure environment variables:[/]")
        console.print()
        for var in meta.env_vars:
            var_name = var.get("name", "")
            default = var.get("default", "")
            desc = var.get("description", "")
            hint = f" ({desc})" if desc else ""

            value = inquirer.text(
                message=f"{var_name}{hint}:",
                default=default,
            ).execute()
            variables[var_name] = value

    # Check if output exists
    if output.exists() and any(output.iterdir()):
        overwrite = inquirer.confirm(
            message=f"{output} already exists and is not empty. Continue?",
            default=False,
        ).execute()
        if not overwrite:
            console.print("  [dim]Cancelled.[/]")
            return

    # Generate
    try:
        result = engine.generate(template, output, variables)
    except Exception as e:
        console.print(f"[red]Error generating template:[/] {e}")
        raise typer.Exit(1)

    # Success output
    console.print()
    console.print(f"  [green]✓[/] Generated {template} compose stack!")
    console.print()
    console.print(f"  [cyan]Files created:[/]")
    console.print(f"    compose.yaml  — {result.compose_path}")
    if result.env_path:
        console.print(f"    .env          — {result.env_path}")
    console.print()
    console.print(f"  [cyan]Next steps:[/]")
    console.print(f"    1. Review compose.yaml and update volume paths")
    console.print(f"    2. Edit .env with your actual values")
    console.print(f"    3. cd {output}")
    console.print(f"    4. docker compose up -d")
    console.print()
    console.print(f"  [dim]Tip: Run 'composearr audit {output}' to verify your config![/]")
    console.print()


def _show_template_list(templates: dict) -> None:
    """Display a formatted table of available templates."""
    # Group by category
    categories: dict[str, list] = {}
    for name, meta in sorted(templates.items()):
        cat = meta.category
        categories.setdefault(cat, []).append((name, meta))

    table = Table(
        title="Available Templates",
        box=box.SIMPLE_HEAD,
        header_style="dim",
    )
    table.add_column("TEMPLATE", style="bold cyan")
    table.add_column("DESCRIPTION")
    table.add_column("CATEGORY", style="dim")
    table.add_column("TAGS", style="dim")

    for cat in sorted(categories.keys()):
        for name, meta in categories[cat]:
            tags = ", ".join(meta.tags) if meta.tags else ""
            table.add_row(name, meta.description, meta.category, tags)

    console.print(table)
    console.print()
