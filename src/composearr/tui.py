"""Interactive TUI menu for ComposeArr."""

from __future__ import annotations

import sys
from datetime import datetime
from pathlib import Path

from InquirerPy import inquirer
from InquirerPy.base.control import Choice
from rich.console import Console

from composearr import __version__
from composearr.engine import run_audit
from composearr.formatters.console import ConsoleFormatter, make_console
from composearr.formatters.github_formatter import format_github
from composearr.formatters.json_formatter import format_json
from composearr.formatters.progress import RichProgressReporter
from composearr.formatters.sarif_formatter import format_sarif
from composearr.models import FormatOptions, Severity
from composearr.rules.base import get_all_rules

# Color tokens
C_TEAL = "#2dd4bf"
C_MUTED = "#71717a"
C_OK = "#22c55e"
C_ERR = "#ef4444"
C_WARN = "#f59e0b"
C_TEXT = "#fafafa"
C_INFO = "#3b82f6"

# Sentinel values
_BACK = "__back__"
_EXIT = "__exit__"


def _nav_choices() -> list[Choice]:
    """Return Back and Exit choices for appending to any menu."""
    return [
        Choice(value=_BACK, name="\u2190 Back"),
        Choice(value=_EXIT, name="\u2716 Exit"),
    ]


def _check_nav(value: str) -> str | None:
    """Return 'back', 'exit', or None for normal values."""
    if value == _EXIT:
        return "exit"
    if value == _BACK:
        return "back"
    return None


def _resolve_path(console: Console, session: dict) -> str | None:
    """Resolve stack path — reuse session path or prompt for new one.

    Returns the path string, or None if user chose back/exit.
    Saves the resolved path to session for future reuse.
    """
    remembered = session.get("path")

    if remembered:
        # Offer to reuse the remembered path
        path_mode = inquirer.select(
            message="Stack directory:",
            choices=[
                Choice(value="reuse", name=f"Use {remembered}"),
                Choice(value="auto", name="Auto-detect again"),
                Choice(value="manual", name="Enter path manually"),
                *_nav_choices(),
            ],
            default="reuse",
        ).execute()
    else:
        path_mode = inquirer.select(
            message="How to find your stacks?",
            choices=[
                Choice(value="auto", name="Auto-detect Docker stacks"),
                Choice(value="manual", name="Enter path manually"),
                *_nav_choices(),
            ],
            default="auto",
        ).execute()

    nav = _check_nav(path_mode)
    if nav:
        return None

    if path_mode == "reuse":
        return remembered

    if path_mode == "auto":
        from composearr.scanner.discovery import detect_stack_directory
        from rich.progress import Progress, SpinnerColumn, TextColumn
        with Progress(
            SpinnerColumn(style=C_TEAL),
            TextColumn(f"[{C_MUTED}]Searching common locations\u2026[/]"),
            console=console,
            transient=True,
        ) as progress:
            progress.add_task("", total=None)
            detected = detect_stack_directory()
        if detected:
            path = str(detected)
            console.print(f"  [{C_OK}]\u2713[/] [{C_TEXT}]Found stacks at[/] [{C_TEAL}]{path}[/]")
        else:
            console.print(f"  [{C_WARN}]\u26a0[/] [{C_TEXT}]No Docker stacks found in common locations[/]")
            path = inquirer.text(
                message="Enter stack directory:",
                default=str(Path.cwd()),
                validate=lambda p: Path(p).is_dir() or "Directory not found",
            ).execute()
    else:
        path = inquirer.text(
            message="Stack directory:",
            default=remembered or str(Path.cwd()),
            validate=lambda p: Path(p).is_dir() or "Directory not found",
        ).execute()

    session["path"] = path
    return path


def launch_tui() -> None:
    """Launch interactive TUI menu."""
    console = make_console()
    # Session state persists across menu actions
    session: dict = {}

    console.print()
    console.print(f"  [bold {C_TEAL}]\u25c6[/] [bold {C_TEXT}]ComposeArr[/]  [{C_MUTED}]v{__version__}[/]")
    console.print(f"  [{C_MUTED}]Docker Compose hygiene linter[/]")

    while True:
        console.print()
        action = inquirer.select(
            message="What would you like to do?",
            choices=[
                Choice(value="audit", name="Audit Docker stacks"),
                Choice(value="fix", name="Fix issues interactively"),
                Choice(value="ports", name="Port allocation table"),
                Choice(value="rules", name="View available rules"),
                Choice(value="explain", name="Explain a rule"),
                Choice(value="config", name="View/validate config"),
                Choice(value=_EXIT, name="\u2716 Exit"),
            ],
            default="audit",
        ).execute()

        if action == _EXIT:
            console.print(f"\n  [{C_MUTED}]Goodbye![/]\n")
            break

        elif action == "audit":
            _tui_audit(console, session)

        elif action == "fix":
            _tui_fix(console, session)

        elif action == "ports":
            _tui_ports(console, session)

        elif action == "rules":
            _tui_rules(console)

        elif action == "explain":
            _tui_explain(console)

        elif action == "config":
            _tui_config(console, session)


