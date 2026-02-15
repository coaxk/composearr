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
    no_args_is_help=False,
    add_completion=False,
    invoke_without_command=True,
)
console = make_console()

# Color tokens
C_MUTED = "#71717a"
C_TEAL = "#2dd4bf"
C_ERR = "#ef4444"
C_WARN = "#f59e0b"
C_INFO = "#3b82f6"
C_TEXT = "#fafafa"
C_OK = "#22c55e"
C_BORDER = "#27272a"


WHALE_ART = (
    "[#3b82f6]"
    "\n                    ##         ."
    "\n              ## ## ##        =="
    "\n           ## ## ## ## ##    ==="
    '\n       /"""""""""""""""""\\___/ ==='
    "\n      {                       /  ===-"
    "\n       \\______ O           __/"
    "\n         \\    \\         __/"
    "\n          \\____\\_______/[/]"
)


def version_callback(value: bool) -> None:
    if value:
        console.print(f"composearr v{__version__}")
        raise typer.Exit()


@app.callback(invoke_without_command=True)
def main(
    ctx: typer.Context,
    version: bool = typer.Option(
        False, "--version", "-v", help="Show version", callback=version_callback, is_eager=True
    ),
) -> None:
    """ComposeArr — Docker Compose hygiene linter."""
    if ctx.invoked_subcommand is None:
        from composearr.tui import launch_tui
        launch_tui()


@app.command()
def audit(
    path: str = typer.Argument(None, help="Path to scan (auto-detects if omitted)"),
    severity: str = typer.Option("error", "--severity", "-s", help="Minimum severity to show details (error, warning, info)"),
    rule: str = typer.Option(None, "--rule", "-r", help="Only run specific rules (comma-separated)"),
    ignore: str = typer.Option(None, "--ignore", "-i", help="Skip specific rules (comma-separated)"),
    verbose: bool = typer.Option(False, "--verbose", help="Show full file context for each issue"),
    group_by: str = typer.Option("rule", "--group-by", "-g", help="Group issues by: rule, file, severity"),
    output_format: str = typer.Option("console", "--format", "-f", help="Output format: console, json, github, sarif"),
    no_network: bool = typer.Option(False, "--no-network", help="Disable network features (tag analysis)"),
    output: str = typer.Option(None, "--output", "-o", help="Output file path (auto-named for non-console formats)"),
) -> None:
    """Scan Docker Compose files for issues."""
    if path is None:
        from composearr.scanner.discovery import detect_stack_directory
        detected = detect_stack_directory()
        if detected:
            root = detected
            console.print(f"  [{C_INFO}]\u2139[/]  [{C_TEXT}]Auto-detected stack directory:[/] [{C_TEAL}]{root}[/]")
        else:
            root = Path.cwd().resolve()
            console.print(f"  [{C_INFO}]\u2139[/]  [{C_TEXT}]No stack directory found, scanning:[/] [{C_TEAL}]{root}[/]")
    else:
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

    # Run audit with progress (stderr for machine formats so piping works)
    if output_format in ("json", "github", "sarif"):
        import sys as _sys
        if _sys.stderr.isatty():
            reporter = RichProgressReporter(stderr_mode=True)
            result = run_audit(root, progress=reporter)
        else:
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
    content: str | None = None
    if output_format == "json":
        content = format_json(result, str(root), fmt_opts)
    elif output_format == "github":
        content = format_github(result, str(root), fmt_opts)
    elif output_format == "sarif":
        content = format_sarif(result, str(root), fmt_opts)
    else:
        formatter = ConsoleFormatter(console)
        formatter.render(result, str(root), options=fmt_opts)

    if content is not None:
        # Print to stdout
        print(content)

        # Auto-save to file (when --output given, or when running interactively)
        import sys as _sys
        should_save = output is not None or _sys.stdout.isatty()
        if should_save:
            from datetime import datetime
            ext_map = {"json": "json", "sarif": "sarif", "github": "txt"}
            ext = ext_map.get(output_format, "txt")
            if output:
                out_path = Path(output)
            else:
                timestamp = datetime.now().strftime("%Y-%m-%dT%H-%M-%S")
                out_path = Path(f"composearr-audit-{timestamp}.{ext}")
            out_path.write_text(content, encoding="utf-8")
            err_console = Console(file=_sys.stderr, highlight=False)
            err_console.print(f"\n  [{C_OK}]\u2713[/] Saved to [{C_TEAL}]{out_path}[/]")

    # Exit code: 1 if errors, 0 otherwise
    if result.error_count > 0:
        raise typer.Exit(code=1)


