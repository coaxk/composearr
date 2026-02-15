"""CLI entry point — Typer app."""

from __future__ import annotations

import sys
from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table
from rich import box
from rich.style import Style

from composearr import __version__
from composearr.engine import run_audit
from composearr.formatters.console import ConsoleFormatter, make_console
from composearr.formatters.github_formatter import format_github
from composearr.formatters.json_formatter import format_json
from composearr.formatters.progress import RichProgressReporter
from composearr.formatters.sarif_formatter import format_sarif
from composearr.models import FormatOptions, Severity, SEVERITY_RANK
from composearr.rules.base import get_all_rules

app = typer.Typer(
    name="composearr",
    help="Docker Compose hygiene linter with cross-file intelligence.",
    no_args_is_help=True,
    add_completion=False,
)
console = make_console()

# Color tokens
C_MUTED = "#71717a"
C_TEAL = "#2dd4bf"
C_ERR = "#ef4444"
C_WARN = "#f59e0b"
C_INFO = "#3b82f6"
C_TEXT = "#fafafa"
C_BORDER = "#27272a"


def version_callback(value: bool) -> None:
    if value:
        console.print(f"composearr v{__version__}")
        raise typer.Exit()


@app.callback()
def main(
    version: bool = typer.Option(
        False, "--version", "-v", help="Show version", callback=version_callback, is_eager=True
    ),
) -> None:
    """ComposeArr — Docker Compose hygiene linter."""


@app.command()
def audit(
    path: str = typer.Argument(".", help="Path to scan for compose files"),
    severity: str = typer.Option("error", "--severity", "-s", help="Minimum severity to show details (error, warning, info)"),
    rule: str = typer.Option(None, "--rule", "-r", help="Only run specific rules (comma-separated)"),
    ignore: str = typer.Option(None, "--ignore", "-i", help="Skip specific rules (comma-separated)"),
    verbose: bool = typer.Option(False, "--verbose", help="Show full file context for each issue"),
    group_by: str = typer.Option("severity", "--group-by", "-g", help="Group issues by: severity, file, rule"),
    output_format: str = typer.Option("console", "--format", "-f", help="Output format: console, json, github, sarif"),
    no_network: bool = typer.Option(False, "--no-network", help="Disable network features (tag analysis)"),
) -> None:
    """Scan Docker Compose files for issues."""
    root = Path(path).resolve()

    if not root.is_dir():
        console.print(f"[{C_ERR}]Error:[/] {path} is not a directory")
        raise typer.Exit(code=2)

    # Parse severity
    try:
        min_severity = Severity(severity.lower())
    except ValueError:
        console.print(f"[{C_ERR}]Error:[/] Invalid severity: {severity}. Use: error, warning, info")
        raise typer.Exit(code=2)

    # Configure network features
    from composearr.rules.CA0xx_images import set_network_enabled
    set_network_enabled(not no_network)

    # Run audit — suppress progress for machine-readable formats
    if output_format in ("json", "github", "sarif"):
        result = run_audit(root)
    else:
        reporter = RichProgressReporter(console)
        console.print()
        result = run_audit(root, progress=reporter)
        console.print()

    # Filter by rule (before rendering)
    if rule:
        rule_ids = {r.strip().upper() for r in rule.split(",")}
        result.issues = [i for i in result.issues if i.rule_id in rule_ids]
        result.cross_file_issues = [i for i in result.cross_file_issues if i.rule_id in rule_ids]

    # Filter by ignore (before rendering)
    if ignore:
        ignore_ids = {r.strip().upper() for r in ignore.split(",")}
        result.issues = [i for i in result.issues if i.rule_id not in ignore_ids]
        result.cross_file_issues = [i for i in result.cross_file_issues if i.rule_id not in ignore_ids]

    # Format options
    fmt_opts = FormatOptions(
        min_severity=min_severity,
        verbose=verbose,
        group_by=group_by,
    )

    # Output routing
    if output_format == "json":
        print(format_json(result, str(root), fmt_opts))
    elif output_format == "github":
        print(format_github(result, str(root), fmt_opts))
    elif output_format == "sarif":
        print(format_sarif(result, str(root), fmt_opts))
    else:
        formatter = ConsoleFormatter(console)
        formatter.render(result, str(root), options=fmt_opts)

    # Exit code: 1 if errors, 0 otherwise
    if result.error_count > 0:
        raise typer.Exit(code=1)


@app.command()
def rules() -> None:
    """List all available rules."""
    all_rules = get_all_rules()

    sev_colors = {
        Severity.ERROR: C_ERR,
        Severity.WARNING: C_WARN,
        Severity.INFO: C_INFO,
    }

    table = Table(
        box=box.SIMPLE_HEAD,
        border_style=Style(color=C_BORDER),
        header_style=f"{C_MUTED}",
        padding=(0, 2),
        show_edge=False,
    )
    table.add_column("", width=2)
    table.add_column("RULE", style=f"bold {C_TEXT}", no_wrap=True)
    table.add_column("SEVERITY", no_wrap=True)
    table.add_column("NAME", style=f"{C_TEXT}")
    table.add_column("DESCRIPTION", style=C_MUTED)

    for r in sorted(all_rules, key=lambda x: x.id):
        color = sev_colors.get(r.severity, C_MUTED)
        dot = f"[{color}]\u25cf[/]"
        sev_label = f"[{color}]{r.severity.value}[/]"
        table.add_row(dot, r.id, sev_label, r.name, r.description)

    console.print()
    console.print(f"  [{C_TEXT}]Available Rules[/]  [{C_MUTED}]{len(all_rules)} rules[/]")
    console.print()
    console.print(table)
    console.print()