def _tui_audit(console: Console, session: dict | None = None) -> None:
    """Interactive audit flow with back/exit at every step."""
    session = session or {}

    steps = [
        "_step_path",
        "_step_severity",
        "_step_group_by",
        "_step_rules_filter",
        "_step_options",
        "_step_format",
        "_step_destination",
    ]
    step_fns = {
        "_step_path": _step_path,
        "_step_severity": _step_severity,
        "_step_group_by": _step_group_by,
        "_step_rules_filter": _step_rules_filter,
        "_step_options": _step_options,
        "_step_format": _step_format,
        "_step_destination": _step_destination,
    }

    state: dict = {"_session": session}
    idx = 0

    while idx < len(steps):
        step_name = steps[idx]
        result = step_fns[step_name](console, state)

        if result == "exit":
            return
        elif result == "back":
            idx = max(0, idx - 1)
            if idx == 0 and step_name == steps[0]:
                return  # Back from first step = return to main menu
        elif result == "skip":
            idx += 1
        else:
            idx += 1

    # All steps complete — run the audit
    _run_audit(console, state)


def _step_path(console: Console, state: dict) -> str:
    """Step 1: Path selection (uses session memory)."""
    session = state.get("_session", {})
    path = _resolve_path(console, session)
    if path is None:
        return "back"
    state["path"] = path
    return "ok"


def _step_severity(console: Console, state: dict) -> str:
    """Step 2: Minimum severity."""
    severity = inquirer.select(
        message="Minimum severity to display:",
        choices=[
            Choice(value="error", name="Error only"),
            Choice(value="warning", name="Warnings and above"),
            Choice(value="info", name="Everything (info+)"),
            *_nav_choices(),
        ],
        default="error",
    ).execute()

    nav = _check_nav(severity)
    if nav:
        return nav

    state["severity"] = severity
    return "ok"


def _step_group_by(console: Console, state: dict) -> str:
    """Step 3: Group by."""
    group_by = inquirer.select(
        message="Group issues by:",
        choices=[
            Choice(value="rule", name="Rule (default)"),
            Choice(value="file", name="File"),
            Choice(value="severity", name="Severity"),
            *_nav_choices(),
        ],
        default="rule",
    ).execute()

    nav = _check_nav(group_by)
    if nav:
        return nav

    state["group_by"] = group_by
    return "ok"


def _step_rules_filter(console: Console, state: dict) -> str:
    """Step 4: Rule filtering."""
    all_rules = get_all_rules()

    filter_mode = inquirer.select(
        message="Which rules to run?",
        choices=[
            Choice(value="all", name="All rules"),
            Choice(value="select", name="Select specific rules"),
            Choice(value="exclude", name="Exclude specific rules"),
            *_nav_choices(),
        ],
        default="all",
    ).execute()

    nav = _check_nav(filter_mode)
    if nav:
        return nav

    if filter_mode == "select":
        rule_choices = [
            Choice(value=r.id, name=f"{r.id} — {r.name}", enabled=True)
            for r in sorted(all_rules, key=lambda x: x.id)
        ]
        selected = inquirer.checkbox(
            message="Select rules to run (space to toggle):",
            choices=rule_choices,
        ).execute()
        state["rule_ids"] = set(selected) if selected else None
        state["ignore_ids"] = None
    elif filter_mode == "exclude":
        rule_choices = [
            Choice(value=r.id, name=f"{r.id} — {r.name}", enabled=False)
            for r in sorted(all_rules, key=lambda x: x.id)
        ]
        excluded = inquirer.checkbox(
            message="Select rules to skip (space to toggle):",
            choices=rule_choices,
        ).execute()
        state["ignore_ids"] = set(excluded) if excluded else None
        state["rule_ids"] = None
    else:
        state["rule_ids"] = None
        state["ignore_ids"] = None

    return "ok"