@app.command()
def fix(
    path: str = typer.Argument(None, help="Path to scan (auto-detects if omitted)"),
    rule: str = typer.Option(None, "--rule", "-r", help="Only fix specific rules (comma-separated)"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Show what would be fixed without applying"),
    no_backup: bool = typer.Option(False, "--no-backup", help="Skip creating .bak backup files"),
    no_network: bool = typer.Option(False, "--no-network", help="Disable network features (tag analysis)"),
) -> None:
    """Apply auto-fixes to Docker Compose files."""
    if path is None:
        from composearr.scanner.discovery import detect_stack_directory
        detected = detect_stack_directory()
        if detected:
            root = detected
            console.print(f"  [{C_INFO}]\u2139[/]  [{C_TEXT}]Auto-detected stack directory:[/] [{C_TEAL}]{root}[/]")
        else:
            root = Path.cwd().resolve()
            console.print(f"  [{C_INFO}]\u2139[/]  [{C_TEXT}]No stack directory found, scanning:[/] [{C_TEAL}]{root}[/]")
    else:
        root = Path(path).resolve()

    if not root.is_dir():
        console.print(f"[{C_ERR}]Error:[/] {path} is not a directory")
        raise typer.Exit(code=2)

    # Configure network features
    from composearr.rules.CA0xx_images import set_network_enabled
    set_network_enabled(not no_network)

    # Run audit
    reporter = RichProgressReporter(console)
    console.print()
    result = run_audit(root, progress=reporter)
    console.print()

    # Filter by rule
    fixable = [i for i in result.all_issues if i.fix_available and i.suggested_fix]
    if rule:
        rule_ids = {r.strip().upper() for r in rule.split(",")}
        fixable = [i for i in fixable if i.rule_id in rule_ids]

    if not fixable:
        console.print(f"  [{C_OK}]\u2713[/] [{C_TEXT}]No fixable issues found[/]")
        raise typer.Exit()

    console.print(f"  [{C_TEXT}]Found[/] [bold {C_TEAL}]{len(fixable)}[/] [{C_TEXT}]fixable issues[/]")
    console.print()

    # Show what will be fixed
    from collections import defaultdict
    by_file: dict[str, list] = defaultdict(list)
    for issue in fixable:
        by_file[issue.file_path].append(issue)

    for file_path in sorted(by_file.keys()):
        try:
            rel = str(Path(file_path).relative_to(root))
        except ValueError:
            rel = file_path
        console.print(f"  [{C_TEXT}]{rel}[/]")
        for issue in by_file[file_path]:
            svc = f" [bold {C_TEAL}]{issue.service}[/]" if issue.service else ""
            console.print(f"    [{C_WARN}]\u25cf[/] [{C_WARN}]{issue.rule_id}[/]  {issue.message}{svc}")
        console.print()

    if dry_run:
        console.print(f"  [{C_MUTED}]Dry run \u2014 no files modified[/]")
        raise typer.Exit()

    from composearr.fixer import apply_fixes
    applied, skipped, errors = apply_fixes(fixable, root, backup=not no_backup)

    if applied:
        console.print(f"  [{C_OK}]\u2713[/] [{C_TEXT}]Applied {applied} fixes[/]")
    if skipped:
        console.print(f"  [{C_WARN}]\u26a0[/] [{C_TEXT}]{skipped} fixes skipped (not auto-applicable)[/]")
    if errors:
        console.print(f"  [{C_ERR}]\u2716[/] [{C_TEXT}]{errors} fixes failed[/]")
    if not no_backup and applied:
        console.print(f"  [{C_MUTED}]Backup files saved with .bak extension[/]")


@app.command()
def ports(
    path: str = typer.Argument(None, help="Path to scan (auto-detects if omitted)"),
    conflicts_only: bool = typer.Option(False, "--conflicts", "-c", help="Only show conflicting ports"),
    output_format: str = typer.Option("console", "--format", "-f", help="Output format: console, json, csv"),
    output: str = typer.Option(None, "--output", "-o", help="Output file path"),
) -> None:
    """Show port allocation table across all services."""
    from composearr.commands.ports import collect_ports, render_port_table, format_ports_json, format_ports_csv

    if path is None:
        from composearr.scanner.discovery import detect_stack_directory
        detected = detect_stack_directory()
        if detected:
            root = detected
            console.print(f"  [{C_INFO}]\u2139[/]  [{C_TEXT}]Auto-detected stack directory:[/] [{C_TEAL}]{root}[/]")
        else:
            root = Path.cwd().resolve()
            console.print(f"  [{C_INFO}]\u2139[/]  [{C_TEXT}]No stack directory found, scanning:[/] [{C_TEAL}]{root}[/]")
    else:
        root = Path(path).resolve()

    if not root.is_dir():
        console.print(f"[{C_ERR}]Error:[/] {path} is not a directory")
        raise typer.Exit(code=2)

    import sys as _sys
    if _sys.stdout.isatty() and output_format == "console":
        from rich.progress import Progress, SpinnerColumn, TextColumn
        with Progress(
            SpinnerColumn(style=C_TEAL),
            TextColumn(f"[{C_MUTED}]Scanning ports\u2026[/]"),
            console=console,
            transient=True,
        ) as progress:
            progress.add_task("", total=None)
            all_ports = collect_ports(root)
    else:
        all_ports = collect_ports(root)

    if output_format == "json":
        content = format_ports_json(all_ports, root)
        print(content)
    elif output_format == "csv":
        content = format_ports_csv(all_ports, root)
        print(content)
    else:
        render_port_table(all_ports, root, console, show_conflicts_only=conflicts_only)
        content = None

    if output and content:
        Path(output).write_text(content, encoding="utf-8")
        console.print(f"  [{C_OK}]\u2713[/] Saved to [{C_TEAL}]{output}[/]")


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
    console.print(f"  [{C_MUTED}]More rules coming soon \u2014[/] [{C_TEAL}]github.com/coaxk/composearr[/]")
    console.print()
    console.print(f"  [{C_MUTED}]Use[/] [bold {C_TEXT}]composearr explain CA001[/] [{C_MUTED}]for detailed rule documentation[/]")
    console.print()


@app.command()
def config(
    path: str = typer.Argument(None, help="Project path to check config for"),
    validate_only: bool = typer.Option(False, "--validate", help="Only validate, don't show effective config"),
) -> None:
    """Validate and show effective configuration."""
    from composearr.commands.config_cmd import validate_config_data, render_effective_config
    from composearr.config import load_config
    from ruamel.yaml import YAML

    project_path = Path(path).resolve() if path else None
    yaml = YAML()

    # Find and validate config files
    config_files: list[Path] = []
    user_config = Path.home() / ".composearr.yml"
    if user_config.is_file():
        config_files.append(user_config)
    if project_path:
        for name in [".composearr.yml", ".composearr.yaml"]:
            p = project_path / name
            if p.is_file():
                config_files.append(p)
                break

    all_issues: list[str] = []
    has_config = False

    for cf in config_files:
        has_config = True
        try:
            data = yaml.load(cf)
            if isinstance(data, dict):
                file_issues = validate_config_data(data)
                if file_issues:
                    console.print(f"\n  [{C_WARN}]\u26a0[/] [{C_TEXT}]Issues in {cf}:[/]")
                    for issue in file_issues:
                        console.print(f"    [{C_ERR}]\u2022[/] [{C_TEXT}]{issue}[/]")
                    all_issues.extend(file_issues)
                else:
                    console.print(f"\n  [{C_OK}]\u2713[/] [{C_TEXT}]{cf}[/] [{C_OK}]valid[/]")
            else:
                console.print(f"\n  [{C_WARN}]\u26a0[/] [{C_TEXT}]{cf} is empty or not a mapping[/]")
        except Exception as e:
            console.print(f"\n  [{C_ERR}]\u2716[/] [{C_TEXT}]{cf}:[/] [{C_ERR}]{e}[/]")
            all_issues.append(str(e))

    if not has_config:
        console.print(f"\n  [{C_MUTED}]No .composearr.yml found. Using defaults.[/]")
        console.print(f"  [{C_MUTED}]Create one at {user_config} or in your project directory.[/]")

    if not validate_only:
        effective = load_config(project_path)
        render_effective_config(effective, console, project_path)

    if all_issues:
        raise typer.Exit(code=1)


@app.command()
def explain(
    rule_id: str = typer.Argument(..., help="Rule ID to explain (e.g. CA001)"),
) -> None:
    """Show detailed explanation of a rule."""
    from composearr.commands.explain import render_explanation

    rule_id_upper = rule_id.strip().upper()

    if not render_explanation(rule_id_upper, console):
        # Try matching by name
        from composearr.config import _RULE_NAME_TO_ID
        resolved = _RULE_NAME_TO_ID.get(rule_id.strip().lower())
        if resolved and render_explanation(resolved, console):
            return

        console.print(f"  [{C_ERR}]Unknown rule:[/] [{C_TEXT}]{rule_id}[/]")
        console.print()
        console.print(f"  [{C_MUTED}]Available rules:[/]")
        from composearr.rules.base import get_all_rules
        for r in sorted(get_all_rules(), key=lambda x: x.id):
            console.print(f"    [{C_TEAL}]{r.id}[/]  {r.name}")
        console.print()
        raise typer.Exit(code=1)


@app.command(hidden=True)
def whale() -> None:
    """You found the Easter egg!"""
    console.print()
    console.print(WHALE_ART)
    console.print()
    console.print(f"  [bold {C_TEAL}]ComposeArr[/] [{C_MUTED}]v{__version__}[/]")
    console.print(f"  [{C_MUTED}]Keeping your Docker stacks shipshape[/] \U0001f433")
    console.print()
