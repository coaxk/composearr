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
from composearr.security.input_validator import validate_scan_path

app = typer.Typer(
    name="composearr",
    help="Docker Compose linter and advisor. Catch configuration mistakes before they cause incidents.",
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


def _validate_path(root: Path, raw: str | None) -> None:
    """Validate a scan path and exit with error if invalid."""
    ok, err = validate_scan_path(root)
    if not ok:
        console.print(f"[{C_ERR}]Error:[/] {err}")
        raise typer.Exit(code=2)


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
    """ComposeArr — Docker Compose linter and advisor."""
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
    explain: bool = typer.Option(False, "--explain", "-e", help="Show detailed explanations for each triggered rule"),
    no_suppression: bool = typer.Option(False, "--no-suppression", help="Ignore inline suppression comments"),
    recursive: bool = typer.Option(False, "--recursive", "-R", help="Scan subdirectories recursively"),
    max_depth: int = typer.Option(None, "--max-depth", help="Maximum directory depth for recursive scan"),
    profile: str = typer.Option(None, "--profile", "-P", help="Rule profile: strict, balanced, relaxed"),
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

    _validate_path(root, path)

    # Parse severity
    try:
        min_severity = Severity(severity.lower())
    except ValueError:
        console.print(f"[{C_ERR}]Error:[/] Invalid severity: {severity}. Use: error, warning, info")
        raise typer.Exit(code=2)

    # Configure network features
    from composearr.rules.CA0xx_images import set_network_enabled
    set_network_enabled(not no_network)

    # Configure suppression and profile
    from composearr.config import load_config
    audit_config = load_config(root)
    if no_suppression:
        audit_config.honor_suppressions = False
    if recursive:
        audit_config.recursive = True
    if max_depth is not None:
        audit_config.max_depth = max_depth
    if profile:
        from composearr.profiles import apply_profile
        try:
            audit_config.rules = apply_profile(audit_config.rules, profile)
            audit_config.profile = profile
        except ValueError as e:
            console.print(f"[{C_ERR}]Error:[/] {e}")
            raise typer.Exit(code=2)

    # Run audit with progress (stderr for machine formats so piping works)
    if output_format in ("json", "github", "sarif"):
        import sys as _sys
        if _sys.stderr.isatty():
            reporter = RichProgressReporter(stderr_mode=True)
            result = run_audit(root, config=audit_config, progress=reporter)
        else:
            result = run_audit(root, config=audit_config)
    else:
        reporter = RichProgressReporter(console)
        console.print()
        result = run_audit(root, config=audit_config, progress=reporter)
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

        # Show detailed explanations for triggered rules
        if explain:
            from composearr.commands.explain import render_explanation
            triggered_rules = sorted({i.rule_id for i in result.all_issues})
            if triggered_rules:
                console.print()
                console.print(f"  [bold {C_TEXT}]Detailed Explanations[/]")
                for rule_id in triggered_rules:
                    render_explanation(rule_id, console)

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

    # Save to audit history
    try:
        from composearr.history import AuditHistory
        from composearr.scoring import calculate_stack_score

        score = calculate_stack_score(
            result.all_issues,
            result.total_services,
            file_count=len(result.compose_files),
        )
        history = AuditHistory(root)
        history.save_audit(
            issues=result.all_issues,
            score=score,
            files_scanned=len(result.compose_files),
            services_scanned=result.total_services,
            duration_seconds=result.timing.total_seconds,
        )
    except Exception:
        pass  # History saving should never break the audit

    # Exit code: 1 if errors, 0 otherwise
    if result.error_count > 0:
        raise typer.Exit(code=1)


@app.command()
def fix(
    path: str = typer.Argument(None, help="Path to scan (auto-detects if omitted)"),
    rule: str = typer.Option(None, "--rule", "-r", help="Only fix specific rules (comma-separated)"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Show what would be fixed without applying"),
    preview: bool = typer.Option(False, "--preview", "-p", help="Show colored diff preview of changes before applying"),
    no_backup: bool = typer.Option(False, "--no-backup", help="Skip creating .bak backup files"),
    no_network: bool = typer.Option(False, "--no-network", help="Disable network features (tag analysis)"),
    no_suppression: bool = typer.Option(False, "--no-suppression", help="Ignore inline suppression comments"),
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

    _validate_path(root, path)

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

    if preview:
        from composearr.fixer import preview_fixes
        from composearr.diff import DiffGenerator

        previews = preview_fixes(fixable)
        differ = DiffGenerator()
        for pv in previews:
            try:
                rel = str(pv.file_path.relative_to(root))
            except ValueError:
                rel = str(pv.file_path)
            differ.display_diff(console, pv.original, pv.modified, rel,
                                description=f"{pv.fix_count} fix{'es' if pv.fix_count != 1 else ''}")
            rule_ids = sorted({i.rule_id for i in pv.issues})
            console.print(f"  [{C_MUTED}]Rules: {', '.join(rule_ids)}[/]")
            console.print()

        if not previews:
            console.print(f"  [{C_MUTED}]No previewable changes[/]")
        console.print(f"  [{C_MUTED}]Preview only \u2014 no files modified. Remove --preview to apply.[/]")
        raise typer.Exit()

    from composearr.fixer import apply_fixes
    fix_result = apply_fixes(fixable, root, backup=not no_backup)

    if fix_result.applied:
        console.print(f"  [{C_OK}]\u2713[/] [{C_TEXT}]Applied {fix_result.applied} fixes[/]")
    if fix_result.skipped:
        console.print(f"  [{C_WARN}]\u26a0[/] [{C_TEXT}]{fix_result.skipped} fixes skipped (not auto-applicable)[/]")
    if fix_result.errors:
        console.print(f"  [{C_ERR}]\u2716[/] [{C_TEXT}]{fix_result.errors} fixes failed[/]")
    if fix_result.backup_paths:
        console.print()
        console.print(f"  [{C_OK}]\u2713[/] [{C_TEXT}]Backups created:[/]")
        for bak in fix_result.backup_paths:
            try:
                rel = bak.relative_to(root)
            except ValueError:
                rel = bak
            console.print(f"    [{C_MUTED}]{rel}[/]")
        console.print()
        console.print(f"  [{C_MUTED}]To roll back: copy .bak files over the originals[/]")
        console.print(f"  [{C_MUTED}]  e.g.  cp compose.yaml.bak compose.yaml[/]")


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

    _validate_path(root, path)

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
def topology(
    path: str = typer.Argument(None, help="Path to scan (auto-detects if omitted)"),
    output_format: str = typer.Option("console", "--format", "-f", help="Output format: console, json"),
) -> None:
    """Show network topology and dependency reachability."""
    from composearr.commands.topology import render_topology, format_topology_json

    if path is None:
        from composearr.scanner.discovery import detect_stack_directory
        detected = detect_stack_directory()
        if detected:
            root = detected
            console.print(f"  [{C_INFO}]\u2139[/]  [{C_TEXT}]Auto-detected stack directory:[/] [{C_TEAL}]{root}[/]")
        else:
            root = Path.cwd().resolve()
    else:
        root = Path(path).resolve()

    _validate_path(root, path)

    if output_format == "json":
        content = format_topology_json(root)
        typer.echo(content)
    else:
        render_topology(root, console)


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


@app.command()
def history(
    path: str = typer.Argument(None, help="Stack directory (auto-detects if omitted)"),
    limit: int = typer.Option(10, "--limit", "-n", help="Number of entries to show"),
) -> None:
    """View audit history and score trends."""
    if path is None:
        from composearr.scanner.discovery import detect_stack_directory
        detected = detect_stack_directory()
        if detected:
            root = detected
        else:
            root = Path.cwd().resolve()
    else:
        root = Path(path).resolve()

    from composearr.history import AuditHistory, make_sparkline

    hist = AuditHistory(root)
    entries = hist.get_recent(limit=limit)

    if not entries:
        console.print(f"\n  [{C_MUTED}]No audit history found for {root}[/]")
        console.print(f"  [{C_MUTED}]Run an audit first:[/] [{C_TEAL}]composearr audit[/]")
        console.print()
        return

    # History table
    table = Table(
        box=box.SIMPLE_HEAD,
        border_style=Style(color=C_BORDER),
        header_style=f"{C_MUTED}",
        padding=(0, 2),
        show_edge=False,
    )
    table.add_column("DATE", style=f"{C_TEXT}", no_wrap=True)
    table.add_column("GRADE", justify="center")
    table.add_column("SCORE", justify="right", style=f"{C_TEXT}")
    table.add_column("ISSUES", justify="right", style=f"{C_TEXT}")
    table.add_column("ERR", justify="right")
    table.add_column("WARN", justify="right")
    table.add_column("FILES", justify="right", style=f"{C_MUTED}")
    table.add_column("SVCS", justify="right", style=f"{C_MUTED}")
    table.add_column("TIME", justify="right", style=f"{C_MUTED}")

    grade_colors = {
        "A+": C_OK, "A": C_OK, "A-": C_OK,
        "B+": C_WARN, "B": C_WARN, "B-": C_WARN,
        "C+": C_WARN, "C": C_WARN, "C-": C_WARN,
        "D+": C_ERR, "D": C_ERR, "D-": C_ERR,
        "F": C_ERR,
    }

    for entry in entries:
        ts = entry.timestamp[:19].replace("T", " ")
        gc = grade_colors.get(entry.grade, C_TEXT)
        dur = f"{entry.duration_seconds:.1f}s" if entry.duration_seconds else ""
        table.add_row(
            ts,
            f"[{gc}]{entry.grade}[/]",
            str(entry.score),
            str(entry.total_issues),
            f"[{C_ERR}]{entry.errors}[/]" if entry.errors else "0",
            f"[{C_WARN}]{entry.warnings}[/]" if entry.warnings else "0",
            str(entry.files_scanned),
            str(entry.services_scanned),
            dur,
        )

    console.print()
    console.print(f"  [{C_TEXT}]Audit History[/]  [{C_MUTED}]{len(entries)} entries[/]")
    console.print()
    console.print(table)
    console.print()

    # Sparkline
    score_history = hist.get_score_history(limit=30)
    if len(score_history) >= 2:
        scores = [s for _, s in score_history]
        sparkline = make_sparkline(scores)
        console.print(f"  [{C_MUTED}]Score trend:[/] [{C_TEAL}]{sparkline}[/]")

    # Trend
    trend = hist.get_trend()
    if trend:
        if trend.improved:
            console.print(f"  [{C_OK}]\u25b2 {trend.summary()}[/]")
        elif trend.score_delta < 0:
            console.print(f"  [{C_ERR}]\u25bc {trend.summary()}[/]")
        else:
            console.print(f"  [{C_MUTED}]\u25ac {trend.summary()}[/]")
    console.print()


@app.command()
def freshness(
    path: str = typer.Argument(None, help="Stack directory (auto-detects if omitted)"),
    timeout: int = typer.Option(10, "--timeout", "-t", help="API timeout in seconds"),
) -> None:
    """Check for newer image versions across your stack."""
    if path is None:
        from composearr.scanner.discovery import detect_stack_directory
        detected = detect_stack_directory()
        if detected:
            root = detected
        else:
            root = Path.cwd().resolve()
    else:
        root = Path(path).resolve()

    _validate_path(root, path)

    from composearr.registry_client import RegistryClient
    from composearr.scanner.discovery import discover_compose_files
    from composearr.scanner.parser import parse_compose_file

    console.print(f"\n  [{C_INFO}]\u2139[/]  [{C_TEXT}]Checking image freshness\u2026[/]")
    console.print(f"  [{C_MUTED}]Querying registries for available tags (this may take a moment)[/]\n")

    paths_found, _ = discover_compose_files(root)
    client = RegistryClient(timeout=timeout)

    all_results = []
    for file_path in paths_found:
        cf = parse_compose_file(file_path)
        if cf.parse_error or not cf.services:
            continue
        results = client.check_freshness(cf.services, str(cf.path))
        all_results.extend(results)

    if not all_results:
        console.print(f"  [{C_MUTED}]No images found to check[/]\n")
        return

    table = Table(
        box=box.SIMPLE_HEAD,
        border_style=Style(color=C_BORDER),
        header_style=f"{C_MUTED}",
        padding=(0, 2),
        show_edge=False,
    )
    table.add_column("SERVICE", style=f"bold {C_TEXT}")
    table.add_column("CURRENT", no_wrap=True)
    table.add_column("LATEST STABLE", no_wrap=True)
    table.add_column("STATUS")
    table.add_column("TAGS", justify="right", style=f"{C_MUTED}")

    for r in all_results:
        if r.error:
            status = f"[{C_MUTED}]{r.error}[/]"
            latest = "-"
        elif r.up_to_date:
            status = f"[{C_OK}]\u2713 Up to date[/]"
            latest = f"[{C_OK}]{r.latest_stable or '-'}[/]"
        elif r.latest_stable and r.current_tag != r.latest_stable:
            status = f"[{C_WARN}]\u25b2 Update available[/]"
            latest = f"[{C_TEAL}]{r.latest_stable}[/]"
        else:
            status = f"[{C_MUTED}]Unknown[/]"
            latest = f"{r.latest_stable or '-'}"

        # Color the current tag
        if r.current_tag == "latest":
            current = f"[{C_WARN}]:latest[/]"
        else:
            current = f"[{C_TEXT}]:{r.current_tag}[/]"

        table.add_row(
            r.service,
            current,
            latest,
            status,
            str(r.available_tags) if r.available_tags else "-",
        )

    console.print(f"  [{C_TEXT}]Image Freshness Report[/]  [{C_MUTED}]{len(all_results)} images[/]")
    console.print()
    console.print(table)
    console.print()
    console.print(f"  [{C_MUTED}]This is informational only. ComposeArr respects your version choices.[/]")
    console.print(f"  [{C_MUTED}]Use[/] [{C_TEAL}]composearr explain CA001[/] [{C_MUTED}]for tag pinning guidance.[/]")
    console.print()


@app.command()
def watch(
    path: str = typer.Argument(None, help="Stack directory to watch (auto-detects if omitted)"),
    debounce: float = typer.Option(1.0, "--debounce", "-d", help="Debounce seconds between re-audits"),
) -> None:
    """Watch compose files and re-audit on changes."""
    if path is None:
        from composearr.scanner.discovery import detect_stack_directory
        detected = detect_stack_directory()
        if detected:
            root = detected
        else:
            root = Path.cwd().resolve()
    else:
        root = Path(path).resolve()

    _validate_path(root, path)

    from composearr.watcher import WatchMode

    watcher = WatchMode(root, debounce=debounce)
    watcher.start(console)


@app.command()
def orphanage(
    path: str = typer.Argument(None, help="Stack directory (auto-detects if omitted)"),
) -> None:
    """Find orphaned Docker resources (volumes, networks) not in compose files.

    Identifies Docker resources that exist but aren't referenced
    in any compose file. ComposeArr never auto-deletes — you decide what to keep.
    """
    if path is None:
        from composearr.scanner.discovery import detect_stack_directory
        detected = detect_stack_directory()
        if detected:
            root = detected
        else:
            root = Path.cwd().resolve()
    else:
        root = Path(path).resolve()

    _validate_path(root, path)

    from composearr.orphanage import OrphanageFinder
    from rich import box
    from rich.table import Table

    finder = OrphanageFinder(root)
    report = finder.find_orphans()

    if not report.docker_available:
        console.print(f"\n  [red]Could not connect to Docker[/]")
        console.print()
        for line in report.error.splitlines():
            console.print(f"  [dim]{line}[/]")
        console.print()
        raise typer.Exit(1)

    if not report.has_orphans:
        console.print(f"\n  [green]✓[/] No orphaned resources found!")
        console.print(f"  All {report.total_volumes} volumes and {report.total_networks} networks are referenced in compose files.")
        return

    if report.orphaned_volumes:
        table = Table(title=f"Orphaned Volumes ({len(report.orphaned_volumes)})", box=box.SIMPLE_HEAD)
        table.add_column("NAME", style="yellow")
        table.add_column("DRIVER")
        table.add_column("MOUNTPOINT", style="dim")
        for v in report.orphaned_volumes:
            table.add_row(v.name, v.driver, v.mountpoint)
        console.print(table)
        console.print()

    if report.orphaned_networks:
        table = Table(title=f"Orphaned Networks ({len(report.orphaned_networks)})", box=box.SIMPLE_HEAD)
        table.add_column("NAME", style="yellow")
        table.add_column("ID", style="dim")
        table.add_column("DRIVER")
        for n in report.orphaned_networks:
            table.add_row(n.name, n.id, n.driver)
        console.print(table)
        console.print()

    console.print(f"  Total orphans: {report.total_orphans}")
    console.print(f"  [dim]Manual cleanup: docker volume rm <name> / docker network rm <name>[/]")
    console.print(f"  [dim]ComposeArr never auto-deletes — you're in control.[/]")


@app.command()
def runtime(
    path: str = typer.Argument(None, help="Stack directory (auto-detects if omitted)"),
) -> None:
    """Compare compose definitions against running containers.

    Shows services that are defined but not running, running but not defined,
    or running with different images than specified in compose files.
    """
    if path is None:
        from composearr.scanner.discovery import detect_stack_directory
        detected = detect_stack_directory()
        if detected:
            root = detected
        else:
            root = Path.cwd().resolve()
    else:
        root = Path(path).resolve()

    _validate_path(root, path)

    from composearr.runtime import RuntimeComparator
    from rich import box
    from rich.table import Table

    comparator = RuntimeComparator(root)
    report = comparator.compare()

    if not report.docker_available:
        console.print(f"\n  [red]Could not connect to Docker[/]")
        console.print()
        for line in report.error.splitlines():
            console.print(f"  [dim]{line}[/]")
        console.print()
        raise typer.Exit(1)

    console.print(f"\n  Compose: {report.compose_services} services  |  Running: {report.running_services} containers")
    console.print()

    if not report.has_diffs:
        console.print(f"  [green]✓[/] All compose services match running containers!")
        return

    sev_colors = {"error": "red", "warning": "yellow", "info": "blue"}
    table = Table(box=box.SIMPLE_HEAD)
    table.add_column("SERVICE", style="bold")
    table.add_column("ISSUE")
    table.add_column("EXPECTED", style="dim")
    table.add_column("ACTUAL", style="dim")
    table.add_column("SEV", justify="center")

    for d in report.diffs:
        color = sev_colors.get(d.severity, "dim")
        table.add_row(d.service, d.category, d.expected, d.actual, f"[{color}]{d.severity}[/]")

    console.print(table)


@app.command()
def init(
    template: str = typer.Argument(None, help="Template name (e.g., 'sonarr')"),
    output: Path = typer.Option(None, "--output", "-o", help="Output directory (default: ./<template>)"),
    list_all: bool = typer.Option(False, "--list", "-l", help="List all available templates"),
) -> None:
    """Generate a compose file from a best-practice template.

    Creates a production-ready compose file for common self-hosted apps
    with all ComposeArr best practices applied.

    Examples:
        composearr init sonarr
        composearr init nginx --output ~/docker/nginx
        composearr init --list
    """
    from composearr.commands.init import init_command
    init_command(template, output, list_all)


@app.command()
def batch(
    path: str = typer.Argument(None, help="Stack directory (auto-detects if omitted)"),
    fix: bool = typer.Option(False, "--fix", help="Auto-fix all fixable issues"),
    yes: bool = typer.Option(False, "--yes", "-y", help="Don't prompt, apply all fixes"),
    severity: str = typer.Option(None, "--severity", "-s", help="Minimum severity (error/warning/info)"),
    rules: str = typer.Option(None, "--rules", "-r", help="Comma-separated rule IDs to fix"),
    no_backup: bool = typer.Option(False, "--no-backup", help="Don't create .bak backups"),
    json_output: bool = typer.Option(False, "--json", help="Output results as JSON"),
) -> None:
    """Batch operations for CI/CD pipelines.

    Scan and fix all compose files without interactive prompts.
    Perfect for automated pipelines and pre-commit hooks.

    Examples:
        composearr batch                          # Scan only
        composearr batch --fix --yes              # Fix everything
        composearr batch --fix --yes --severity error  # Fix errors only
        composearr batch --fix --yes --rules CA001,CA501
    """
    if path is None:
        from composearr.scanner.discovery import detect_stack_directory
        detected = detect_stack_directory()
        root = detected if detected else Path.cwd().resolve()
    else:
        root = Path(path).resolve()

    _validate_path(root, path)

    from composearr.batch import BatchProcessor

    rule_list = [r.strip().upper() for r in rules.split(",")] if rules else None

    processor = BatchProcessor(
        stack_path=root,
        auto_approve=fix and yes,
        create_backups=not no_backup,
    )

    result = processor.fix_all(
        min_severity=severity,
        rule_ids=rule_list,
    )

    if json_output:
        import json
        console.print(json.dumps({
            "files_processed": result.files_processed,
            "issues_found": result.issues_found,
            "issues_fixed": result.issues_fixed,
            "issues_unfixable": result.issues_unfixable,
            "errors": result.errors,
            "exit_code": result.exit_code,
        }, indent=2))
    else:
        console.print(f"\n  [cyan]Batch Results:[/]")
        console.print(f"    Files processed: {result.files_processed}")
        console.print(f"    Issues found:    {result.issues_found}")
        console.print(f"    Issues fixed:    [green]{result.issues_fixed}[/]")
        console.print(f"    Unfixable:       {result.issues_unfixable}")

        if result.fixed_rules:
            console.print(f"\n  [cyan]Fixed by rule:[/]")
            for rule_id, count in sorted(result.fixed_rules.items()):
                console.print(f"    {rule_id}: {count}")

        if result.errors:
            console.print(f"\n  [red]Errors ({len(result.errors)}):[/]")
            for error in result.errors:
                console.print(f"    {error}")

        if not fix:
            console.print(f"\n  [dim]Add --fix --yes to auto-fix all issues[/]")

    raise typer.Exit(result.exit_code)


@app.command(name="help")
def help_cmd(
    command: str = typer.Argument(None, help="Specific command to explain"),
) -> None:
    """Show all available commands with descriptions."""
    from rich.panel import Panel

    COMMANDS = {
        "Core": [
            ("audit", "Analyze compose files for issues", "composearr audit [PATH] [OPTIONS]", [
                ("composearr audit", "Audit current directory"),
                ("composearr audit ~/docker", "Audit specific directory"),
                ("composearr audit --severity warning", "Show warnings and errors"),
                ("composearr audit --format json", "Output as JSON"),
                ("composearr audit --group-by file", "Group by file"),
                ("composearr audit --verbose", "Show full file context"),
            ]),
            ("fix", "Auto-fix detected issues (creates backups)", "composearr fix [PATH] [OPTIONS]", [
                ("composearr fix", "Fix with interactive preview"),
                ("composearr fix --yes", "Apply all fixes without prompts"),
                ("composearr fix --rule CA001,CA501", "Fix specific rules only"),
                ("composearr fix --dry-run", "Preview without applying"),
            ]),
            ("(no args)", "Launch interactive TUI", "composearr", [
                ("composearr", "Launch the full interactive menu"),
            ]),
        ],
        "Analysis": [
            ("ports", "Show port allocation table and conflicts", "composearr ports [PATH]", [
                ("composearr ports", "Show all port mappings"),
            ]),
            ("topology", "Display network topology between services", "composearr topology [PATH]", [
                ("composearr topology", "Show network connections"),
            ]),
            ("history", "View audit history and score trends", "composearr history [PATH]", [
                ("composearr history", "Show recent audit history"),
            ]),
            ("freshness", "Check for newer image versions", "composearr freshness [PATH]", [
                ("composearr freshness", "Check all images for updates"),
            ]),
            ("orphanage", "Find orphaned Docker resources", "composearr orphanage", [
                ("composearr orphanage", "List unused volumes, networks, images"),
            ]),
            ("runtime", "Compare compose vs running containers", "composearr runtime [PATH]", [
                ("composearr runtime", "Show drift between compose and running state"),
            ]),
        ],
        "Utility": [
            ("watch", "Monitor files and re-audit on changes", "composearr watch [PATH]", [
                ("composearr watch", "Watch current directory"),
                ("composearr watch ~/docker", "Watch specific directory"),
            ]),
            ("init", "Generate compose file from template", "composearr init [TEMPLATE]", [
                ("composearr init", "Interactive template selection"),
                ("composearr init sonarr", "Generate Sonarr compose"),
            ]),
            ("batch", "Batch operations for CI/CD", "composearr batch [PATH] [OPTIONS]", [
                ("composearr batch --fix --yes", "Fix all issues non-interactively"),
                ("composearr batch --fix --yes --severity error", "Fix only errors"),
                ("composearr batch --fix --yes --json", "JSON output for CI"),
            ]),
            ("config", "Interactive configuration wizard", "composearr config", [
                ("composearr config", "Create or edit .composearr.yml"),
            ]),
        ],
        "Reference": [
            ("rules", "List all 30 lint rules", "composearr rules", [
                ("composearr rules", "Show all rules with severity"),
            ]),
            ("explain", "Explain a specific rule in detail", "composearr explain <RULE>", [
                ("composearr explain CA001", "Explain the unpinned image tag rule"),
                ("composearr explain CA201", "Explain the healthcheck rule"),
            ]),
            ("help", "Show this command reference", "composearr help [COMMAND]", [
                ("composearr help", "Show all commands"),
                ("composearr help audit", "Detailed help for audit"),
            ]),
        ],
    }

    CATEGORY_ICONS = {
        "Core": "Core Commands",
        "Analysis": "Analysis Commands",
        "Utility": "Utility Commands",
        "Reference": "Reference Commands",
    }

    # Detailed help for a specific command
    if command:
        found = False
        for category, cmds in COMMANDS.items():
            for cmd_name, desc, usage, examples in cmds:
                if cmd_name == command:
                    found = True
                    console.print(Panel(
                        f"[bold {C_TEAL}]{command.upper()}[/]\n\n{desc}",
                        border_style=C_TEAL,
                    ))
                    console.print(f"\n  [bold]Usage:[/]  [{C_TEAL}]{usage}[/]\n")
                    if examples:
                        console.print("  [bold]Examples:[/]\n")
                        for ex_cmd, ex_desc in examples:
                            console.print(f"    [{C_TEAL}]{ex_cmd}[/]")
                            console.print(f"    [{C_MUTED}]{ex_desc}[/]\n")
                    console.print(f"  [{C_MUTED}]Or try: composearr {command} --help[/]\n")
                    break
            if found:
                break
        if not found:
            console.print(f"  [{C_WARN}]No detailed help for '{command}'[/]")
            console.print(f"  Try: [{C_TEAL}]composearr {command} --help[/]")
        raise typer.Exit()

    # Full command index
    console.print(Panel(
        f"[bold {C_TEAL}]ComposeArr Command Reference[/]\n\n"
        f"[{C_MUTED}]Run 'composearr help <command>' for detailed usage[/]",
        border_style=C_TEAL,
    ))

    for category, cmds in COMMANDS.items():
        label = CATEGORY_ICONS.get(category, category)
        console.print(f"\n  [bold]{label}[/]\n")

        cmd_table = Table(show_header=False, box=None, padding=(0, 2))
        cmd_table.add_column("Command", style=C_TEAL, width=20)
        cmd_table.add_column("Description")

        for cmd_name, desc, _usage, _examples in cmds:
            cmd_table.add_row(cmd_name, desc)

        console.print(cmd_table)

    console.print(f"\n  [bold]Quick Start[/]\n")
    console.print(f"    [{C_TEAL}]composearr[/]          [{C_MUTED}]Launch interactive TUI[/]")
    console.print(f"    [{C_TEAL}]composearr audit[/]    [{C_MUTED}]Scan your stack[/]")
    console.print(f"    [{C_TEAL}]composearr fix[/]      [{C_MUTED}]Auto-fix issues[/]")
    console.print(f"    [{C_TEAL}]composearr watch[/]    [{C_MUTED}]Monitor and re-audit[/]")
    console.print()

    console.print(Panel(
        f"[{C_MUTED}]For detailed help:[/]  [{C_TEAL}]composearr help <command>[/]\n"
        f"[{C_MUTED}]Or use the flag:[/]    [{C_TEAL}]composearr audit --help[/]",
        border_style=C_MUTED,
    ))

    raise typer.Exit()