def _step_options(console: Console, state: dict) -> str:
    """Step 5: Additional options (verbose, no-network)."""
    options = inquirer.checkbox(
        message="Additional options (space to toggle):",
        choices=[
            Choice(value="verbose", name="Verbose — show full file context for each issue", enabled=False),
            Choice(value="no_network", name="No network — disable tag analysis lookups", enabled=False),
            Choice(value=_BACK, name="\u2190 Back", enabled=False),
            Choice(value=_EXIT, name="\u2716 Exit", enabled=False),
        ],
    ).execute()

    if _EXIT in options:
        return "exit"
    if _BACK in options:
        return "back"

    state["verbose"] = "verbose" in options
    state["no_network"] = "no_network" in options
    return "ok"


def _step_format(console: Console, state: dict) -> str:
    """Step 6: Output format."""
    output_format = inquirer.select(
        message="Output format:",
        choices=[
            Choice(value="console", name="Console (rich terminal output)"),
            Choice(value="json", name="JSON (machine-readable)"),
            Choice(value="sarif", name="SARIF (GitHub Advanced Security)"),
            Choice(value="github", name="GitHub Actions annotations"),
            *_nav_choices(),
        ],
        default="console",
    ).execute()

    nav = _check_nav(output_format)
    if nav:
        return nav

    state["output_format"] = output_format
    return "ok"


def _step_destination(console: Console, state: dict) -> str:
    """Step 7: Output destination (non-console only)."""
    state["save_to_file"] = False
    state["print_to_screen"] = True
    state["output_file"] = None

    if state["output_format"] == "console":
        return "skip"

    destination = inquirer.select(
        message="Output destination:",
        choices=[
            Choice(value="both", name="Save to file AND print to screen"),
            Choice(value="file", name="Save to file only"),
            Choice(value="screen", name="Print to screen only"),
            *_nav_choices(),
        ],
        default="both",
    ).execute()

    nav = _check_nav(destination)
    if nav:
        return nav

    state["save_to_file"] = destination in ("both", "file")
    state["print_to_screen"] = destination in ("both", "screen")

    if state["save_to_file"]:
        ext_map = {"json": "json", "sarif": "sarif", "github": "txt"}
        ext = ext_map.get(state["output_format"], "txt")
        timestamp = datetime.now().strftime("%Y-%m-%dT%H-%M-%S")
        default_name = f"composearr-audit-{timestamp}.{ext}"
        state["output_file"] = inquirer.text(
            message="Output filename:",
            default=default_name,
        ).execute()

    return "ok"


def _run_audit(console: Console, state: dict) -> None:
    """Execute the audit with collected TUI state."""
    # Configure network
    from composearr.rules.CA0xx_images import set_network_enabled
    set_network_enabled(not state.get("no_network", False))

    root = Path(state["path"]).resolve()
    console.print()

    reporter = RichProgressReporter(console)
    result = run_audit(root, progress=reporter)
    console.print()

    # Apply rule filters
    rule_ids = state.get("rule_ids")
    ignore_ids = state.get("ignore_ids")

    if rule_ids:
        result.issues = [i for i in result.issues if i.rule_id in rule_ids]
        result.cross_file_issues = [i for i in result.cross_file_issues if i.rule_id in rule_ids]

    if ignore_ids:
        result.issues = [i for i in result.issues if i.rule_id not in ignore_ids]
        result.cross_file_issues = [i for i in result.cross_file_issues if i.rule_id not in ignore_ids]

    # Format options
    fmt_opts = FormatOptions(
        min_severity=Severity(state["severity"]),
        verbose=state.get("verbose", False),
        group_by=state.get("group_by", "rule"),
    )

    output_format = state["output_format"]

    # Render
    if output_format == "console":
        formatter = ConsoleFormatter(console)
        formatter.render(result, str(root), options=fmt_opts)
    else:
        if output_format == "json":
            content = format_json(result, str(root), fmt_opts)
        elif output_format == "sarif":
            content = format_sarif(result, str(root), fmt_opts)
        else:
            content = format_github(result, str(root), fmt_opts)

        if state.get("print_to_screen", True):
            console.print(content)

        if state.get("save_to_file") and state.get("output_file"):
            Path(state["output_file"]).write_text(content, encoding="utf-8")
            console.print(f"\n  [{C_OK}]\u2713[/] Saved to [{C_TEAL}]{state['output_file']}[/]")

    # Summary
    if result.error_count > 0:
        console.print(f"\n  [{C_ERR}]Audit completed with {result.error_count} error(s)[/]")
    else:
        console.print(f"\n  [{C_OK}]Audit completed \u2014 no errors[/]")


def _tui_ports(console: Console, session: dict | None = None) -> None:
    """Interactive port allocation table."""
    from composearr.commands.ports import collect_ports, render_port_table
    session = session or {}

    # Path selection (uses session memory)
    path = _resolve_path(console, session)
    if path is None:
        return

    # Display options
    view_mode = inquirer.select(
        message="What to show?",
        choices=[
            Choice(value="all", name="All port mappings"),
            Choice(value="conflicts", name="Conflicts only"),
            *_nav_choices(),
        ],
        default="all",
    ).execute()

    nav = _check_nav(view_mode)
    if nav:
        return

    root = Path(path).resolve()
    all_ports = collect_ports(root)
    render_port_table(
        all_ports, root, console,
        show_conflicts_only=(view_mode == "conflicts"),
    )


def _tui_rules(console: Console) -> None:
    """Display rules in the TUI."""
    from rich.table import Table
    from rich import box
    from rich.style import Style

    all_rules = get_all_rules()
    sev_colors = {
        Severity.ERROR: C_ERR,
        Severity.WARNING: C_WARN,
        Severity.INFO: C_INFO,
    }

    table = Table(
        box=box.SIMPLE_HEAD,
        border_style=Style(color="#27272a"),
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


def _tui_fix(console: Console, session: dict | None = None) -> None:
    """Interactive fix flow — scan, review fixable issues, apply selected fixes."""
    session = session or {}

    # Step 1: Path selection (uses session memory)
    path = _resolve_path(console, session)
    if path is None:
        return

    # Step 2: Fix scope
    fix_scope = inquirer.select(
        message="Which fixes to review?",
        choices=[
            Choice(value="all", name="All fixable issues"),
            Choice(value="rule", name="Filter by rule"),
            *_nav_choices(),
        ],
        default="all",
    ).execute()

    nav = _check_nav(fix_scope)
    if nav:
        return

    rule_filter: set[str] | None = None
    if fix_scope == "rule":
        all_rules = get_all_rules()
        rule_choices = [
            Choice(value=r.id, name=f"{r.id} \u2014 {r.name}", enabled=True)
            for r in sorted(all_rules, key=lambda x: x.id)
        ]
        selected = inquirer.checkbox(
            message="Select rules (space to toggle):",
            choices=rule_choices,
        ).execute()
        if selected:
            rule_filter = set(selected)

    # Step 3: Dry run or apply
    apply_mode = inquirer.select(
        message="Fix mode:",
        choices=[
            Choice(value="review", name="Review fixes (show what would change)"),
            Choice(value="apply", name="Apply fixes to files"),
            *_nav_choices(),
        ],
        default="review",
    ).execute()

    nav = _check_nav(apply_mode)
    if nav:
        return

    # Step 4: Backup preference (only when applying)
    create_backup = False
    if apply_mode == "apply":
        backup = inquirer.select(
            message="Create backups before modifying files?",
            choices=[
                Choice(value="yes", name="Yes \u2014 save .bak files"),
                Choice(value="no", name="No \u2014 modify in place"),
                *_nav_choices(),
            ],
            default="yes",
        ).execute()

        nav = _check_nav(backup)
        if nav:
            return
        create_backup = backup == "yes"

    # Run the scan
    root = Path(path).resolve()
    console.print()

    reporter = RichProgressReporter(console)
    result = run_audit(root, progress=reporter)
    console.print()

    # Collect fixable issues
    fixable = [i for i in result.all_issues if i.fix_available and i.suggested_fix]
    if rule_filter:
        fixable = [i for i in fixable if i.rule_id in rule_filter]

    if not fixable:
        console.print(f"  [{C_OK}]\u2713[/] [{C_TEXT}]No fixable issues found[/]")
        return

    console.print(f"  [{C_TEXT}]Found[/] [bold {C_TEAL}]{len(fixable)}[/] [{C_TEXT}]fixable issues[/]")
    console.print()

    # Group by file for display
    from collections import defaultdict
    by_file: dict[str, list] = defaultdict(list)
    for issue in fixable:
        by_file[issue.file_path].append(issue)

    sev_colors = {
        Severity.ERROR: C_ERR,
        Severity.WARNING: C_WARN,
        Severity.INFO: C_INFO,
    }

    for file_path in sorted(by_file.keys()):
        try:
            rel = str(Path(file_path).relative_to(root))
        except ValueError:
            rel = file_path
        console.print(f"  [{C_TEXT}]{rel}[/]")
        for issue in by_file[file_path]:
            color = sev_colors.get(issue.severity, C_MUTED)
            svc = f" [bold {C_TEAL}]{issue.service}[/]" if issue.service else ""
            console.print(f"    [{color}]\u25cf[/] [{color}]{issue.rule_id}[/]  {issue.message}{svc}")
            # Show fix preview (first line only in compact view)
            fix_preview = issue.suggested_fix.split("\n")[0]
            console.print(f"      [{C_OK}]\u2192[/] [{C_TEAL}]{fix_preview}[/]")
        console.print()

    if apply_mode == "review":
        console.print(f"  [{C_MUTED}]Review complete \u2014 no files modified[/]")
        console.print(f"  [{C_MUTED}]Run again with 'Apply fixes' to modify files[/]")
        return

    # Confirm before applying
    confirm = inquirer.confirm(
        message=f"Apply {len(fixable)} fixes to {len(by_file)} files?",
        default=False,
    ).execute()

    if not confirm:
        console.print(f"\n  [{C_MUTED}]Cancelled \u2014 no files modified[/]")
        return

    # Apply fixes
    from composearr.fixer import apply_fixes
    applied, skipped, errors = apply_fixes(fixable, root, backup=create_backup)

    console.print()
    if applied:
        console.print(f"  [{C_OK}]\u2713[/] [{C_TEXT}]Applied {applied} fixes[/]")
    if skipped:
        console.print(f"  [{C_WARN}]\u26a0[/] [{C_TEXT}]{skipped} fixes skipped (not auto-applicable)[/]")
    if errors:
        console.print(f"  [{C_ERR}]\u2716[/] [{C_TEXT}]{errors} fixes failed[/]")
    if create_backup and applied:
        console.print(f"  [{C_MUTED}]Backup files saved with .bak extension[/]")


def _tui_explain(console: Console) -> None:
    """Interactive explain — pick a rule and show documentation."""
    all_rules = sorted(get_all_rules(), key=lambda r: r.id)

    choices = [
        Choice(value=r.id, name=f"{r.id}  {r.name} — {r.description}")
        for r in all_rules
    ]
    choices.extend(_nav_choices())

    rule_id = inquirer.select(
        message="Which rule to explain?",
        choices=choices,
    ).execute()

    nav = _check_nav(rule_id)
    if nav:
        return

    from composearr.commands.explain import render_explanation
    render_explanation(rule_id, console)


def _tui_config(console: Console, session: dict) -> None:
    """Interactive config view/validate."""
    action = inquirer.select(
        message="Config action:",
        choices=[
            Choice(value="show", name="Show effective configuration"),
            Choice(value="validate", name="Validate config files"),
            *_nav_choices(),
        ],
        default="show",
    ).execute()

    nav = _check_nav(action)
    if nav:
        return

    # Resolve path for project config
    path_str = _resolve_path(console, session)
    if path_str is None:
        return
    project_path = Path(path_str).resolve()

    if action == "validate":
        from composearr.commands.config_cmd import validate_config_data
        from ruamel.yaml import YAML

        yaml = YAML()
        config_files: list[Path] = []
        user_config = Path.home() / ".composearr.yml"
        if user_config.is_file():
            config_files.append(user_config)
        for name in [".composearr.yml", ".composearr.yaml"]:
            p = project_path / name
            if p.is_file():
                config_files.append(p)
                break

        if not config_files:
            console.print(f"\n  [{C_MUTED}]No .composearr.yml found. Using defaults.[/]")
            return

        for cf in config_files:
            try:
                data = yaml.load(cf)
                if isinstance(data, dict):
                    issues = validate_config_data(data)
                    if issues:
                        console.print(f"\n  [{C_WARN}]\u26a0[/] [{C_TEXT}]{cf}:[/]")
                        for issue in issues:
                            console.print(f"    [{C_ERR}]\u2022[/] [{C_TEXT}]{issue}[/]")
                    else:
                        console.print(f"\n  [{C_OK}]\u2713[/] [{C_TEXT}]{cf}[/] [{C_OK}]valid[/]")
                else:
                    console.print(f"\n  [{C_WARN}]\u26a0[/] [{C_TEXT}]{cf} is empty[/]")
            except Exception as e:
                console.print(f"\n  [{C_ERR}]\u2716[/] [{C_TEXT}]{cf}:[/] [{C_ERR}]{e}[/]")

    else:
        from composearr.commands.config_cmd import render_effective_config
        from composearr.config import load_config
        effective = load_config(project_path)
        render_effective_config(effective, console, project_path)
