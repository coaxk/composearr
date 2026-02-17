"""Interactive TUI menu for ComposeArr."""

from __future__ import annotations

import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path

from InquirerPy import inquirer
from InquirerPy.base.control import Choice
from rich.console import Console
from rich.rule import Rule
from rich.text import Text

from composearr import __version__
from composearr.engine import run_audit
from composearr.formatters.console import ConsoleFormatter, make_console
from composearr.formatters.github_formatter import format_github
from composearr.formatters.json_formatter import format_json
from composearr.formatters.progress import RichProgressReporter
from composearr.formatters.sarif_formatter import format_sarif
from composearr.models import FormatOptions, Severity
from composearr.rules.base import get_all_rules

# Color tokens (Beszel-inspired)
C_TEAL = "#2dd4bf"
C_MUTED = "#71717a"
C_OK = "#22c55e"
C_ERR = "#ef4444"
C_WARN = "#f59e0b"
C_TEXT = "#fafafa"
C_INFO = "#3b82f6"
C_DIM = "#52525b"

# Sentinel values
_BACK = "__back__"
_EXIT = "__exit__"





# ── Navigation Helpers ─────────────────────────────────────────


def _nav_choices() -> list[Choice]:
    """Return Back and Exit choices for appending to any menu."""
    return [
        Choice(value=_BACK, name="\u2190  Back"),
        Choice(value=_EXIT, name="\u2716  Exit"),
    ]


def _check_nav(value: str) -> str | None:
    """Return 'back', 'exit', or None for normal values."""
    if value == _EXIT:
        return "exit"
    if value == _BACK:
        return "back"
    return None


def _section_header(console: Console, title: str, subtitle: str | None = None) -> None:
    """Print a visual section divider with title."""
    console.print()
    console.print(Rule(f"[bold {C_TEAL}]{title}[/]", style=C_DIM))
    if subtitle:
        console.print(f"  [{C_MUTED}]{subtitle}[/]")
    console.print()


def _print_rules_quick_ref(console: Console) -> None:
    """Print a compact rule reference table."""
    from composearr.config import DEFAULT_RULES, _RULE_NAME_TO_ID

    _id_to_name = {v: k for k, v in _RULE_NAME_TO_ID.items()}
    _rule_short = {
        "CA001": ":latest tag usage",
        "CA003": "Untrusted registries",
        "CA101": "Inline secrets",
        "CA201": "Missing healthchecks",
        "CA202": "Fake healthchecks",
        "CA203": "Missing restart policy",
        "CA301": "Port conflicts",
        "CA302": "Unreachable dependencies",
        "CA303": "Isolated service ports",
        "CA401": "PUID/PGID mismatch",
        "CA402": "Umask inconsistency",
        "CA403": "Missing timezone (TZ)",
        "CA404": "Duplicate env variables",
        "CA501": "Missing memory limit",
        "CA502": "Missing CPU limit",
        "CA503": "Unusual resource limits",
        "CA504": "No logging config",
        "CA505": "No log rotation",
        "CA601": "Hardlink path issues",
        "CA701": "Prefer named volumes",
        "CA702": "Undefined volume ref",
        "CA304": "DNS configuration issues",
        "CA801": "No capability restrictions",
        "CA802": "Privileged mode",
        "CA803": "No read-only root",
        "CA804": "No new privileges",
        "CA901": "Resource requests mismatch",
        "CA902": "Restart always (unlimited)",
        "CA903": "Tmpfs no size limit",
        "CA904": "No user namespace",
    }
    for rule_id in sorted(DEFAULT_RULES.keys()):
        name = _id_to_name.get(rule_id, "")
        desc = _rule_short.get(rule_id, "")
        default = DEFAULT_RULES[rule_id]
        console.print(
            f"    [{C_TEAL}]{rule_id}[/] [{C_MUTED}]({name})[/]"
            f"  [{C_MUTED}]{desc:<28s} default: {default}[/]"
        )


def _pause(console: Console, message: str = "Press Enter to continue...") -> None:
    """Pause for user acknowledgment."""
    try:
        console.input(f"\n  [{C_MUTED}]{message}[/] ")
    except (EOFError, KeyboardInterrupt):
        pass


# ── Path Resolution (session-aware) ───────────────────────────


def _clean_path(path: str) -> str:
    """Clean up path display — remove trailing spaces and dots."""
    return path.rstrip(" .")


def _resolve_path(console: Console, session: dict) -> str | None:
    """Resolve stack path — silently reuses session path if available.

    When the session already has a path, uses it directly (no prompt).
    When no path exists, prompts for auto-detect or manual entry.
    Use _change_path() to explicitly change the remembered path.
    """
    remembered = session.get("path")

    if remembered:
        # Silently reuse — the path is shown in settings dashboard / confirmed elsewhere
        console.print(f"  [{C_MUTED}]Using:[/] [{C_TEAL}]{_clean_path(remembered)}[/]")
        return remembered

    # First time — need to find the stacks
    return _prompt_for_path(console, session)


def _prompt_for_path(console: Console, session: dict) -> str | None:
    """Prompt user to find their stacks (auto-detect or manual)."""
    path_mode = inquirer.select(
        message="How to find your stacks?",
        choices=[
            Choice(value="auto", name="Auto-detect Docker stacks \u2014 searches common locations like ~/docker, /opt/stacks"),
            Choice(value="manual", name="Enter path manually \u2014 type the full directory path to your compose files"),
            *_nav_choices(),
        ],
        default="auto",
    ).execute()

    nav = _check_nav(path_mode)
    if nav:
        return None

    if path_mode == "auto":
        return _auto_detect_path(console, session)
    else:
        path = inquirer.text(
            message="Stack directory:",
            default=session.get("path") or str(Path.cwd()),
            validate=lambda p: Path(p).is_dir() or "Directory not found",
        ).execute()

    session["path"] = path
    return path


def _auto_detect_path(console: Console, session: dict) -> str | None:
    """Run auto-detection and update session."""
    from composearr.scanner.discovery import detect_all_stack_directories
    from rich.progress import Progress, SpinnerColumn, TextColumn

    console.print(f"  [{C_MUTED}]Looking for Docker Compose stacks\u2026[/]")
    with Progress(
        SpinnerColumn(style=C_TEAL),
        TextColumn(f"[{C_MUTED}]Checking config, common locations, and drives\u2026[/]"),
        console=console,
        transient=False,
    ) as progress:
        progress.add_task("", total=None)
        candidates = detect_all_stack_directories()
    # Clear the spinner line after detection completes
    console.print()

    if not candidates:
        console.print(f"  [{C_WARN}]\u26a0[/] [{C_TEXT}]No Docker stacks found automatically[/]")
        console.print(f"  [{C_MUTED}]Checked: config file, current directory, common locations, and scanned drives[/]")
        console.print(f"  [{C_MUTED}]Tip: set stack_path in ~/.composearr.yml to remember your location[/]")
        console.print()
        path = inquirer.text(
            message="Enter stack directory:",
            default=str(Path.cwd()),
            validate=lambda p: Path(p).is_dir() or "Directory not found",
        ).execute()
        session["path"] = path
        return path

    if len(candidates) == 1:
        # Single result — use it directly
        path = str(candidates[0]["path"])
        count = candidates[0]["compose_count"]
        console.print(f"  [{C_OK}]\u2713[/] [{C_TEXT}]Found stacks at[/] [{C_TEAL}]{path}[/]  [{C_MUTED}]({count} compose files)[/]")
        session["path"] = path
        return path

    # Multiple candidates — let user choose
    source_labels = {"config": "from config", "cwd": "current dir", "common": "common location", "scan": "found by scan"}
    console.print(f"  [{C_OK}]\u2713[/] [{C_TEXT}]Found {len(candidates)} potential stack directories[/]")
    console.print()

    choices = []
    for c in candidates:
        label = source_labels.get(c["source"], c["source"])
        count = c["compose_count"]
        path_str = str(c["path"])
        choices.append(Choice(
            value=path_str,
            name=f"{path_str}  \u2014 {count} compose file{'s' if count != 1 else ''} ({label})",
        ))
    choices.append(Choice(value="__manual__", name="Enter path manually \u2014 none of these are right"))

    selected = inquirer.select(
        message="Which stack directory?",
        choices=choices,
        default=str(candidates[0]["path"]),
        long_instruction="Select your main Docker Compose stack directory",
    ).execute()

    if selected == "__manual__":
        path = inquirer.text(
            message="Enter stack directory:",
            default=str(Path.cwd()),
            validate=lambda p: Path(p).is_dir() or "Directory not found",
        ).execute()
    else:
        path = selected

    session["path"] = path
    return path


def _change_path(console: Console, session: dict) -> str | None:
    """Explicitly change the remembered path."""
    remembered = session.get("path")
    path_mode = inquirer.select(
        message="Change stack directory:",
        choices=[
            Choice(value="auto", name="Re-scan \u2014 auto-detect stacks in common locations"),
            Choice(value="manual", name="Enter path manually \u2014 type the full directory path"),
            *_nav_choices(),
        ],
        default="auto",
    ).execute()

    nav = _check_nav(path_mode)
    if nav:
        return remembered  # Keep current path on back/exit

    if path_mode == "auto":
        # Auto-detect directly — don't re-prompt
        return _auto_detect_path(console, session)
    else:
        path = inquirer.text(
            message="Stack directory:",
            default=remembered or str(Path.cwd()),
            validate=lambda p: Path(p).is_dir() or "Directory not found",
        ).execute()
        session["path"] = path
        return path


def _auto_resolve_path(console: Console, session: dict) -> str | None:
    """Auto-resolve path for quick audit — uses session if available, else detects."""
    remembered = session.get("path")
    if remembered:
        return remembered

    # No remembered path — run full detection with user choice
    return _auto_detect_path(console, session)


# ── First Launch Setup ─────────────────────────────────────────


def _is_first_launch() -> bool:
    """Check if this is the first time ComposeArr has been used."""
    # Check marker file first
    marker = Path.home() / ".composearr" / ".first_run_complete"
    if marker.exists():
        return False

    config_names = [".composearr.yml", ".composearr.yaml"]

    # Check home directory
    for name in config_names:
        if (Path.home() / name).is_file():
            return False

    # Check CWD
    try:
        for name in config_names:
            if (Path.cwd() / name).is_file():
                return False
    except (OSError, PermissionError):
        pass

    # Check stack_path from any config already found
    try:
        from composearr.scanner.discovery import _read_config_stack_path
        stack_path = _read_config_stack_path()
        if stack_path:
            for name in config_names:
                if (stack_path / name).is_file():
                    return False
    except Exception:
        pass

    # Check all common/well-known stack directories for a config file
    try:
        from composearr.scanner.discovery import _build_common_paths
        for common_path in _build_common_paths():
            try:
                if common_path.is_dir():
                    for name in config_names:
                        if (common_path / name).is_file():
                            return False
            except (OSError, PermissionError):
                continue
    except Exception:
        pass

    return True


def _check_first_launch(console: Console, session: dict) -> None:
    """On first launch, run guided setup: scan → pick stack → create config."""
    if not _is_first_launch():
        return

    from composearr.scanner.discovery import detect_all_stack_directories
    from rich.progress import Progress, SpinnerColumn, TextColumn

    console.print(Rule(f"[bold {C_TEAL}]First Launch Setup[/]", style=C_DIM))
    console.print()
    console.print(f"  [{C_TEXT}]Looks like this is your first time running ComposeArr.[/]")
    console.print(f"  [{C_TEXT}]Let\u2019s get you set up \u2014 it only takes a moment.[/]")
    console.print()
    console.print(f"  [{C_MUTED}]Step 1: We\u2019ll scan your system for Docker Compose stacks[/]")
    console.print(f"  [{C_MUTED}]Step 2: You pick your stack directory[/]")
    console.print(f"  [{C_MUTED}]Step 3: We\u2019ll create a config file so you never have to do this again[/]")
    console.print()

    # Step 1: Scan
    console.print(f"  [{C_TEXT}]Scanning for Docker Compose stacks\u2026[/]")
    console.print(f"  [{C_MUTED}]Checking config, current directory, common locations, and drives[/]")
    console.print()

    with Progress(
        SpinnerColumn(style=C_TEAL),
        TextColumn(f"[{C_MUTED}]Scanning\u2026[/]"),
        console=console,
        transient=True,
    ) as progress:
        progress.add_task("", total=None)
        candidates = detect_all_stack_directories()

    if candidates:
        console.print(f"  [{C_OK}]\u2713[/] [{C_TEXT}]Found {len(candidates)} location{'s' if len(candidates) != 1 else ''} with Docker Compose files:[/]")
        console.print()
        for c in candidates:
            count = c["compose_count"]
            console.print(
                f"    [{C_TEAL}]{c['path']}[/]  "
                f"[{C_MUTED}]\u2014 {count} compose file{'s' if count != 1 else ''}[/]"
            )
        console.print()

    # Step 2: Pick stack directory
    if not candidates:
        console.print(f"  [{C_WARN}]\u26a0[/] [{C_TEXT}]No Docker stacks found automatically[/]")
        console.print(f"  [{C_MUTED}]That\u2019s okay \u2014 just tell us where your compose files live.[/]")
        console.print()
        stack_path = inquirer.text(
            message="Where are your Docker Compose files?",
            default=str(Path.cwd()),
            validate=lambda p: Path(p).is_dir() or "Directory not found",
        ).execute()
    elif len(candidates) == 1:
        stack_path = str(candidates[0]["path"])
        confirm = inquirer.select(
            message=f"Use {stack_path} as your stack directory?",
            choices=[
                Choice(value="yes", name=f"\u2713 Yes \u2014 use {stack_path}"),
                Choice(value="other", name="Enter a different path"),
            ],
            default="yes",
        ).execute()
        if confirm == "other":
            stack_path = inquirer.text(
                message="Stack directory:",
                default=str(Path.cwd()),
                validate=lambda p: Path(p).is_dir() or "Directory not found",
            ).execute()
    else:
        # Multiple candidates — let user choose
        choices = []
        for c in candidates:
            count = c["compose_count"]
            path_str = str(c["path"])
            choices.append(Choice(
                value=path_str,
                name=f"{path_str}  \u2014 {count} compose file{'s' if count != 1 else ''}",
            ))
        choices.append(Choice(value="__manual__", name="Enter path manually \u2014 none of these"))

        stack_path = inquirer.select(
            message="Which is your main stack directory?",
            choices=choices,
            default=str(candidates[0]["path"]),
        ).execute()

        if stack_path == "__manual__":
            stack_path = inquirer.text(
                message="Stack directory:",
                default=str(Path.cwd()),
                validate=lambda p: Path(p).is_dir() or "Directory not found",
            ).execute()

    session["path"] = stack_path
    project_path = Path(stack_path).resolve()

    # Quick preview of what we found
    from composearr.scanner.discovery import discover_compose_files
    paths, managed = discover_compose_files(project_path)
    total_services = 0
    for p in paths:
        try:
            from ruamel.yaml import YAML
            yaml = YAML()
            data = yaml.load(p.read_text(encoding="utf-8"))
            if data and "services" in data and isinstance(data["services"], dict):
                total_services += len(data["services"])
        except Exception:
            pass

    console.print()
    console.print(f"  [{C_OK}]\u2713[/] [{C_TEXT}]Stack directory:[/] [{C_TEAL}]{project_path}[/]")
    console.print(f"    [{C_MUTED}]{len(paths)} compose files, {total_services} services[/]")
    if managed:
        for platform, skipped in managed.items():
            console.print(f"    [{C_MUTED}]{len(skipped)} managed by {platform} (will be skipped)[/]")
    console.print()

    # Step 3: Config creation
    console.print(Rule(f"[bold {C_TEAL}]Create Your Config[/]", style=C_DIM))
    console.print()
    console.print(f"  [{C_TEXT}]A .composearr.yml config saves your preferences so ComposeArr[/]")
    console.print(f"  [{C_TEXT}]remembers your stack location and settings on every launch.[/]")
    console.print()

    create_config = inquirer.select(
        message="Create a config file now?",
        choices=[
            Choice(value="yes", name="\u2713 Yes \u2014 set up my config (takes 30 seconds)"),
            Choice(value="skip", name="\u2192 Skip for now \u2014 I\u2019ll use defaults"),
        ],
        default="yes",
    ).execute()

    if create_config == "yes":
        _tui_create_config(console, project_path)
    else:
        console.print()
        console.print(f"  [{C_MUTED}]No worries \u2014 using defaults.[/]")
        console.print(f"  [{C_MUTED}]You can always create a config later from the Config menu.[/]")
        console.print(f"  [{C_MUTED}]Tip: your stack path will be remembered for this session.[/]")

    console.print()
    console.print(Rule(f"[bold {C_TEAL}]Ready to Go[/]", style=C_DIM))
    console.print()
    console.print(f"  [{C_TEXT}]Setup complete! Choose an action below to get started.[/]")
    console.print(f"  [{C_MUTED}]Tip: 'Scan Stack' is the fastest way to see how your stack looks.[/]")
    console.print()

    # Write first-run marker so wizard doesn't show again
    try:
        marker = Path.home() / ".composearr" / ".first_run_complete"
        marker.parent.mkdir(parents=True, exist_ok=True)
        marker.touch()
    except OSError:
        pass


def _verify_config_on_startup(console: Console) -> None:
    """Validate any existing .composearr.yml on startup and warn about issues."""
    from composearr.commands.config_cmd import validate_config_data
    from ruamel.yaml import YAML

    yaml = YAML()
    config_files: list[Path] = []
    seen_paths: set[str] = set()

    def _add_config(p: Path) -> None:
        resolved = str(p.resolve()).lower()
        if resolved not in seen_paths and p.is_file():
            seen_paths.add(resolved)
            config_files.append(p)

    user_config = Path.home() / ".composearr.yml"
    _add_config(user_config)

    # Also check CWD for project config
    try:
        for name in [".composearr.yml", ".composearr.yaml"]:
            _add_config(Path.cwd() / name)
    except (OSError, PermissionError):
        pass

    # Also check the stack directory if referenced by user config
    try:
        from composearr.scanner.discovery import _read_config_stack_path
        stack_path = _read_config_stack_path()
        if stack_path:
            for name in [".composearr.yml", ".composearr.yaml"]:
                _add_config(stack_path / name)
    except Exception:
        pass

    if not config_files:
        return  # No config to verify

    all_ok = True
    for cf in config_files:
        try:
            data = yaml.load(cf)
            if isinstance(data, dict):
                issues = validate_config_data(data)
                if issues:
                    all_ok = False
                    console.print(f"  [{C_WARN}]\u26a0[/] [{C_TEXT}]Config issue in[/] [{C_TEAL}]{cf}[/][{C_TEXT}]:[/]")
                    for issue in issues:
                        console.print(f"    [{C_ERR}]\u2022[/] [{C_TEXT}]{issue}[/]")
                    console.print(f"    [{C_MUTED}]Run Config \u2192 Validate for details, or edit the file directly.[/]")
                    console.print()
            elif data is None:
                # Empty config file — not an error, just using defaults
                pass
            else:
                all_ok = False
                console.print(f"  [{C_WARN}]\u26a0[/] [{C_TEXT}]{cf} has invalid format (expected YAML mapping)[/]")
                console.print()
        except Exception as e:
            all_ok = False
            console.print(f"  [{C_ERR}]\u2716[/] [{C_TEXT}]Error reading {cf}:[/] [{C_ERR}]{e}[/]")
            console.print()

    if all_ok and config_files:
        sources = ", ".join(str(cf) for cf in config_files)
        console.print(f"  [{C_OK}]\u2713[/] [{C_MUTED}]Config loaded: {sources}[/]")
        console.print()


# ── Main TUI Entry Point ──────────────────────────────────────


def launch_tui() -> None:
    """Launch interactive TUI menu."""
    console = make_console()
    session: dict = {}

    # Clean professional header
    console.print()
    console.print(f"  [bold {C_TEAL}]ComposeArr[/] [{C_MUTED}]v{__version__}[/]")
    console.print(f"  [{C_MUTED}]Grammarly for Docker Compose[/]")
    console.print(f"  [{C_MUTED}]Catch configuration mistakes before they cause incidents.[/]")
    console.print()

    # ── First Launch Detection ────────────────────────────────
    _check_first_launch(console, session)

    # ── Config Verification on Startup ────────────────────────
    _verify_config_on_startup(console)

    while True:
        console.print(f"  [{C_MUTED}]Scan Stack      \u2014 Quick or custom audit with options[/]")
        console.print(f"  [{C_MUTED}]Fix Issues      \u2014 Auto-fix problems (creates backups first)[/]")
        console.print(f"  [{C_MUTED}]History         \u2014 View past audit scores, trends, and progress[/]")
        console.print(f"  [{C_MUTED}]Analysis Tools  \u2014 Freshness, ports, runtime diff, orphaned resources[/]")
        console.print(f"  [{C_MUTED}]Rules & Help    \u2014 Browse lint rules and command reference[/]")
        console.print(f"  [{C_MUTED}]Settings        \u2014 Config, secrets, batch fix, change path[/]")
        console.print()

        action = inquirer.select(
            message="What would you like to do?",
            choices=[
                Choice(value="scan", name="\U0001f50d Scan Stack"),
                Choice(value="fix", name="\U0001f527 Fix Issues"),
                Choice(value="history", name="\U0001f4ca History & Reports"),
                Choice(value="tools", name="\U0001f6e0  Analysis Tools"),
                Choice(value="rules_help", name="\U0001f4da Rules & Help"),
                Choice(value="settings", name="\u2699  Settings"),
                Choice(value=_EXIT, name="\u2716  Exit"),
            ],
            default="scan",
        ).execute()

        if action == _EXIT:
            console.print()
            console.print(f"  [{C_MUTED}]Thanks for using ComposeArr![/]")
            console.print()
            break
        elif action == "scan":
            _tui_scan_stack(console, session)
        elif action == "fix":
            _tui_fix(console, session)
        elif action == "history":
            _tui_history(console, session)
        elif action == "tools":
            _tui_analysis_tools(console, session)
        elif action == "rules_help":
            _tui_rules_help(console)
        elif action == "settings":
            _tui_settings(console, session)


# ── Scan Stack (merged Quick + Custom) ────────────────────────


def _tui_scan_stack(console: Console, session: dict) -> None:
    """Combined scan menu — quick or custom audit."""
    _section_header(console, "Scan Stack", "Run an audit on your Docker Compose files")

    scan_mode = inquirer.select(
        message="Scan mode:",
        choices=[
            Choice(value="quick", name="\u26a1 Quick Scan \u2014 recommended defaults"),
            Choice(value="custom", name="\u2699  Custom Scan \u2014 choose rules, severity, format"),
            *_nav_choices(),
        ],
        default="quick",
    ).execute()

    if _check_nav(scan_mode):
        return

    if scan_mode == "quick":
        _tui_quick_audit(console, session)
    else:
        _tui_custom_audit(console, session)


# ── Analysis Tools Submenu ────────────────────────────────────


def _tui_analysis_tools(console: Console, session: dict) -> None:
    """Analysis tools submenu."""
    while True:
        _section_header(console, "Analysis Tools")

        tool = inquirer.select(
            message="Choose a tool:",
            choices=[
                Choice(value="freshness", name="\U0001f4e6 Image Freshness \u2014 check for newer versions"),
                Choice(value="runtime", name="\U0001f504 Runtime vs Compose \u2014 compare running state"),
                Choice(value="ports", name="\U0001f4cb Port Allocation \u2014 mappings and conflicts"),
                Choice(value="orphaned", name="\U0001f5d1  Orphaned Resources \u2014 unused volumes/networks"),
                Choice(value="watch", name="\U0001f441  Watch Mode \u2014 monitor and re-audit on changes"),
                Choice(value="topology", name="\U0001f310 Network Topology \u2014 service connectivity"),
                *_nav_choices(),
            ],
        ).execute()

        if _check_nav(tool):
            return

        if tool == "freshness":
            _tui_freshness(console, session)
        elif tool == "runtime":
            _tui_runtime(console, session)
        elif tool == "ports":
            _tui_ports(console, session)
        elif tool == "orphaned":
            _tui_orphanage(console, session)
        elif tool == "watch":
            _tui_watch(console, session)
        elif tool == "topology":
            _tui_topology(console, session)


# ── Rules & Help Submenu ──────────────────────────────────────


def _tui_rules_help(console: Console) -> None:
    """Rules and help submenu."""
    while True:
        _section_header(console, "Rules & Help")

        choice = inquirer.select(
            message="Choose:",
            choices=[
                Choice(value="rules", name="\U0001f4d6 Browse Rules \u2014 all 30 lint rules with explanations"),
                Choice(value="help", name="\u2753 Command Reference \u2014 CLI and TUI commands"),
                *_nav_choices(),
            ],
        ).execute()

        if _check_nav(choice):
            return

        if choice == "rules":
            _tui_rules_and_explain(console)
        elif choice == "help":
            _tui_help(console)


# ── Settings Submenu ──────────────────────────────────────────


def _tui_settings(console: Console, session: dict) -> None:
    """Settings submenu."""
    while True:
        _section_header(console, "Settings")

        choice = inquirer.select(
            message="Choose:",
            choices=[
                Choice(value="config", name="\u2699  Configuration \u2014 customize rules, paths, and registries"),
                Choice(value="secrets", name="\U0001f512 Secure Secrets \u2014 move secrets to .env files"),
                Choice(value="batch", name="\u26a1 Batch Fix \u2014 CI/CD friendly auto-fix"),
                Choice(value="path", name="\U0001f4c2 Change Stack Path"),
                *_nav_choices(),
            ],
        ).execute()

        if _check_nav(choice):
            return

        if choice == "config":
            _tui_config(console, session)
        elif choice == "secrets":
            _tui_secure_secrets(console, session)
        elif choice == "batch":
            _tui_batch(console, session)
        elif choice == "path":
            _change_path(console, session)


# ── Help ──────────────────────────────────────────────────────


def _tui_help(console: Console) -> None:
    """Show command reference in TUI."""
    from rich.panel import Panel
    from rich.table import Table

    _section_header(console, "Command Reference", "All available CLI and TUI commands")

    sections = {
        "Core Commands": [
            ("composearr", "Launch interactive TUI (this menu)"),
            ("composearr audit [PATH]", "Analyze compose files for issues"),
            ("composearr fix [PATH]", "Auto-fix detected issues (creates backups)"),
        ],
        "Analysis Commands": [
            ("composearr ports [PATH]", "Show port allocation table and conflicts"),
            ("composearr topology [PATH]", "Display network topology"),
            ("composearr history [PATH]", "View audit history and score trends"),
            ("composearr freshness [PATH]", "Check for newer image versions"),
            ("composearr orphanage", "Find orphaned Docker resources"),
            ("composearr runtime [PATH]", "Compare compose vs running containers"),
        ],
        "Utility Commands": [
            ("composearr watch [PATH]", "Monitor files and re-audit on changes"),
            ("composearr init [TEMPLATE]", "Generate compose file from template"),
            ("composearr batch --fix --yes", "Batch operations for CI/CD"),
            ("composearr config", "Interactive configuration wizard"),
        ],
        "Reference Commands": [
            ("composearr rules", "List all 30 lint rules"),
            ("composearr explain <RULE>", "Explain a specific rule in detail"),
            ("composearr help [COMMAND]", "Show command reference"),
        ],
    }

    for section_name, commands in sections.items():
        console.print(f"  [bold]{section_name}[/]\n")
        tbl = Table(show_header=False, box=None, padding=(0, 2))
        tbl.add_column("Command", style=C_TEAL, width=32)
        tbl.add_column("Description")
        for cmd, desc in commands:
            tbl.add_row(cmd, desc)
        console.print(tbl)
        console.print()

    console.print(f"  [bold]Common Options[/]\n")
    opts = Table(show_header=False, box=None, padding=(0, 2))
    opts.add_column("Flag", style=C_TEAL, width=32)
    opts.add_column("Description")
    opts.add_row("--severity error|warning|info", "Filter by minimum severity")
    opts.add_row("--format console|json|sarif", "Output format (json/sarif for CI)")
    opts.add_row("--group-by rule|file", "Group issues by rule or file")
    opts.add_row("--verbose", "Show full file context for each issue")
    opts.add_row("--yes", "Skip confirmation prompts")
    opts.add_row("--dry-run", "Preview without applying changes")
    console.print(opts)
    console.print()

    console.print(f"  [{C_MUTED}]Tip: From the CLI, run 'composearr help <command>' for detailed examples[/]")
    console.print()

    try:
        inquirer.select(
            message="",
            choices=[Choice(value=_BACK, name="\u2190 Back to menu")],
            default=_BACK,
        ).execute()
    except (EOFError, KeyboardInterrupt):
        pass


# ── Watch Mode ─────────────────────────────────────────────────


def _tui_watch(console: Console, session: dict) -> None:
    """Launch watch mode from TUI."""
    _section_header(console, "Watch Mode", "Monitor compose files and re-audit on changes")

    path = _auto_resolve_path(console, session)
    if path is None:
        return

    root = Path(path).resolve()

    console.print(f"  [{C_MUTED}]Watch mode will monitor your stack and re-audit whenever[/]")
    console.print(f"  [{C_MUTED}]a compose file is saved. Press Ctrl+C to return to the menu.[/]")
    console.print()

    from composearr.watcher import WatchMode

    watcher = WatchMode(root)
    try:
        watcher.start(console)
    except KeyboardInterrupt:
        pass  # Absorb any residual Ctrl+C so it doesn't leak to the menu

    import time
    time.sleep(0.1)  # Let terminal settle after Ctrl+C


# ── Orphanage ─────────────────────────────────────────────────


def _tui_orphanage(console: Console, session: dict) -> None:
    """Find orphaned Docker volumes and networks."""
    _section_header(console, "Orphaned Resources", "Find Docker resources not referenced in compose files")

    console.print(f"  [{C_TEXT}]Compares your Docker volumes and networks against[/]")
    console.print(f"  [{C_TEXT}]what's defined in your compose files — anything not referenced is an orphan.[/]")
    console.print()
    console.print(f"  [{C_MUTED}]Requires: Docker SDK (pip install composearr[docker]) + running Docker daemon[/]")
    console.print(f"  [{C_MUTED}]Supports: Docker Desktop, Docker Engine on Linux, WSL2, Colima, Rancher[/]")
    console.print()

    path = _auto_resolve_path(console, session)
    if path is None:
        return

    root = Path(path).resolve()

    from composearr.orphanage import OrphanageFinder
    from rich import box
    from rich.progress import Progress, SpinnerColumn, TextColumn
    from rich.table import Table

    with Progress(
        SpinnerColumn(style=C_TEAL),
        TextColumn(f"[{C_MUTED}]Connecting to Docker and scanning resources\u2026[/]"),
        console=console,
        transient=True,
    ) as progress:
        progress.add_task("", total=None)
        finder = OrphanageFinder(root)
        report = finder.find_orphans()

    if not report.docker_available:
        console.print(f"  [{C_ERR}]\u2716[/] [{C_TEXT}]Could not connect to Docker[/]")
        console.print()
        # Show the multi-line platform-specific help
        for line in report.error.splitlines():
            console.print(f"  [{C_MUTED}]{line}[/]")
        console.print()
        return

    if not report.has_orphans:
        console.print(f"  [{C_OK}]\u2713[/] [{C_TEXT}]No orphaned resources found![/]")
        console.print(f"  [{C_MUTED}]All {report.total_volumes} volumes and {report.total_networks} networks are referenced.[/]")
        console.print()
        return

    if report.orphaned_volumes:
        table = Table(
            title=f"Orphaned Volumes ({len(report.orphaned_volumes)})",
            box=box.SIMPLE_HEAD,
            border_style="#27272a",
            header_style=C_MUTED,
        )
        table.add_column("NAME", style=f"bold {C_WARN}")
        table.add_column("DRIVER", style=C_MUTED)
        table.add_column("MOUNTPOINT", style=C_MUTED)
        for v in report.orphaned_volumes:
            table.add_row(v.name, v.driver, v.mountpoint)
        console.print(table)
        console.print()

    if report.orphaned_networks:
        table = Table(
            title=f"Orphaned Networks ({len(report.orphaned_networks)})",
            box=box.SIMPLE_HEAD,
            border_style="#27272a",
            header_style=C_MUTED,
        )
        table.add_column("NAME", style=f"bold {C_WARN}")
        table.add_column("ID", style=C_MUTED)
        table.add_column("DRIVER", style=C_MUTED)
        for n in report.orphaned_networks:
            table.add_row(n.name, n.id, n.driver)
        console.print(table)
        console.print()

    console.print(f"  [{C_TEXT}]Total orphans: {report.total_orphans}[/]")
    console.print(f"  [{C_MUTED}]Cleanup: docker volume rm <name> / docker network rm <name>[/]")
    console.print(f"  [{C_MUTED}]ComposeArr never auto-deletes \u2014 you\u2019re in control.[/]")
    console.print()


# ── Runtime Diff ──────────────────────────────────────────────


def _tui_runtime(console: Console, session: dict) -> None:
    """Compare compose definitions against running containers."""
    _section_header(console, "Runtime Diff", "Compare compose files vs running containers")

    console.print(f"  [{C_TEXT}]Runtime Diff compares what your compose files define against[/]")
    console.print(f"  [{C_TEXT}]what Docker is actually running — finds drift, missing services,[/]")
    console.print(f"  [{C_TEXT}]and image mismatches.[/]")
    console.print()
    console.print(f"  [{C_MUTED}]Requires: Docker SDK (pip install composearr[docker]) + running Docker daemon[/]")
    console.print(f"  [{C_MUTED}]Supports: Docker Desktop, Docker Engine on Linux, WSL2, Colima, Rancher[/]")
    console.print()

    path = _auto_resolve_path(console, session)
    if path is None:
        return

    root = Path(path).resolve()

    from composearr.runtime import RuntimeComparator
    from rich import box
    from rich.progress import Progress, SpinnerColumn, TextColumn
    from rich.table import Table

    with Progress(
        SpinnerColumn(style=C_TEAL),
        TextColumn(f"[{C_MUTED}]Connecting to Docker and comparing services\u2026[/]"),
        console=console,
        transient=True,
    ) as progress:
        progress.add_task("", total=None)
        comparator = RuntimeComparator(root)
        report = comparator.compare()

    if not report.docker_available:
        console.print(f"  [{C_ERR}]\u2716[/] [{C_TEXT}]Could not connect to Docker[/]")
        console.print()
        for line in report.error.splitlines():
            console.print(f"  [{C_MUTED}]{line}[/]")
        console.print()
        return

    console.print(f"  [{C_TEXT}]Compose:[/] [{C_TEAL}]{report.compose_services}[/] [{C_TEXT}]services[/]"
                   f"  [{C_MUTED}]|[/]  "
                   f"[{C_TEXT}]Running:[/] [{C_TEAL}]{report.running_services}[/] [{C_TEXT}]containers[/]")
    console.print()

    if not report.has_diffs:
        console.print(f"  [{C_OK}]\u2713[/] [{C_TEXT}]All compose services match running containers![/]")
        console.print()
        return

    sev_styles = {"error": C_ERR, "warning": C_WARN, "info": C_INFO}

    table = Table(
        box=box.SIMPLE_HEAD,
        border_style="#27272a",
        header_style=C_MUTED,
    )
    table.add_column("SERVICE", style=f"bold {C_TEXT}")
    table.add_column("ISSUE")
    table.add_column("EXPECTED", style=C_MUTED)
    table.add_column("ACTUAL", style=C_MUTED)
    table.add_column("SEV", justify="center")

    for d in report.diffs:
        color = sev_styles.get(d.severity, C_MUTED)
        table.add_row(d.service, d.category, d.expected, d.actual, f"[{color}]{d.severity}[/]")

    console.print(table)
    console.print()


# ── History View ───────────────────────────────────────────────


def _tui_history(console: Console, session: dict) -> None:
    """Display audit history and trends."""
    _section_header(console, "Audit History", "Track your stack health over time")

    path = _auto_resolve_path(console, session)
    if path is None:
        return

    root = Path(path).resolve()

    from composearr.history import AuditHistory, make_sparkline

    hist = AuditHistory(root)
    entries = hist.get_recent(limit=20)

    if not entries:
        console.print(f"  [{C_MUTED}]No audit history found for this stack.[/]")
        console.print(f"  [{C_MUTED}]Run a Quick Audit first to start tracking your score![/]")
        console.print()
        return

    from rich.table import Table
    from rich import box
    from rich.style import Style

    grade_colors = {
        "A+": C_OK, "A": C_OK, "A-": C_OK,
        "B+": C_WARN, "B": C_WARN, "B-": C_WARN,
        "C+": C_WARN, "C": C_WARN, "C-": C_WARN,
        "D+": C_ERR, "D": C_ERR, "D-": C_ERR,
        "F": C_ERR,
    }

    table = Table(
        box=box.SIMPLE_HEAD,
        border_style=Style(color="#27272a"),
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

    for entry in entries:
        ts = entry.timestamp[:19].replace("T", " ")
        gc = grade_colors.get(entry.grade, C_TEXT)
        table.add_row(
            ts,
            f"[{gc}]{entry.grade}[/]",
            str(entry.score),
            str(entry.total_issues),
            f"[{C_ERR}]{entry.errors}[/]" if entry.errors else "0",
            f"[{C_WARN}]{entry.warnings}[/]" if entry.warnings else "0",
            str(entry.files_scanned),
            str(entry.services_scanned),
        )

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


# ── Image Freshness ───────────────────────────────────────────


def _tui_freshness(console: Console, session: dict) -> None:
    """Check for newer image versions."""
    _section_header(console, "Image Freshness", "Check for available updates across your stack")

    path = _auto_resolve_path(console, session)
    if path is None:
        return

    root = Path(path).resolve()

    from composearr.registry_client import RegistryClient
    from composearr.scanner.discovery import discover_compose_files
    from composearr.scanner.parser import parse_compose_file

    from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskID

    paths_found, _ = discover_compose_files(root)

    # Count total services to show progress
    all_files = []
    total_images = 0
    for file_path in paths_found:
        cf = parse_compose_file(file_path)
        if cf.parse_error or not cf.services:
            continue
        all_files.append(cf)
        total_images += len(cf.services)

    if not all_files:
        console.print(f"  [{C_MUTED}]No compose files with services found.[/]")
        console.print()
        return

    client = RegistryClient(timeout=10)
    all_results = []

    with Progress(
        SpinnerColumn(style=C_TEAL),
        TextColumn(f"[{C_TEXT}]Querying registries…[/]"),
        BarColumn(complete_style=C_TEAL, finished_style=C_OK),
        TextColumn(f"[{C_MUTED}]{{task.completed}}/{{task.total}} images[/]"),
        console=console,
        transient=True,
    ) as progress:
        task = progress.add_task("Checking", total=total_images)
        for cf in all_files:
            results = client.check_freshness(cf.services, str(cf.path))
            all_results.extend(results)
            progress.advance(task, len(cf.services))

    if not all_results:
        console.print(f"  [{C_MUTED}]No images found to check.[/]")
        console.print()
        return

    from rich.table import Table
    from rich import box
    from rich.style import Style

    table = Table(
        box=box.SIMPLE_HEAD,
        border_style=Style(color="#27272a"),
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
    console.print()


# ── History Saving Helper ──────────────────────────────────────


def _save_audit_history(result, root: Path, console: Console | None = None) -> None:
    """Save audit results to history."""
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
        pass


# ── Quick Audit ────────────────────────────────────────────────


def _tui_quick_audit(console: Console, session: dict) -> None:
    """One-click audit with smart defaults."""
    _section_header(console, "Quick Audit", "Scanning your full stack with recommended settings")

    # Quick audit always uses auto-detected path (reset any custom path)
    session.pop("path", None)
    path = _auto_resolve_path(console, session)
    if path is None:
        return

    root = Path(path).resolve()
    console.print()

    reporter = RichProgressReporter(console)
    result = run_audit(root, progress=reporter)
    console.print()

    # Save to audit history
    _save_audit_history(result, root, console)

    fmt_opts = FormatOptions(
        min_severity=Severity.INFO,
        verbose=False,
        group_by="severity",
        tui_mode=True,
    )

    formatter = ConsoleFormatter(console)
    formatter.render(result, str(root), options=fmt_opts)

    # Post-audit actions
    _post_audit_menu(console, session, result, root)


def _post_audit_menu(console: Console, session: dict, result, root: Path) -> None:
    """After an audit completes, offer next actions."""
    has_fixable = any(i.fix_available for i in result.all_issues)

    # Guidance text
    console.print()
    if has_fixable:
        fixable_count = sum(1 for i in result.all_issues if i.fix_available)
        console.print(f"  [{C_OK}]\u2713 {fixable_count} issues can be auto-fixed![/]")
        console.print(f"  [{C_MUTED}]Select 'Fix issues' below, or run: composearr fix[/]")
    console.print()

    choices = []
    if has_fixable:
        choices.append(Choice(value="fix", name="\U0001f527 Fix issues \u2014 auto-fix problems with backups"))
    choices.extend([
        Choice(value="rerun", name="\u26a1 Re-run with different settings \u2014 change severity, grouping, or rules"),
        Choice(value="export", name="\U0001f4be Export results \u2014 save as JSON, SARIF, or GitHub annotations"),
        Choice(value="ports", name="\U0001f4cb View port allocation \u2014 see all port mappings and conflicts"),
        Choice(value="topo", name="\U0001f310 View network topology \u2014 check service connectivity"),
        Choice(value="menu", name="\u2190  Back to main menu"),
    ])

    action = inquirer.select(
        message="What next?",
        choices=choices,
        default="fix" if has_fixable else "menu",
    ).execute()

    if action == "fix":
        _tui_fix(console, session)
    elif action == "rerun":
        _tui_custom_audit(console, session)
    elif action == "export":
        _export_results(console, result, root)
    elif action == "ports":
        from composearr.commands.ports import collect_ports, render_port_table
        _section_header(console, "Port Allocation", "All port mappings across your stack")
        all_ports = collect_ports(root)
        render_port_table(all_ports, root, console)
    elif action == "topo":
        from composearr.commands.topology import render_topology
        from composearr.scanner.discovery import discover_compose_files
        from composearr.scanner.parser import parse_compose_file
        from rich.progress import Progress, SpinnerColumn, TextColumn
        _section_header(console, "Network Topology", "How your services connect to each other")
        with Progress(
            SpinnerColumn(style=C_TEAL),
            TextColumn(f"[{C_MUTED}]Analyzing network topology\u2026[/]"),
            console=console,
            transient=True,
        ) as progress:
            progress.add_task("", total=None)
            paths, _ = discover_compose_files(root)
            compose_files = [parse_compose_file(p) for p in paths]
            compose_files = [cf for cf in compose_files if not cf.parse_error]
        render_topology(root, console, compose_files=compose_files)


def _export_results(console: Console, result, root: Path) -> None:
    """Export audit results to file."""
    fmt = inquirer.select(
        message="Export format:",
        choices=[
            Choice(value="json", name="JSON \u2014 machine-readable for scripts and dashboards"),
            Choice(value="sarif", name="SARIF \u2014 GitHub Advanced Security and IDE integration"),
            Choice(value="github", name="GitHub Actions \u2014 inline annotations in pull requests"),
            *_nav_choices(),
        ],
        default="json",
    ).execute()

    nav = _check_nav(fmt)
    if nav:
        return

    fmt_opts = FormatOptions(min_severity=Severity.INFO, verbose=False, group_by="rule")

    if fmt == "json":
        content = format_json(result, str(root), fmt_opts)
    elif fmt == "sarif":
        content = format_sarif(result, str(root), fmt_opts)
    else:
        content = format_github(result, str(root), fmt_opts)

    ext_map = {"json": "json", "sarif": "sarif", "github": "txt"}
    ext = ext_map.get(fmt, "txt")
    timestamp = datetime.now().strftime("%Y-%m-%dT%H-%M-%S")
    default_name = f"composearr-audit-{timestamp}.{ext}"

    filename = inquirer.text(
        message="Filename:",
        default=default_name,
    ).execute()

    Path(filename).write_text(content, encoding="utf-8")
    console.print(f"\n  [{C_OK}]\u2713[/] Saved to [{C_TEAL}]{filename}[/]")


# ── Custom Audit (Settings Dashboard) ─────────────────────────


def _tui_custom_audit(console: Console, session: dict) -> None:
    """Custom audit with a settings dashboard — see all options, change what you need."""
    _section_header(console, "Custom Audit", "Configure your audit settings, then run")

    # Default audit settings — use session path but track separately
    settings = {
        "path": session.get("path"),
        "severity": "error",
        "group_by": "rule",
        "format": "console",
        "verbose": False,
        "no_network": False,
        "rule_ids": None,
        "ignore_ids": None,
    }

    # Resolve path first (only if we don't have one)
    if not settings["path"]:
        path = _resolve_path(console, session)
        if path is None:
            return
        settings["path"] = path

    # Settings dashboard loop
    while True:
        console.print()
        # Show current settings
        path_display = _clean_path(settings["path"])
        if len(path_display) > 50:
            path_display = "..." + path_display[-47:]

        rules_display = "all"
        if settings["rule_ids"]:
            rules_display = ", ".join(sorted(settings["rule_ids"]))
        if settings["ignore_ids"]:
            rules_display = f"all except {', '.join(sorted(settings['ignore_ids']))}"

        opts = []
        if settings["verbose"]:
            opts.append("verbose")
        if settings["no_network"]:
            opts.append("no-network")
        opts_display = ", ".join(opts) if opts else "none"

        console.print(f"  [bold {C_TEXT}]Current Audit Settings[/]")
        console.print(f"    [{C_MUTED}]Path:[/]     [{C_TEAL}]{path_display}[/]")
        console.print(f"    [{C_MUTED}]Severity:[/] [{C_TEXT}]{settings['severity']}[/]")
        console.print(f"    [{C_MUTED}]Group by:[/] [{C_TEXT}]{settings['group_by']}[/]")
        console.print(f"    [{C_MUTED}]Format:[/]   [{C_TEXT}]{settings['format']}[/]")
        console.print(f"    [{C_MUTED}]Options:[/]  [{C_TEXT}]{opts_display}[/]")
        console.print(f"    [{C_MUTED}]Rules:[/]    [{C_TEXT}]{rules_display}[/]")
        console.print()

        action = inquirer.select(
            message="Configure or run:",
            choices=[
                Choice(value="run", name="\u25b6 Run audit \u2014 scan now with the settings above"),
                Choice(value="path", name="  Change path \u2014 pick a different directory to scan"),
                Choice(value="severity", name="  Change severity \u2014 filter by error, warning, or info level"),
                Choice(value="group_by", name="  Change grouping \u2014 organize results by rule, file, or severity"),
                Choice(value="format", name="  Change format \u2014 console, JSON, SARIF, or GitHub annotations"),
                Choice(value="options", name="  Toggle options \u2014 verbose output, disable network lookups"),
                Choice(value="rules", name="  Filter rules \u2014 select or exclude specific lint rules"),
                *_nav_choices(),
            ],
            default="run",
        ).execute()

        nav = _check_nav(action)
        if nav:
            return

        if action == "run":
            break

        elif action == "path":
            path = _change_path(console, session)
            if path:
                settings["path"] = path

        elif action == "severity":
            val = inquirer.select(
                message="Minimum severity:",
                choices=[
                    Choice(value="error", name="Error only"),
                    Choice(value="warning", name="Warnings and above"),
                    Choice(value="info", name="Everything (info+)"),
                    *_nav_choices(),
                ],
                default=settings["severity"],
                long_instruction="Error = critical issues only | Warning = best practices | Info = everything including suggestions",
            ).execute()
            nav = _check_nav(val)
            if not nav:
                settings["severity"] = val
                console.print(f"  [{C_OK}]\u2713[/] Severity set to [{C_TEAL}]{val}[/]")

        elif action == "group_by":
            val = inquirer.select(
                message="Group issues by:",
                choices=[
                    Choice(value="rule", name="Rule (default)"),
                    Choice(value="file", name="File"),
                    Choice(value="severity", name="Severity"),
                    *_nav_choices(),
                ],
                default=settings["group_by"],
                long_instruction="By rule = fix one issue type everywhere | By file = fix one service at a time",
            ).execute()
            nav = _check_nav(val)
            if not nav:
                settings["group_by"] = val
                console.print(f"  [{C_OK}]\u2713[/] Grouping set to [{C_TEAL}]{val}[/]")

        elif action == "format":
            val = inquirer.select(
                message="Output format:",
                choices=[
                    Choice(value="console", name="Console (rich terminal output)"),
                    Choice(value="json", name="JSON (machine-readable)"),
                    Choice(value="sarif", name="SARIF (GitHub Advanced Security)"),
                    Choice(value="github", name="GitHub Actions annotations"),
                    *_nav_choices(),
                ],
                default=settings["format"],
                long_instruction="Console = terminal display | JSON/SARIF = for CI/CD and IDE integration",
            ).execute()
            nav = _check_nav(val)
            if not nav:
                settings["format"] = val
                console.print(f"  [{C_OK}]\u2713[/] Format set to [{C_TEAL}]{val}[/]")

        elif action == "options":
            selected = inquirer.checkbox(
                message="Toggle options (space to toggle, enter to confirm):",
                choices=[
                    Choice(value="verbose", name="Verbose \u2014 show full file context for each issue", enabled=settings["verbose"]),
                    Choice(value="no_network", name="No network \u2014 skip tag lookups (work offline)", enabled=settings["no_network"]),
                ],
                long_instruction="Disable network to work offline | Verbose shows surrounding YAML for each issue",
            ).execute()
            settings["verbose"] = "verbose" in selected
            settings["no_network"] = "no_network" in selected
            console.print(f"  [{C_OK}]\u2713[/] Options updated")

        elif action == "rules":
            filter_mode = inquirer.select(
                message="Rule filter:",
                choices=[
                    Choice(value="all", name="All rules \u2014 run every available check"),
                    Choice(value="select", name="Select specific rules \u2014 only run the rules you pick"),
                    Choice(value="exclude", name="Exclude specific rules \u2014 skip rules you don't want"),
                    *_nav_choices(),
                ],
                default="all",
            ).execute()

            nav = _check_nav(filter_mode)
            if nav:
                continue

            all_rules = get_all_rules()
            if filter_mode == "select":
                rule_choices = [
                    Choice(value=r.id, name=f"{r.id} \u2014 {r.name}", enabled=True)
                    for r in sorted(all_rules, key=lambda x: x.id)
                ]
                selected = inquirer.checkbox(
                    message="Select rules (space to toggle):",
                    choices=rule_choices,
                ).execute()
                settings["rule_ids"] = set(selected) if selected else None
                settings["ignore_ids"] = None
            elif filter_mode == "exclude":
                rule_choices = [
                    Choice(value=r.id, name=f"{r.id} \u2014 {r.name}", enabled=False)
                    for r in sorted(all_rules, key=lambda x: x.id)
                ]
                excluded = inquirer.checkbox(
                    message="Select rules to skip (space to toggle):",
                    choices=rule_choices,
                ).execute()
                settings["ignore_ids"] = set(excluded) if excluded else None
                settings["rule_ids"] = None
            else:
                settings["rule_ids"] = None
                settings["ignore_ids"] = None

    # Run the audit with collected settings
    _run_audit_with_settings(console, session, settings)


def _run_audit_with_settings(console: Console, session: dict, settings: dict) -> None:
    """Execute audit with the given settings dict."""
    from composearr.rules.CA0xx_images import set_network_enabled
    set_network_enabled(not settings.get("no_network", False))

    root = Path(settings["path"]).resolve()
    console.print()

    reporter = RichProgressReporter(console)
    result = run_audit(root, progress=reporter)
    console.print()

    # Save to audit history
    _save_audit_history(result, root, console)

    # Apply rule filters
    rule_ids = settings.get("rule_ids")
    ignore_ids = settings.get("ignore_ids")

    if rule_ids:
        result.issues = [i for i in result.issues if i.rule_id in rule_ids]
        result.cross_file_issues = [i for i in result.cross_file_issues if i.rule_id in rule_ids]
    if ignore_ids:
        result.issues = [i for i in result.issues if i.rule_id not in ignore_ids]
        result.cross_file_issues = [i for i in result.cross_file_issues if i.rule_id not in ignore_ids]

    fmt_opts = FormatOptions(
        min_severity=Severity(settings["severity"]),
        verbose=settings.get("verbose", False),
        group_by=settings.get("group_by", "rule"),
        tui_mode=True,
    )

    output_format = settings["format"]

    if output_format == "console":
        formatter = ConsoleFormatter(console)
        formatter.render(result, str(root), options=fmt_opts)
        _post_audit_menu(console, session, result, root)
    else:
        if output_format == "json":
            content = format_json(result, str(root), fmt_opts)
        elif output_format == "sarif":
            content = format_sarif(result, str(root), fmt_opts)
        else:
            content = format_github(result, str(root), fmt_opts)

        # For non-console: save to file
        ext_map = {"json": "json", "sarif": "sarif", "github": "txt"}
        ext = ext_map.get(output_format, "txt")
        timestamp = datetime.now().strftime("%Y-%m-%dT%H-%M-%S")
        default_name = f"composearr-audit-{timestamp}.{ext}"

        dest = inquirer.select(
            message="Output destination:",
            choices=[
                Choice(value="both", name="Save to file AND print to screen \u2014 best of both worlds"),
                Choice(value="file", name="Save to file only \u2014 for CI/CD pipelines and scripts"),
                Choice(value="screen", name="Print to screen only \u2014 quick review without saving"),
            ],
            default="both",
        ).execute()

        if dest in ("both", "screen"):
            console.print(content)

        if dest in ("both", "file"):
            filename = inquirer.text(
                message="Filename:",
                default=default_name,
            ).execute()
            Path(filename).write_text(content, encoding="utf-8")
            console.print(f"\n  [{C_OK}]\u2713[/] Saved to [{C_TEAL}]{filename}[/]")

    # Reset session path after custom audit to prevent state leaking
    session.pop("path", None)


# ── Fix Explanations ──────────────────────────────────────────

_FIX_EXPLANATIONS = {
    "CA001": (
        "Pin :latest tags",
        "Looks up the image registry for the latest stable version and pins to that exact tag.\n"
        "    This prevents unexpected breaking changes when images are updated upstream.",
    ),
    "CA203": (
        "Add restart policy",
        "Adds restart: unless-stopped to services without a restart policy.\n"
        "    This ensures containers restart after crashes or host reboots, but stay stopped if you\n"
        "    manually stop them. This is the recommended policy for most homelab services.",
    ),
    "CA403": (
        "Add timezone (TZ)",
        "Detects the correct timezone in this order:\n"
        "    1. Matches other services in the same compose file (keeps your stack consistent)\n"
        "    2. Uses your system timezone if detectable\n"
        "    3. Falls back to Etc/UTC if nothing else is found\n"
        "    Consistent timezones ensure logs, schedules, and cron jobs all align.",
    ),
}


def _explain_fix_logic(console: Console, rule_ids: set[str]) -> None:
    """Print explanation of how each fix type decides what value to use."""
    explanations = [(rid, _FIX_EXPLANATIONS[rid]) for rid in sorted(rule_ids) if rid in _FIX_EXPLANATIONS]
    if not explanations:
        return

    console.print(f"  [bold {C_TEXT}]How these fixes work:[/]")
    console.print()
    for rule_id, (title, detail) in explanations:
        console.print(f"    [{C_TEAL}]{rule_id}[/] [{C_TEXT}]{title}[/]")
        for line in detail.split("\n"):
            console.print(f"    [{C_MUTED}]{line}[/]")
        console.print()


# ── Fix Summary ────────────────────────────────────────────────


def _show_fix_summary(
    console: Console,
    fix_result,
    root: Path,
    *,
    skipped_files: list[str] | None = None,
) -> None:
    """Show a clean, non-duplicated summary after fix process completes."""
    from rich.panel import Panel

    stack_display = str(root).rstrip(" .")

    summary_parts = []
    summary_parts.append(f"[bold]Stack:[/] [cyan]{stack_display}[/]\n")

    # Files modified (from verified_files — deduplicated source of truth)
    if fix_result.verified_files:
        summary_parts.append(f"[bold]Files Modified:[/] {len(fix_result.verified_files)}")
        for vf in fix_result.verified_files:
            try:
                rel = vf.relative_to(root)
            except ValueError:
                rel = vf
            summary_parts.append(f"  [{C_OK}]\u2713[/] [{C_TEAL}]{rel}[/]  [{C_MUTED}]valid YAML[/]")
        summary_parts.append("")

    # Verification errors
    if fix_result.verification_errors:
        summary_parts.append(f"[bold {C_ERR}]Verification Errors:[/]")
        for vf, err_msg in fix_result.verification_errors:
            try:
                rel = vf.relative_to(root)
            except ValueError:
                rel = vf
            summary_parts.append(f"  [{C_ERR}]\u2716[/] [{C_TEAL}]{rel}[/] [{C_ERR}]{err_msg}[/]")
            summary_parts.append(f"    [{C_MUTED}]Restore: cp {rel}.bak {rel}[/]")
        summary_parts.append("")

    # Files skipped
    if skipped_files:
        summary_parts.append(f"[bold]Files Skipped:[/] {len(skipped_files)}")
        for sf in skipped_files:
            summary_parts.append(f"  [{C_WARN}]\u2298[/] [{C_MUTED}]{sf}[/]")
        summary_parts.append("")

    # Counts
    count_line = []
    if fix_result.applied:
        count_line.append(f"[{C_OK}]{fix_result.applied} applied[/]")
    if fix_result.skipped:
        count_line.append(f"[{C_WARN}]{fix_result.skipped} skipped[/]")
    if fix_result.errors:
        count_line.append(f"[{C_ERR}]{fix_result.errors} failed[/]")
    if count_line:
        summary_parts.append(f"[bold]Fixes:[/] {'  '.join(count_line)}")
        summary_parts.append("")

    # Backup info
    if fix_result.backup_paths:
        summary_parts.append(f"[dim]Backups: .yaml.bak files in same directories[/]")
        summary_parts.append(f"[dim]To rollback: cp compose.yaml.bak compose.yaml[/]")

    console.print()
    console.print(Panel(
        "\n".join(summary_parts),
        border_style="green",
        padding=(1, 2),
        title="Fix Process Complete",
    ))
    console.print()


# ── Fix Issues ─────────────────────────────────────────────────


def _tui_fix(console: Console, session: dict) -> None:
    """Fix flow — scan, review, apply."""
    _section_header(console, "Fix Issues", "Scan for auto-fixable problems and apply fixes")

    path = _resolve_path(console, session)
    if path is None:
        return

    # Run scan
    root = Path(path).resolve()
    console.print()

    reporter = RichProgressReporter(console)
    result = run_audit(root, progress=reporter)
    console.print()

    # Collect fixable issues
    fixable = [i for i in result.all_issues if i.fix_available and i.suggested_fix]

    if not fixable:
        console.print(f"  [{C_OK}]\u2713[/] [{C_TEXT}]No fixable issues found[/]")
        console.print(f"  [{C_MUTED}]All auto-fixable issues are already resolved.[/]")
        return

    # Group by file for display
    by_file: dict[str, list] = defaultdict(list)
    for issue in fixable:
        by_file[issue.file_path].append(issue)
    file_count = len(by_file)

    # Fix process intro panel
    from rich.panel import Panel
    console.print(Panel(
        f"[bold cyan]Fix Process[/]\n\n"
        f"Found [bold]{len(fixable)}[/] auto-fixable issues across [bold]{file_count}[/] file{'s' if file_count != 1 else ''}.\n\n"
        f"[bold]How this works:[/]\n"
        f"  1. Review the issues and proposed fixes below\n"
        f"  2. Choose: Preview diffs, Apply all, or Cancel\n"
        f"  3. In preview mode, approve or skip each file individually\n"
        f"  4. Backups are created automatically (.yaml.bak files)\n\n"
        f"[dim]All changes are reversible — backups are saved in the same directory.[/]",
        border_style="cyan",
        padding=(1, 2),
        title="Fix Issues",
    ))
    console.print()

    # Explain how each fix type decides what to do
    fix_rules = {i.rule_id for i in fixable}
    _explain_fix_logic(console, fix_rules)

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
        console.print(f"  [{C_TEAL}]{rel}[/]")
        for issue in by_file[file_path]:
            color = sev_colors.get(issue.severity, C_MUTED)
            svc = f" [bold {C_TEAL}]{issue.service}[/]" if issue.service else ""
            console.print(f"    [{color}]\u25cf[/] [{color}]{issue.rule_id}[/]  {issue.message}{svc}")
            fix_preview = issue.suggested_fix.split("\n")[0]
            console.print(f"      [{C_OK}]\u2192[/] [{C_TEAL}]{fix_preview}[/]")
        console.print()

    # Explain what happens before applying
    console.print(f"  [{C_TEXT}]What happens when you apply fixes:[/]")
    console.print(f"    [{C_MUTED}]\u2022 Backups created as .yaml.bak (always)[/]")
    console.print(f"    [{C_MUTED}]\u2022 Original compose files are modified[/]")
    console.print(f"    [{C_MUTED}]\u2022 Running containers are NOT affected[/]")
    console.print(f"    [{C_MUTED}]\u2022 Restart with: docker compose up -d[/]")
    console.print(f"    [{C_MUTED}]\u2022 To rollback: copy .bak files over originals[/]")
    console.print()

    # Apply, preview, or cancel?
    action = inquirer.select(
        message="Apply fixes?",
        choices=[
            Choice(value="preview", name="\U0001f441 Preview changes \u2014 see exactly what will change (diff view)"),
            Choice(value="apply", name="\u2713 Apply all fixes \u2014 modify compose files (.yaml.bak backups created automatically)"),
            Choice(value="cancel", name="\u2716  Cancel \u2014 don't modify any files, return to menu"),
        ],
        default="preview",
    ).execute()

    if action == "cancel":
        console.print(f"\n  [{C_MUTED}]No files modified[/]")
        return

    if action == "preview":
        # Show diff previews per-file with approve/skip/cancel
        from composearr.fixer import preview_fixes, apply_fixes
        from composearr.diff import DiffGenerator
        from rich.panel import Panel

        previews = preview_fixes(fixable)
        if not previews:
            console.print(f"\n  [{C_MUTED}]No previewable changes found[/]")
            return

        differ = DiffGenerator()
        approved_files: list[str] = []
        skipped_files: list[str] = []
        cancelled = False
        total_files = len(previews)

        for idx, preview in enumerate(previews, 1):
            try:
                rel = str(preview.file_path.relative_to(root))
            except ValueError:
                rel = str(preview.file_path)

            # Progress header
            console.print()
            console.print(Panel(
                f"[bold]File {idx} of {total_files}[/]\n"
                f"[cyan]{rel}[/]\n"
                f"[dim]{preview.fix_count} fix{'es' if preview.fix_count != 1 else ''} in this file[/]",
                border_style="cyan",
                padding=(0, 1),
            ))
            console.print()

            differ.display_diff(console, preview.original, preview.modified, rel)

            # Show which rules are being fixed
            rule_ids = sorted({i.rule_id for i in preview.issues})
            console.print(f"  [{C_MUTED}]Rules: {', '.join(rule_ids)}[/]")
            console.print()

            file_action = inquirer.select(
                message=f"What would you like to do?",
                choices=[
                    Choice(value="approve", name=f"Apply changes and continue to next file"),
                    Choice(value="skip", name=f"Skip this file and continue to next"),
                    Choice(value="cancel", name="Cancel fix process (return to menu)"),
                ],
                default="approve",
            ).execute()

            if file_action == "approve":
                approved_files.append(str(preview.file_path))
                console.print(f"\n  [{C_OK}]\u2713 Changes approved for {rel}[/]")
            elif file_action == "skip":
                skipped_files.append(rel)
                console.print(f"\n  [{C_WARN}]\u2298 Skipped {rel}[/]")
            else:
                cancelled = True
                console.print(f"\n  [{C_MUTED}]Fix process cancelled[/]")
                break

        if cancelled and not approved_files:
            console.print(f"  [{C_MUTED}]No files modified[/]")
            return

        if not approved_files:
            console.print(f"\n  [{C_MUTED}]No files approved \u2014 nothing modified[/]")
            return

        # Filter fixable issues to only approved files
        approved_set = set(approved_files)
        approved_issues = [i for i in fixable if i.file_path in approved_set]

        console.print(f"\n  [{C_TEXT}]Applying {len(approved_issues)} fixes to {len(approved_files)} file{'s' if len(approved_files) != 1 else ''}...[/]")
        fix_result = apply_fixes(approved_issues, root, backup=True)
    else:
        from composearr.fixer import apply_fixes
        fix_result = apply_fixes(fixable, root, backup=True)
        skipped_files = []

    # ── Clean final summary (no duplication) ──
    _show_fix_summary(console, fix_result, root, skipped_files=skipped_files)


# ── Secure Secrets ────────────────────────────────────────────


def _tui_secure_secrets(console: Console, session: dict) -> None:
    """Secure Secrets hub — extract, view, and manage .env files."""
    _section_header(console, "Secure Secrets", "Manage secrets across your Docker Compose stack")

    # Explain the feature
    console.print(f"  [{C_TEXT}]Keep secrets out of your compose files and in .env instead.[/]")
    console.print(f"    [{C_MUTED}]\u2022 Compose files are often committed to git \u2014 secrets in them get exposed[/]")
    console.print(f"    [{C_MUTED}]\u2022 A .env file keeps secrets separate and can be git-ignored[/]")
    console.print(f"    [{C_MUTED}]\u2022 One place to manage all passwords, API keys, and tokens[/]")
    console.print(f"    [{C_MUTED}]\u2022 Docker Compose natively loads .env files \u2014 no extra config needed[/]")
    console.print()
    console.print(f"  [bold {C_TEXT}]Adding a new service?[/]")
    console.print(f"    [{C_MUTED}]1. Add your secret variables to .env first (use 'Add variable' below)[/]")
    console.print(f"    [{C_MUTED}]2. Reference them in your compose.yaml as: ${'{'}MY_SECRET{'}'}[/]")
    console.print(f"    [{C_MUTED}]3. Run an audit to verify everything is clean[/]")
    console.print(f"    [{C_MUTED}]Or just write your yaml and use 'Extract secrets' to clean it up after.[/]")
    console.print()

    action = inquirer.select(
        message="What would you like to do?",
        choices=[
            Choice(value="extract", name="\U0001f512 Extract secrets \u2014 scan compose files and move inline secrets to .env"),
            Choice(value="smart_env", name="\U0001f4e6 Smart Env Extraction \u2014 split central .env into per-stack files"),
            Choice(value="view", name="\U0001f4cb View .env files \u2014 see all variables across your stack (values masked)"),
            Choice(value="add", name="\u2795  Add variable \u2014 add a new secret to a .env file"),
            *_nav_choices(),
        ],
        default="extract",
    ).execute()

    nav = _check_nav(action)
    if nav:
        return

    if action == "extract":
        _tui_extract_secrets(console, session)
    elif action == "smart_env":
        _tui_smart_env_extraction(console, session)
    elif action == "view":
        _tui_view_env_files(console, session)
    elif action == "add":
        _tui_add_env_variable(console, session)


def _tui_extract_secrets(console: Console, session: dict) -> None:
    """Extract inline secrets from compose files into .env files.

    Smart pattern detection: detects whether the user already has per-app .env files,
    a master .env, or no .env files at all, then adapts the strategy accordingly.
    """
    _section_header(console, "Extract Secrets", "Scan for hardcoded secrets and move them to .env")

    path = _resolve_path(console, session)
    if path is None:
        return

    root = Path(path).resolve()
    console.print()

    # ── Phase 1: Scan ──────────────────────────────────────────
    from rich.progress import Progress, SpinnerColumn, TextColumn
    with Progress(
        SpinnerColumn(style=C_TEAL),
        TextColumn(f"[{C_MUTED}]Analysing your stack\u2026[/]"),
        console=console,
        transient=True,
    ) as progress:
        progress.add_task("", total=None)
        reporter = RichProgressReporter(console)
        result = run_audit(root, progress=reporter)

        # Detect existing .env pattern
        env_files = _discover_env_files(root)
        master_env = root / ".env"
        has_master = master_env.is_file()
        per_app_envs = [e for e in env_files if e != master_env]

    # ── Phase 2: Pattern Detection ─────────────────────────────
    secret_issues = [
        i for i in result.all_issues
        if i.rule_id == "CA101" and i.service and i.suggested_fix
    ]

    # Classify each compose dir
    compose_dirs_with_env: list[str] = []  # dirs that already have their own .env
    compose_dirs_without_env: list[str] = []  # dirs with secrets but no .env
    compose_dirs_clean: list[str] = []  # dirs with no inline secrets

    dirs_with_secrets: set[str] = set()
    for issue in secret_issues:
        dirs_with_secrets.add(str(Path(issue.file_path).parent))

    per_app_env_dirs = {str(e.parent) for e in per_app_envs}

    # All compose file dirs
    for cf in result.compose_files:
        if cf.parse_error:
            continue
        cf_dir = str(cf.path.parent)
        if cf_dir in dirs_with_secrets:
            if cf_dir in per_app_env_dirs:
                compose_dirs_with_env.append(cf_dir)
            else:
                compose_dirs_without_env.append(cf_dir)
        else:
            if cf_dir in per_app_env_dirs:
                compose_dirs_clean.append(cf_dir)

    # Display the analysis
    console.print(f"  [bold {C_TEXT}]Stack Analysis[/]")
    console.print()

    if per_app_envs:
        console.print(f"  [{C_OK}]\u25cf[/] [{C_TEXT}]{len(per_app_envs)} per-app .env file{'s' if len(per_app_envs) != 1 else ''} found[/]")
        for env_path in per_app_envs[:5]:
            try:
                rel = str(env_path.relative_to(root))
            except ValueError:
                rel = str(env_path)
            count = len(_parse_env_file(env_path))
            console.print(f"    [{C_TEAL}]{rel}[/]  [{C_MUTED}]{count} variables[/]")
        if len(per_app_envs) > 5:
            console.print(f"    [{C_MUTED}]\u2026and {len(per_app_envs) - 5} more[/]")
        console.print()

    if has_master:
        count = len(_parse_env_file(master_env))
        console.print(f"  [{C_OK}]\u25cf[/] [{C_TEXT}]Master .env exists at stack root[/]  [{C_MUTED}]{count} variables[/]")
        console.print()

    if not secret_issues:
        console.print(f"  [{C_OK}]\u2713[/] [{C_TEXT}]No inline secrets found \u2014 your compose files are clean![/]")
        if per_app_envs:
            console.print(f"  [{C_MUTED}]Your per-app .env files are doing their job. Nice work![/]")
        console.print()
        return

    console.print(f"  [{C_WARN}]\u25cf[/] [{C_TEXT}]{len(secret_issues)} inline secret{'s' if len(secret_issues) != 1 else ''} found in compose files[/]")
    if compose_dirs_with_env:
        console.print(f"    [{C_MUTED}]{len(compose_dirs_with_env)} dir{'s' if len(compose_dirs_with_env) != 1 else ''} have .env but still have inline secrets[/]")
    if compose_dirs_without_env:
        console.print(f"    [{C_MUTED}]{len(compose_dirs_without_env)} dir{'s' if len(compose_dirs_without_env) != 1 else ''} have inline secrets with no .env file[/]")
    console.print()

    # ── Phase 3: Strategy Selection ────────────────────────────

    # Determine what strategies make sense
    has_per_app_pattern = len(per_app_envs) >= 2  # User is already using per-app .env

    if has_per_app_pattern:
        # User already has a per-app pattern — respect it
        console.print(Rule(f"[bold {C_TEAL}]Your Current Pattern[/]", style=C_DIM))
        console.print()
        console.print(f"  [{C_TEXT}]You're already using per-app .env files \u2014 nice! We can see you've got[/]")
        console.print(f"  [{C_TEXT}]{len(per_app_envs)} apps with their own .env. We have two approaches:[/]")
        console.print()
        console.print(f"  [bold {C_TEAL}]Option A: Per-app (match your pattern)[/]")
        console.print(f"    [{C_MUTED}]Create/update a .env in each app's directory[/]")
        console.print(f"    [{C_MUTED}]Keeps secrets next to the compose file that uses them[/]")
        console.print(f"    [{C_MUTED}]Docker Compose auto-loads .env from the same directory[/]")
        console.print(f"    [{C_MUTED}]Best if: you manage each app independently[/]")
        console.print()
        console.print(f"  [bold {C_TEAL}]Option B: Master .env (consolidate everything)[/]")
        console.print(f"    [{C_MUTED}]Move ALL secrets into a single .env at your stack root[/]")
        console.print(f"    [{C_MUTED}]One file to manage, one file to back up, one file to gitignore[/]")
        console.print(f"    [{C_MUTED}]Each compose file gets an env_file: directive pointing to the master[/]")
        console.print(f"    [{C_MUTED}]Best if: you want one place for everything[/]")
        console.print()

        strategy = inquirer.select(
            message="How should we handle secrets?",
            choices=[
                Choice(value="per-app", name="Per-app .env \u2014 match your existing pattern (recommended)"),
                Choice(value="master", name="Master .env \u2014 consolidate everything into one file"),
                Choice(value="cancel", name="\u2716  Cancel \u2014 don't change anything"),
            ],
            default="per-app",
            long_instruction="Per-app keeps your current structure. Master consolidates into one file.",
        ).execute()
    else:
        # No existing pattern — default to master
        strategy = "master"
        console.print(f"  [{C_TEXT}]We'll extract secrets to a .env file and replace inline values with[/]")
        console.print(f"  [{C_TEXT}]${{VAR}} references. Backups of all modified files are created first.[/]")
        console.print()

    if strategy == "cancel":
        console.print(f"\n  [{C_MUTED}]No files modified.[/]")
        return

    # ── Phase 4: Parse secrets ─────────────────────────────────
    from ruamel.yaml import YAML
    yaml_parser = YAML()
    yaml_parser.preserve_quotes = True

    by_file: dict[str, list[dict]] = defaultdict(list)
    for issue in secret_issues:
        var_name = issue.message.split(" ")[0] if issue.message else "UNKNOWN"
        by_file[issue.file_path].append({
            "var_name": var_name,
            "service": issue.service,
            "issue": issue,
        })

    secrets_to_extract: dict[str, list[dict]] = defaultdict(list)
    skipped = 0

    for file_path, entries in by_file.items():
        try:
            data = yaml_parser.load(Path(file_path).read_text(encoding="utf-8"))
            services = data.get("services", {}) if data else {}
        except Exception:
            skipped += len(entries)
            continue

        for entry in entries:
            svc_config = services.get(entry["service"], {})
            env = svc_config.get("environment")
            var_name = entry["var_name"]
            value = None

            if isinstance(env, dict):
                value = env.get(var_name)
            elif isinstance(env, list):
                for item in env:
                    s = str(item)
                    if s.startswith(f"{var_name}="):
                        value = s[len(var_name) + 1:]
                        break

            if value and not str(value).startswith("${"):
                secrets_to_extract[file_path].append({
                    "var_name": var_name,
                    "value": str(value),
                    "service": entry["service"],
                })
            else:
                skipped += 1

    if not secrets_to_extract:
        console.print(f"  [{C_OK}]\u2713[/] [{C_TEXT}]All detected secrets are already using variable references.[/]")
        return

    # ── Phase 5: Preview ───────────────────────────────────────
    total_secrets = sum(len(v) for v in secrets_to_extract.values())
    console.print(f"  [bold {C_TEXT}]Secrets to extract ({total_secrets} total):[/]")
    console.print()

    for file_path in sorted(secrets_to_extract.keys()):
        entries = secrets_to_extract[file_path]
        try:
            rel = str(Path(file_path).relative_to(root))
        except ValueError:
            rel = file_path
        dest_label = ""
        if strategy == "per-app":
            dest_label = f"  [{C_MUTED}]\u2192 {Path(file_path).parent.name}/.env[/]"
        console.print(f"  [{C_TEAL}]{rel}[/]{dest_label}")
        for entry in entries:
            val = entry["value"]
            masked = val[:4] + "\u2022" * min(len(val) - 4, 20) if len(val) > 8 else "\u2022" * len(val)
            console.print(
                f"    [{C_WARN}]\u25cf[/] [{C_TEXT}]{entry['var_name']}[/]"
                f"  [{C_MUTED}]= {masked}[/]"
                f"  [{C_MUTED}]({entry['service']})[/]"
            )
        console.print()

    if skipped:
        console.print(f"  [{C_MUTED}]{skipped} entries skipped (already using variable references)[/]")
        console.print()

    # Strategy-specific explanation
    if strategy == "master":
        master_env_path = root / ".env"
        env_status = "will append to existing" if master_env_path.is_file() else "will be created"
        console.print(f"  [bold {C_TEXT}]What will happen:[/]")
        console.print(f"    [{C_MUTED}]\u2022 Inline values replaced with ${{VAR}} references in compose files[/]")
        console.print(f"    [{C_MUTED}]\u2022 All secrets go into master .env: {master_env_path} ({env_status})[/]")
        console.print(f"    [{C_MUTED}]\u2022 env_file: directive added to compose files pointing to master .env[/]")
        console.print(f"    [{C_MUTED}]\u2022 .yaml.bak backups created for all modified compose files[/]")
    else:
        console.print(f"  [bold {C_TEXT}]What will happen:[/]")
        console.print(f"    [{C_MUTED}]\u2022 Inline values replaced with ${{VAR}} references in compose files[/]")
        console.print(f"    [{C_MUTED}]\u2022 Secrets go into each app's own .env (same directory as compose file)[/]")
        console.print(f"    [{C_MUTED}]\u2022 Docker Compose auto-loads .env from the same directory \u2014 no env_file: needed[/]")
        console.print(f"    [{C_MUTED}]\u2022 .yaml.bak backups created for all modified compose files[/]")
    console.print(f"    [{C_MUTED}]\u2022 Running containers are NOT affected \u2014 restart with: docker compose up -d[/]")
    console.print()

    action = inquirer.select(
        message="Apply extraction?",
        choices=[
            Choice(value="apply", name=f"\u2713  Apply \u2014 extract secrets ({'master .env' if strategy == 'master' else 'per-app .env'})"),
            Choice(value="cancel", name="\u2716  Cancel \u2014 don't modify any files"),
        ],
        default="apply",
    ).execute()

    if action == "cancel":
        console.print(f"\n  [{C_MUTED}]No files modified.[/]")
        return

    # ── Phase 6: Apply ─────────────────────────────────────────
    import shutil
    from composearr.fixer import verify_yaml_file

    applied = 0
    errors = 0
    backup_paths: list[str] = []
    verified_files: list[str] = []
    verification_errors: list[tuple[str, str]] = []
    env_files_written: list[str] = []

    if strategy == "master":
        master_env_path = root / ".env"
        all_new_env_entries: list[tuple[str, str, str]] = []

        # Read existing master .env
        existing_env: dict[str, str] = {}
        if master_env_path.is_file():
            for line in master_env_path.read_text(encoding="utf-8").splitlines():
                stripped = line.strip()
                if stripped and not stripped.startswith("#") and "=" in stripped:
                    k, _, v = stripped.partition("=")
                    existing_env[k.strip()] = v.strip()

    for file_path, entries in secrets_to_extract.items():
        compose_path = Path(file_path)

        try:
            content = compose_path.read_text(encoding="utf-8")
            data = yaml_parser.load(content)
            services = data.get("services", {})

            # Backup compose file
            bak_path = compose_path.with_suffix(compose_path.suffix + ".bak")
            shutil.copy2(compose_path, bak_path)
            backup_paths.append(str(bak_path))

            modified_services: set[str] = set()

            # Per-app: track env entries for this file's .env
            if strategy == "per-app":
                app_env_path = compose_path.parent / ".env"
                app_existing: dict[str, str] = {}
                if app_env_path.is_file():
                    for line in app_env_path.read_text(encoding="utf-8").splitlines():
                        stripped = line.strip()
                        if stripped and not stripped.startswith("#") and "=" in stripped:
                            k, _, v = stripped.partition("=")
                            app_existing[k.strip()] = v.strip()
                app_new_entries: list[tuple[str, str]] = []

            for entry in entries:
                var_name = entry["var_name"]
                value = entry["value"]
                service_name = entry["service"]

                svc_config = services.get(service_name, {})
                env = svc_config.get("environment")

                # Replace in compose
                if isinstance(env, dict) and var_name in env:
                    env[var_name] = f"${{{var_name}}}"
                    modified_services.add(service_name)
                elif isinstance(env, list):
                    for idx, item in enumerate(env):
                        if str(item).startswith(f"{var_name}="):
                            env[idx] = f"{var_name}=${{{var_name}}}"
                            modified_services.add(service_name)
                            break

                if strategy == "master":
                    if var_name not in existing_env:
                        all_new_env_entries.append((var_name, value, str(compose_path.name)))
                        existing_env[var_name] = value
                else:
                    # Per-app
                    if var_name not in app_existing:
                        app_new_entries.append((var_name, value))
                        app_existing[var_name] = value

                applied += 1

            # Master: add env_file directive
            if strategy == "master":
                master_env_path = root / ".env"
                try:
                    env_rel = str(master_env_path.relative_to(compose_path.parent))
                except ValueError:
                    env_rel = str(master_env_path)
                env_rel = env_rel.replace("\\", "/")

                for svc_name in modified_services:
                    svc_config = services.get(svc_name, {})
                    env_files_val = svc_config.get("env_file")
                    if env_files_val is None:
                        svc_config["env_file"] = [env_rel]
                    elif isinstance(env_files_val, str):
                        if env_files_val != env_rel:
                            svc_config["env_file"] = [env_files_val, env_rel]
                    elif isinstance(env_files_val, list):
                        if env_rel not in env_files_val:
                            env_files_val.append(env_rel)

            # Per-app: write the app's .env
            if strategy == "per-app" and app_new_entries:
                app_env_path = compose_path.parent / ".env"
                env_lines = []
                if not app_env_path.is_file():
                    dir_name = compose_path.parent.name
                    env_lines.append(f"# .env for {dir_name}")
                    env_lines.append("# Managed by ComposeArr")
                    env_lines.append("")
                for var_name, value in app_new_entries:
                    env_lines.append(f"{var_name}={value}")
                env_lines.append("")

                mode = "a" if app_env_path.is_file() else "w"
                if mode == "a":
                    env_lines.insert(0, "")
                with open(app_env_path, mode, encoding="utf-8", newline="\n") as f:
                    f.write("\n".join(env_lines))
                env_files_written.append(str(app_env_path))

            # Write updated compose file
            with open(compose_path, "w", encoding="utf-8", newline="") as f:
                yaml_parser.dump(data, f)

            ok, err_msg = verify_yaml_file(compose_path)
            if ok:
                verified_files.append(str(compose_path))
            else:
                verification_errors.append((str(compose_path), err_msg))

        except Exception as e:
            console.print(f"  [{C_ERR}]\u2716[/] [{C_TEXT}]Error processing {file_path}:[/] [{C_ERR}]{e}[/]")
            errors += len(entries)

    # Master: write master .env
    if strategy == "master" and all_new_env_entries:
        master_env_path = root / ".env"
        env_lines = []
        if not master_env_path.is_file():
            env_lines.append("# Master .env \u2014 all secrets for your Docker Compose stack")
            env_lines.append("# Managed by ComposeArr \u2014 add .env to your .gitignore!")
            env_lines.append("")

        by_source: dict[str, list[tuple[str, str]]] = defaultdict(list)
        for var_name, value, source in all_new_env_entries:
            by_source[source].append((var_name, value))

        for source_file in sorted(by_source.keys()):
            env_lines.append(f"# From {source_file}")
            for var_name, value in by_source[source_file]:
                env_lines.append(f"{var_name}={value}")
            env_lines.append("")

        mode = "a" if master_env_path.is_file() else "w"
        if mode == "a":
            env_lines.insert(0, "")
            env_lines.insert(1, "# Added by ComposeArr")

        with open(master_env_path, mode, encoding="utf-8", newline="\n") as f:
            f.write("\n".join(env_lines))
        env_files_written.append(str(master_env_path))

    # ── Phase 7: Summary ───────────────────────────────────────
    console.print()
    if applied:
        dest = "master .env" if strategy == "master" else "per-app .env files"
        console.print(f"  [{C_OK}]\u2713[/] [{C_TEXT}]Extracted {applied} secrets to {dest}[/]")
    if errors:
        console.print(f"  [{C_ERR}]\u2716[/] [{C_TEXT}]{errors} secrets failed to extract[/]")

    if env_files_written:
        console.print()
        console.print(f"  [{C_OK}]\u2713[/] [{C_TEXT}].env files written:[/]")
        for ef in env_files_written:
            try:
                rel = str(Path(ef).relative_to(root))
            except ValueError:
                rel = ef
            console.print(f"    [{C_TEAL}]{rel}[/]")

    if verified_files:
        console.print()
        n = len(verified_files)
        console.print(f"  [{C_OK}]\u2713[/] [{C_TEXT}]YAML structure verified for {n} modified file{'s' if n != 1 else ''}[/]")
    if verification_errors:
        console.print()
        for vf, err_msg in verification_errors:
            try:
                rel = str(Path(vf).relative_to(root))
            except ValueError:
                rel = vf
            console.print(f"  [{C_ERR}]\u2716[/] [{C_TEXT}]YAML verification failed:[/] [{C_TEAL}]{rel}[/]")
            console.print(f"    [{C_ERR}]{err_msg}[/]")
            console.print(f"    [{C_MUTED}]Restore from backup: cp {rel}.bak {rel}[/]")

    if backup_paths:
        console.print()
        console.print(f"  [{C_OK}]\u2713[/] [{C_TEXT}]Backups created:[/]")
        for bp in backup_paths:
            try:
                rel = str(Path(bp).relative_to(root))
            except ValueError:
                rel = bp
            console.print(f"    [{C_TEAL}]{rel}[/]")

    console.print()
    console.print(f"  [bold {C_TEXT}]Next steps:[/]")
    console.print(f"    [{C_MUTED}]1. Add .env to your .gitignore:[/]  [{C_TEAL}]echo '.env' >> .gitignore[/]")
    console.print(f"    [{C_MUTED}]2. Restart your services:[/]  [{C_TEAL}]docker compose up -d[/]")
    console.print(f"    [{C_MUTED}]3. Verify services start correctly with the new .env references[/]")
    console.print(f"    [{C_MUTED}]4. To rollback: copy .yaml.bak files over the originals[/]")
    console.print()


def _discover_env_files(root: Path) -> list[Path]:
    """Find all .env files across the stack."""
    env_files: list[Path] = []
    # Root level .env
    root_env = root / ".env"
    if root_env.is_file():
        env_files.append(root_env)
    # Per-service .env files (one directory deep)
    for child in sorted(root.iterdir()):
        if child.is_dir() and not child.name.startswith("."):
            child_env = child / ".env"
            if child_env.is_file():
                env_files.append(child_env)
    return env_files


def _parse_env_file(env_path: Path) -> list[tuple[str, str]]:
    """Parse a .env file into (key, value) pairs, preserving order."""
    entries: list[tuple[str, str]] = []
    try:
        for line in env_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" in line:
                key, _, value = line.partition("=")
                entries.append((key.strip(), value.strip()))
    except Exception:
        pass
    return entries


def _mask_value(value: str) -> str:
    """Mask a secret value for display."""
    if not value:
        return "(empty)"
    if len(value) > 8:
        return value[:4] + "\u2022" * min(len(value) - 4, 16)
    return "\u2022" * len(value)


def _tui_smart_env_extraction(console: Console, session: dict) -> None:
    """Smart Env Extraction — split a central .env into per-stack .env files."""
    from rich.panel import Panel
    from rich.table import Table

    from composearr.central_env_analyzer import (
        get_extraction_preview,
        map_vars_to_stacks,
        parse_central_env,
    )
    from composearr.compose_env_updater import update_env_file_reference
    from composearr.gitignore_manager import ensure_env_in_gitignore
    from composearr.stack_env_generator import write_stack_env

    _section_header(
        console, "Smart Env Extraction",
        "Split a central .env file into per-stack .env files",
    )

    console.print(f"  [{C_TEXT}]This tool takes a single central .env file and distributes[/]")
    console.print(f"  [{C_TEXT}]the right variables to each stack's own .env file.[/]")
    console.print()
    console.print(f"  [{C_MUTED}]Benefits:[/]")
    console.print(f"    [{C_MUTED}]\u2022 Each stack has only its own secrets[/]")
    console.print(f"    [{C_MUTED}]\u2022 Works with ALL deployment tools (Portainer, Dockge, Komodo, CLI)[/]")
    console.print(f"    [{C_MUTED}]\u2022 Per-stack .env files can be git-ignored[/]")
    console.print(f"    [{C_MUTED}]\u2022 docker compose commands work unchanged[/]")
    console.print()

    # Step 1: Get the stack directory
    path = _resolve_path(console, session)
    if path is None:
        return
    root = Path(path).resolve()

    # Step 2: Find central .env
    central_env = root / ".env"
    if not central_env.is_file():
        # Ask user to locate it
        env_input = inquirer.text(
            message="Path to central .env file:",
            default=str(central_env),
            validate=lambda p: Path(p).is_file() or "File not found",
        ).execute()
        central_env = Path(env_input).resolve()

    # Step 3: Parse and analyze
    console.print()
    console.print(f"  [{C_MUTED}]Analyzing {central_env.name}...[/]")
    env_vars = parse_central_env(central_env)

    if not env_vars:
        console.print(f"  [{C_ERR}]\u2717[/] [{C_TEXT}]No variables found in {central_env}[/]")
        _pause(console)
        return

    console.print(f"  [{C_OK}]\u2713[/] [{C_TEXT}]Found {len(env_vars)} variables[/]")

    # Step 4: Map to stacks
    stack_mapping = map_vars_to_stacks(env_vars, root)

    if not stack_mapping:
        console.print(f"  [{C_ERR}]\u2717[/] [{C_TEXT}]No stack directories found with compose files[/]")
        _pause(console)
        return

    console.print(f"  [{C_OK}]\u2713[/] [{C_TEXT}]Mapped to {len(stack_mapping)} stacks[/]")
    console.print()

    # Step 5: Show preview
    preview = get_extraction_preview(env_vars, stack_mapping)

    table = Table(
        title="Extraction Preview",
        show_header=True,
        header_style=f"bold {C_TEAL}",
        border_style=C_DIM,
        pad_edge=False,
    )
    table.add_column("Stack", style=C_TEXT)
    table.add_column("Common", style=C_MUTED, justify="center")
    table.add_column("Secrets", style=C_WARN, justify="center")
    table.add_column("Config", style=C_INFO, justify="center")
    table.add_column("Total", style=f"bold {C_TEXT}", justify="center")

    for stack_name in sorted(preview):
        cats = preview[stack_name]
        n_common = len(cats.get("common", []))
        n_secrets = len(cats.get("secrets", []))
        n_other = len(cats.get("stack_specific", [])) + len(cats.get("shared", []))
        total = len(stack_mapping[stack_name])
        table.add_row(
            stack_name,
            str(n_common) if n_common else "-",
            str(n_secrets) if n_secrets else "-",
            str(n_other) if n_other else "-",
            str(total),
        )

    console.print(table)
    console.print()

    # Step 6: Confirm
    proceed = inquirer.select(
        message="Proceed with extraction?",
        choices=[
            Choice(value="yes", name="\u2713 Yes \u2014 create per-stack .env files"),
            Choice(value="preview", name="\U0001f50d Show details \u2014 list variables per stack"),
            *_nav_choices(),
        ],
        default="yes",
    ).execute()

    if _check_nav(proceed):
        return

    if proceed == "preview":
        # Show detailed breakdown
        for stack_name in sorted(preview):
            cats = preview[stack_name]
            console.print(f"\n  [bold {C_TEAL}]{stack_name}[/]")
            for category, var_names in cats.items():
                if var_names:
                    console.print(f"    [{C_MUTED}]{category}:[/] {', '.join(var_names)}")

        console.print()
        final = inquirer.confirm(
            message="Proceed with extraction?",
            default=True,
        ).execute()
        if not final:
            console.print(f"  [{C_MUTED}]Cancelled[/]")
            return

    # Step 7: Execute extraction
    console.print()
    created_count = 0
    updated_count = 0
    gitignore_count = 0

    for stack_name, stack_vars in sorted(stack_mapping.items()):
        stack_dir = root / stack_name
        if not stack_dir.is_dir():
            continue

        # Write .env
        env_path = write_stack_env(stack_dir, stack_name, stack_vars, overwrite=False)
        created_count += 1
        console.print(f"  [{C_OK}]\u2713[/] [{C_TEXT}]{stack_name}/.env[/]  [{C_MUTED}]{len(stack_vars)} variables[/]")

        # Update compose.yaml
        compose_file = stack_dir / "compose.yaml"
        if not compose_file.is_file():
            compose_file = stack_dir / "docker-compose.yml"

        if compose_file.is_file():
            changed = update_env_file_reference(compose_file, new_env_path=".env")
            if changed:
                updated_count += 1
                console.print(f"  [{C_OK}]\u2713[/] [{C_TEXT}]{stack_name}/{compose_file.name}[/]  [{C_MUTED}]env_file \u2192 .env[/]")

        # Update .gitignore
        if ensure_env_in_gitignore(stack_dir):
            gitignore_count += 1

    # Step 8: Summary
    console.print()
    console.print(Panel(
        f"[bold {C_OK}]Smart Env Extraction Complete[/]\n\n"
        f"  [{C_TEXT}]Created:[/] [{C_TEAL}]{created_count}[/] [{C_MUTED}]per-stack .env files[/]\n"
        f"  [{C_TEXT}]Updated:[/] [{C_TEAL}]{updated_count}[/] [{C_MUTED}]compose files (env_file \u2192 .env)[/]\n"
        f"  [{C_TEXT}]Secured:[/] [{C_TEAL}]{gitignore_count}[/] [{C_MUTED}].gitignore files updated[/]\n\n"
        f"  [{C_MUTED}]Your stacks now use local .env files.[/]\n"
        f"  [{C_MUTED}]Test with: docker compose logs (should work!)[/]\n"
        f"  [{C_MUTED}]The central .env can be kept as backup or removed.[/]",
        border_style=C_OK,
    ))

    _pause(console)


def _tui_view_env_files(console: Console, session: dict) -> None:
    """View the master .env and any other .env files across the stack."""
    _section_header(console, "View .env Files", "See all environment variables across your stack")

    path = _resolve_path(console, session)
    if path is None:
        return

    root = Path(path).resolve()
    env_files = _discover_env_files(root)

    if not env_files:
        console.print(f"  [{C_MUTED}]No .env files found in your stack.[/]")
        console.print(f"  [{C_MUTED}]Use 'Extract secrets' or 'Add variable' to create one.[/]")
        return

    from rich.table import Table
    from rich import box
    from rich.style import Style

    total_vars = 0
    for env_path in env_files:
        entries = _parse_env_file(env_path)
        if not entries:
            continue

        try:
            rel = str(env_path.relative_to(root))
        except ValueError:
            rel = str(env_path)

        console.print(f"\n  [{C_TEAL}]{rel}[/]  [{C_MUTED}]({len(entries)} variables)[/]")

        table = Table(
            box=box.SIMPLE_HEAD,
            border_style=Style(color="#27272a"),
            header_style=f"{C_MUTED}",
            padding=(0, 2),
            show_edge=False,
        )
        table.add_column("VARIABLE", style=f"bold {C_TEXT}", no_wrap=True)
        table.add_column("VALUE (masked)", style=C_MUTED)

        for key, value in entries:
            table.add_row(key, _mask_value(value))
            total_vars += 1

        console.print(table)

    console.print()
    console.print(f"  [{C_TEXT}]{total_vars} variables across {len(env_files)} .env files[/]")
    console.print()
    console.print(f"  [{C_MUTED}]To use a variable in your compose.yaml:[/]")
    console.print(f"    [{C_TEAL}]environment:[/]")
    console.print(f"    [{C_TEAL}]  MY_SECRET: ${{MY_SECRET}}[/]")
    console.print()


def _tui_add_env_variable(console: Console, session: dict) -> None:
    """Add a new variable to the master .env file."""
    _section_header(console, "Add Variable", "Add a new secret to your master .env")

    console.print(f"  [{C_TEXT}]Add a new variable to your master .env before writing a compose.yaml.[/]")
    console.print(f"  [{C_TEXT}]Your new service can reference it as ${'{'}VAR{'}'} from the start \u2014 no cleanup needed.[/]")
    console.print()

    path = _resolve_path(console, session)
    if path is None:
        return

    root = Path(path).resolve()
    env_path = root / ".env"

    console.print(f"  [{C_TEXT}]Master .env:[/] [{C_TEAL}]{env_path}[/]")
    if env_path.is_file():
        count = len(_parse_env_file(env_path))
        console.print(f"  [{C_MUTED}]{count} variables already in master .env[/]")
    else:
        console.print(f"  [{C_MUTED}]Master .env doesn't exist yet \u2014 it will be created[/]")
    console.print()

    # Show existing variables in this file
    existing = _parse_env_file(env_path)
    if existing:
        console.print(f"\n  [{C_MUTED}]Existing variables in this file:[/]")
        for key, _ in existing:
            console.print(f"    [{C_TEXT}]{key}[/]")
        console.print()

    # Loop: add variables until user is done
    added = 0
    while True:
        # Offer back/exit before committing to entering a variable
        ready = inquirer.select(
            message="Add a variable?",
            choices=[
                Choice(value="add", name="\u2795 Add a new variable"),
                *_nav_choices(),
            ],
            default="add",
        ).execute()

        nav = _check_nav(ready)
        if nav:
            break

        var_name = inquirer.text(
            message="Variable name (e.g. MY_API_KEY):",
            validate=lambda v: (
                bool(v.strip()) and v.strip() == v.strip().upper().replace(" ", "_")
            ) or "Use UPPER_SNAKE_CASE (e.g. MY_API_KEY)",
        ).execute()

        # Check for duplicates
        existing_keys = {k for k, _ in _parse_env_file(env_path)}
        if var_name in existing_keys:
            console.print(f"  [{C_WARN}]\u26a0[/] [{C_TEXT}]{var_name} already exists in this file[/]")
            overwrite = inquirer.select(
                message="Overwrite?",
                choices=[
                    Choice(value="skip", name="Skip \u2014 keep existing value"),
                    Choice(value="overwrite", name="Overwrite \u2014 replace with new value"),
                ],
                default="skip",
            ).execute()
            if overwrite == "skip":
                continue

        var_value = inquirer.text(
            message=f"Value for {var_name}:",
            validate=lambda v: bool(v.strip()) or "Value cannot be empty",
        ).execute()

        # Append to .env file
        try:
            if not env_path.is_file():
                header = f"# .env file managed by ComposeArr\n# Location: {env_path.parent.name}/\n\n"
                env_path.write_text(header + f"{var_name}={var_value}\n", encoding="utf-8")
            else:
                # Check if overwriting
                if var_name in existing_keys:
                    # Rewrite file with updated value
                    lines = env_path.read_text(encoding="utf-8").splitlines()
                    new_lines = []
                    for line in lines:
                        if line.strip().startswith(f"{var_name}="):
                            new_lines.append(f"{var_name}={var_value}")
                        else:
                            new_lines.append(line)
                    env_path.write_text("\n".join(new_lines) + "\n", encoding="utf-8")
                else:
                    with open(env_path, "a", encoding="utf-8") as f:
                        f.write(f"{var_name}={var_value}\n")

            added += 1
            console.print(f"  [{C_OK}]\u2713[/] [{C_TEXT}]{var_name} added[/]")
            console.print(f"    [{C_MUTED}]Use in compose.yaml as:[/]  [{C_TEAL}]{var_name}: ${{{var_name}}}[/]")
            console.print()

        except Exception as e:
            console.print(f"  [{C_ERR}]\u2716[/] [{C_TEXT}]Failed to write: {e}[/]")

        # Continue or done?
        more = inquirer.select(
            message="Add another variable?",
            choices=[
                Choice(value="more", name="\u2795 Add another variable"),
                Choice(value="done", name="\u2713 Done \u2014 return to Secure Secrets menu"),
            ],
            default="done",
        ).execute()

        if more == "done":
            break

    if added:
        try:
            rel = str(env_path.relative_to(root))
        except ValueError:
            rel = str(env_path)
        console.print()
        console.print(f"  [{C_OK}]\u2713[/] [{C_TEXT}]Added {added} variable{'s' if added != 1 else ''} to[/] [{C_TEAL}]{rel}[/]")
        console.print()
        console.print(f"  [{C_TEXT}]Remember to reference these in your compose.yaml:[/]")
        console.print(f"    [{C_TEAL}]environment:[/]")
        console.print(f"    [{C_TEAL}]  VAR_NAME: ${{VAR_NAME}}[/]")
        console.print()
        console.print(f"  [{C_MUTED}]Tip: Add .env to your .gitignore to keep secrets out of version control[/]")
        console.print()


# ── Ports ──────────────────────────────────────────────────────


def _tui_ports(console: Console, session: dict) -> None:
    """Port allocation table."""
    from composearr.commands.ports import collect_ports, render_port_table

    _section_header(console, "Port Allocation", "See all port mappings and detect conflicts across your stack")

    path = _resolve_path(console, session)
    if path is None:
        return

    view_mode = inquirer.select(
        message="What to show?",
        choices=[
            Choice(value="all", name="All port mappings \u2014 every host:container port across your stack"),
            Choice(value="conflicts", name="Conflicts only \u2014 ports used by more than one service"),
            *_nav_choices(),
        ],
        default="all",
    ).execute()

    nav = _check_nav(view_mode)
    if nav:
        return

    root = Path(path).resolve()

    from rich.progress import Progress, SpinnerColumn, TextColumn
    with Progress(
        SpinnerColumn(style=C_TEAL),
        TextColumn(f"[{C_MUTED}]Scanning ports\u2026[/]"),
        console=console,
        transient=True,
    ) as progress:
        progress.add_task("", total=None)
        all_ports = collect_ports(root)

    render_port_table(
        all_ports, root, console,
        show_conflicts_only=(view_mode == "conflicts"),
    )


# ── Network Topology ──────────────────────────────────────────


def _tui_topology(console: Console, session: dict) -> None:
    """Network topology visualization."""
    from composearr.commands.topology import render_topology

    _section_header(console, "Network Topology", "How your services connect to each other")

    path = _resolve_path(console, session)
    if path is None:
        return

    root = Path(path).resolve()

    from composearr.scanner.discovery import discover_compose_files
    from composearr.scanner.parser import parse_compose_file

    from rich.progress import Progress, SpinnerColumn, TextColumn
    with Progress(
        SpinnerColumn(style=C_TEAL),
        TextColumn(f"[{C_MUTED}]Analyzing network topology\u2026[/]"),
        console=console,
        transient=True,
    ) as progress:
        progress.add_task("", total=None)
        paths, _ = discover_compose_files(root)
        compose_files = [parse_compose_file(p) for p in paths]
        compose_files = [cf for cf in compose_files if not cf.parse_error]

    if not compose_files:
        console.print(f"  [{C_MUTED}]No compose files found[/]")
        return

    render_topology(root, console, compose_files=compose_files)


# ── Rules & Explain (combined — with back loop) ───────────────


def _tui_rules_and_explain(console: Console) -> None:
    """View rules list, then optionally explain one — loops until user goes back."""
    from rich.table import Table
    from rich import box
    from rich.style import Style

    _section_header(console, "Rules & Explain", "Browse all lint rules. Select one to see detailed explanation")

    all_rules = sorted(get_all_rules(), key=lambda x: x.id)
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

    for r in all_rules:
        color = sev_colors.get(r.severity, C_MUTED)
        dot = f"[{color}]\u25cf[/]"
        sev_label = f"[{color}]{r.severity.value}[/]"
        table.add_row(dot, r.id, sev_label, r.name, r.description)

    console.print()
    console.print(f"  [{C_TEXT}]Available Rules[/]  [{C_MUTED}]{len(all_rules)} rules[/]")
    console.print()
    console.print(table)
    console.print()

    # Loop: explain rules until user goes back
    while True:
        choices = [
            Choice(value=r.id, name=f"{r.id}  {r.name}")
            for r in all_rules
        ]
        choices.append(Choice(value=_BACK, name="\u2190 Back to menu"))

        console.print(f"  [{C_MUTED}]Select a rule below and press Enter to see a detailed explanation.[/]")
        console.print()

        rule_id = inquirer.select(
            message="Explain a rule:",
            choices=choices,
            default=_BACK,
        ).execute()

        if rule_id == _BACK:
            break

        from composearr.commands.explain import render_explanation
        render_explanation(rule_id, console)
        console.print()


# ── Scaffold (Templates) ──────────────────────────────────────


def _tui_scaffold(console: Console) -> None:
    """Generate a compose file from a best-practice template."""
    _section_header(console, "Scaffold", "Generate best-practice compose files from templates")

    console.print(f"  [{C_TEXT}]Every template includes healthchecks, resource limits, logging,[/]")
    console.print(f"  [{C_TEXT}]security options, and pinned image tags — a clean bill of health[/]")
    console.print(f"  [{C_TEXT}]from ComposeArr before you even start.[/]")
    console.print()

    from composearr.templates.engine import TemplateEngine
    from rich import box
    from rich.table import Table

    engine = TemplateEngine()
    templates = engine.list_templates()

    if not templates:
        console.print(f"  [{C_WARN}]\u26a0[/] [{C_TEXT}]No templates available[/]")
        return

    # Show available templates
    table = Table(
        box=box.SIMPLE_HEAD,
        border_style="#27272a",
        header_style=C_MUTED,
    )
    table.add_column("TEMPLATE", style=f"bold {C_TEAL}")
    table.add_column("DESCRIPTION", style=C_TEXT)
    table.add_column("CATEGORY", style=C_MUTED)

    for name, meta in sorted(templates.items()):
        table.add_row(name, meta.description, meta.category)

    console.print(table)
    console.print()

    # Select template
    choices = [
        Choice(value=name, name=f"{name:<15s} \u2014 {meta.description}")
        for name, meta in sorted(templates.items())
    ]
    choices.extend(_nav_choices())

    template_name = inquirer.select(
        message="Select a template:",
        choices=choices,
    ).execute()

    nav = _check_nav(template_name)
    if nav:
        return

    meta = templates[template_name]

    # Output directory
    default_dir = str(Path.cwd() / template_name)
    output_str = inquirer.text(
        message="Output directory:",
        default=default_dir,
    ).execute()
    output_dir = Path(output_str)

    # Collect variables
    variables: dict[str, str] = {}
    if meta.env_vars:
        console.print()
        console.print(f"  [{C_TEXT}]Configure environment variables:[/]")
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

    # Generate
    try:
        result = engine.generate(template_name, output_dir, variables)
    except Exception as e:
        console.print(f"  [{C_ERR}]\u2716[/] [{C_TEXT}]Error: {e}[/]")
        return

    console.print()
    console.print(f"  [{C_OK}]\u2713[/] [{C_TEXT}]Generated[/] [{C_TEAL}]{template_name}[/] [{C_TEXT}]compose stack![/]")
    console.print()
    console.print(f"  [{C_TEXT}]Files created:[/]")
    console.print(f"    [{C_TEAL}]compose.yaml[/]  \u2014 {result.compose_path}")
    if result.env_path:
        console.print(f"    [{C_TEAL}].env[/]          \u2014 {result.env_path}")
    console.print()
    console.print(f"  [{C_TEXT}]Next steps:[/]")
    console.print(f"    [{C_MUTED}]1. Review compose.yaml and update volume paths[/]")
    console.print(f"    [{C_MUTED}]2. Edit .env with your actual values[/]")
    console.print(f"    [{C_MUTED}]3. cd {output_dir}[/]")
    console.print(f"    [{C_MUTED}]4. docker compose up -d[/]")
    console.print()
    console.print(f"  [{C_MUTED}]Tip: Run composearr audit to verify your new stack![/]")
    console.print()


# ── Batch Fix ─────────────────────────────────────────────────


def _tui_batch(console: Console, session: dict) -> None:
    """Batch fix mode — scan and fix without individual prompts."""
    _section_header(console, "Batch Fix", "CI/CD friendly auto-fix across all compose files")

    console.print(f"  [{C_TEXT}]Batch mode scans your entire stack and applies all available[/]")
    console.print(f"  [{C_TEXT}]auto-fixes in one pass. Backups are created automatically.[/]")
    console.print()
    console.print(f"  [{C_MUTED}]CLI equivalent: composearr batch --fix --yes[/]")
    console.print()

    path = _auto_resolve_path(console, session)
    if path is None:
        return

    root = Path(path).resolve()

    # Confirm
    proceed = inquirer.select(
        message="Scan and auto-fix all issues?",
        choices=[
            Choice(value="fix", name="\u2713 Fix all \u2014 apply all auto-fixes with backups"),
            Choice(value="scan", name="\U0001f50d Scan only \u2014 show issues without fixing"),
            *_nav_choices(),
        ],
        default="fix",
    ).execute()

    nav = _check_nav(proceed)
    if nav:
        return

    from composearr.batch import BatchProcessor
    from rich.progress import Progress, SpinnerColumn, TextColumn

    processor = BatchProcessor(
        stack_path=root,
        auto_approve=(proceed == "fix"),
        create_backups=True,
    )

    with Progress(
        SpinnerColumn(style=C_TEAL),
        TextColumn(f"[{C_MUTED}]Scanning and fixing compose files\u2026[/]"),
        console=console,
        transient=True,
    ) as progress:
        progress.add_task("", total=None)
        result = processor.fix_all()

    console.print(f"  [{C_TEXT}]Files processed:[/] [{C_TEAL}]{result.files_processed}[/]")
    console.print(f"  [{C_TEXT}]Issues found:[/]    [{C_TEAL}]{result.issues_found}[/]")
    console.print(f"  [{C_TEXT}]Issues fixed:[/]    [{C_OK}]{result.issues_fixed}[/]")
    console.print(f"  [{C_TEXT}]Unfixable:[/]       [{C_MUTED}]{result.issues_unfixable}[/]")
    console.print()

    if result.fixed_rules:
        console.print(f"  [{C_TEXT}]Fixed by rule:[/]")
        for rule_id, count in sorted(result.fixed_rules.items()):
            console.print(f"    [{C_TEAL}]{rule_id}[/]: {count}")
        console.print()

    if result.errors:
        console.print(f"  [{C_ERR}]Errors ({len(result.errors)}):[/]")
        for error in result.errors:
            console.print(f"    [{C_MUTED}]{error}[/]")
        console.print()

    if result.issues_fixed > 0:
        console.print(f"  [{C_MUTED}]Backups created as .yaml.bak files.[/]")
        console.print(f"  [{C_MUTED}]Your running containers are NOT affected \u2014 restart with: docker compose up -d[/]")
        console.print()


# ── Config ─────────────────────────────────────────────────────


def _tui_config(console: Console, session: dict) -> None:
    """Config view/validate."""
    _section_header(console, "Configuration", "Customize how ComposeArr behaves for your stack")

    # Explain what config is and why the user should care
    console.print(f"  [{C_TEXT}]ComposeArr can be customized with a .composearr.yml config file.[/]")
    console.print(f"  [{C_MUTED}]This lets you:[/]")
    console.print(f"    [{C_MUTED}]\u2022 Change rule severity (error/warning/info/off) per rule[/]")
    console.print(f"    [{C_MUTED}]\u2022 Ignore specific paths (e.g. backups, test fixtures)[/]")
    console.print(f"    [{C_MUTED}]\u2022 Add trusted registries so they don't trigger warnings[/]")
    console.print(f"    [{C_MUTED}]\u2022 Set default severity level for all audits[/]")
    console.print()
    console.print(f"  [{C_MUTED}]Config files are loaded from two locations (merged together):[/]")
    console.print(f"    [{C_TEAL}]~/.composearr.yml[/]          [{C_MUTED}]\u2014 your global preferences[/]")
    console.print(f"    [{C_TEAL}]<stack>/.composearr.yml[/]    [{C_MUTED}]\u2014 project-specific overrides[/]")
    console.print()
    console.print(f"  [{C_MUTED}]No config file? That's fine \u2014 ComposeArr uses sensible defaults.[/]")
    console.print(f"  [{C_MUTED}]See examples/ in the ComposeArr repo for starter configs (homelab, arrstack, production).[/]")
    console.print()

    action = inquirer.select(
        message="What would you like to do?",
        choices=[
            Choice(value="show", name="Show effective configuration \u2014 see what settings are currently active"),
            Choice(value="create", name="Create starter config \u2014 generate a .composearr.yml for your stack"),
            Choice(value="validate", name="Validate config files \u2014 check your .composearr.yml for errors"),
            Choice(value="reset", name="Reset config \u2014 delete your .composearr.yml and start fresh"),
            *_nav_choices(),
        ],
        default="show",
    ).execute()

    nav = _check_nav(action)
    if nav:
        return

    path_str = _resolve_path(console, session)
    if path_str is None:
        return
    project_path = Path(path_str).resolve()

    if action == "reset":
        _tui_reset_config(console, project_path)
        return

    elif action == "create":
        _tui_create_config(console, project_path)

    elif action == "validate":
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
            console.print(f"  [{C_MUTED}]Use 'Create starter config' to generate one, or create manually.[/]")
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


def _tui_reset_config(console: Console, project_path: Path) -> None:
    """Delete existing .composearr.yml files so user starts from a blank slate."""
    config_locations: list[Path] = []

    # Check project-level configs
    for name in [".composearr.yml", ".composearr.yaml"]:
        p = project_path / name
        if p.is_file():
            config_locations.append(p)

    # Check global config
    user_config = Path.home() / ".composearr.yml"
    if user_config.is_file():
        config_locations.append(user_config)

    if not config_locations:
        console.print(f"\n  [{C_MUTED}]No .composearr.yml files found. Already running with defaults.[/]")
        return

    console.print(f"\n  [{C_TEXT}]Found config files:[/]")
    for cf in config_locations:
        console.print(f"    [{C_TEAL}]{cf}[/]")
    console.print()

    console.print(f"  [{C_WARN}]This will permanently delete the selected config files.[/]")
    console.print(f"  [{C_MUTED}]ComposeArr will use sensible defaults until you create a new config.[/]")
    console.print(f"  [{C_MUTED}]You can rebuild your config right after from this same menu.[/]")
    console.print()

    # Let user pick which to delete
    if len(config_locations) == 1:
        choices = [
            Choice(value="all", name=f"\u2713 Delete {config_locations[0]}"),
            Choice(value="cancel", name="\u2716  Cancel \u2014 keep config"),
        ]
    else:
        choices = [
            Choice(value="all", name="\u2713 Delete all config files"),
        ]
        for cf in config_locations:
            label = "global" if cf == user_config else "project"
            choices.append(Choice(value=str(cf), name=f"\u2713 Delete {label} only \u2014 {cf}"))
        choices.append(Choice(value="cancel", name="\u2716  Cancel \u2014 keep everything"))

    action = inquirer.select(
        message="What to reset?",
        choices=choices,
        default="cancel",
    ).execute()

    if action == "cancel":
        console.print(f"\n  [{C_MUTED}]No changes made.[/]")
        return

    deleted = []
    targets = config_locations if action == "all" else [Path(action)]
    for cf in targets:
        try:
            cf.unlink()
            deleted.append(cf)
        except OSError as e:
            console.print(f"  [{C_ERR}]Failed to delete {cf}: {e}[/]")

    if deleted:
        console.print(f"\n  [{C_OK}]\u2713 Config reset![/]")
        for cf in deleted:
            console.print(f"    [{C_MUTED}]Deleted: {cf}[/]")
        console.print(f"\n  [{C_MUTED}]ComposeArr is now running with defaults.[/]")
        console.print(f"  [{C_MUTED}]Select 'Create starter config' from the Config menu to build a new one.[/]")


def _tui_create_config(console: Console, project_path: Path) -> None:
    """Interactive config generator — walks user through creating .composearr.yml."""
    dest = project_path / ".composearr.yml"

    if dest.exists():
        overwrite = inquirer.select(
            message=f"{dest} already exists. Overwrite?",
            choices=[
                Choice(value="overwrite", name="\u2713 Overwrite \u2014 replace with new config"),
                Choice(value="cancel", name="\u2716  Cancel \u2014 keep existing config"),
            ],
            default="cancel",
        ).execute()
        if overwrite == "cancel":
            console.print(f"\n  [{C_MUTED}]No changes made.[/]")
            return

    # Step 1: Choose a preset
    console.print(f"\n  [{C_TEXT}]Choose a starting point for your config:[/]")
    console.print()

    preset = inquirer.select(
        message="Config preset:",
        choices=[
            Choice(value="homelab", name="Homelab \u2014 relaxed settings, many registries trusted, healthchecks optional"),
            Choice(value="arrstack", name="Arr Stack \u2014 tuned for Sonarr/Radarr/Prowlarr media automation stacks"),
            Choice(value="production", name="Production \u2014 strict, all rules at error level, no exceptions"),
            Choice(value="custom", name="Custom \u2014 set severity for every rule yourself"),
            Choice(value="minimal", name="Minimal \u2014 bare config with just defaults, customize from scratch"),
            *_nav_choices(),
        ],
        default="homelab",
    ).execute()

    nav = _check_nav(preset)
    if nav:
        return

    # Step 2: Severity level
    severity = inquirer.select(
        message="Default minimum severity for audits:",
        choices=[
            Choice(value="error", name="Error only \u2014 just the critical stuff"),
            Choice(value="warning", name="Warning \u2014 errors + best practice issues (recommended)"),
            Choice(value="info", name="Info \u2014 everything including suggestions"),
        ],
        default="warning",
    ).execute()

    # Step 3: Trusted registries
    console.print(f"\n  [{C_MUTED}]Trusted registries won't trigger 'untrusted registry' warnings.[/]")
    console.print(f"  [{C_MUTED}]docker.io and ghcr.io are always included.[/]")
    console.print()

    extra_registries = inquirer.checkbox(
        message="Additional trusted registries (space to toggle):",
        choices=[
            Choice(value="lscr.io", name="lscr.io \u2014 LinuxServer.io images", enabled=preset in ("homelab", "arrstack")),
            Choice(value="gcr.io", name="gcr.io \u2014 Google Container Registry", enabled=preset == "homelab"),
            Choice(value="cr.hotio.dev", name="cr.hotio.dev \u2014 Hotio images (Sonarr, Radarr, etc.)", enabled=preset == "arrstack"),
            Choice(value="quay.io", name="quay.io \u2014 Red Hat Quay registry", enabled=False),
        ],
    ).execute()

    registries = ["docker.io", "ghcr.io"] + sorted(extra_registries)

    # Step 4: Custom per-rule severity (only for "custom" preset)
    custom_rules: dict[str, str] = {}
    if preset == "custom":
        from composearr.config import DEFAULT_RULES, _RULE_NAME_TO_ID

        # Build reverse map: ID -> human name
        _id_to_name = {v: k for k, v in _RULE_NAME_TO_ID.items()}

        _rule_descriptions = {
            "CA001": "Warn on :latest tags (unpinned versions)",
            "CA003": "Untrusted container registries",
            "CA101": "Secrets hardcoded in compose files",
            "CA201": "Missing healthcheck definitions",
            "CA202": "Fake healthchecks (exit 0 / true)",
            "CA203": "Missing restart policy",
            "CA301": "Port conflicts between services",
            "CA302": "Unreachable service dependencies",
            "CA303": "Isolated services exposing ports",
            "CA401": "PUID/PGID mismatch across services",
            "CA402": "Inconsistent umask values",
            "CA403": "Missing timezone (TZ) variable",
            "CA404": "Duplicate environment variables",
            "CA501": "Missing memory limit (unbounded RAM)",
            "CA502": "Missing CPU limit (can starve others)",
            "CA503": "Unusual resource limits for known app",
            "CA504": "No logging config (disk fill risk)",
            "CA505": "No log rotation limits",
            "CA601": "Hardlink-unfriendly volume paths",
            "CA701": "Bind mounts vs named volumes",
            "CA702": "Undefined volume references",
            "CA304": "DNS config issues (host mode, localhost)",
            "CA801": "No capability restrictions (cap_drop)",
            "CA802": "Privileged mode (full host access)",
            "CA803": "Read-only root filesystem hardening",
            "CA804": "No-new-privileges security option",
            "CA901": "Resource reservations/limits mismatch",
            "CA902": "Restart always (infinite crash loop risk)",
            "CA903": "Tmpfs mount without size limit",
            "CA904": "User namespace remapping (advanced)",
        }

        console.print(f"\n  [{C_TEXT}]Set severity for each rule:[/]")
        console.print(f"  [{C_MUTED}]error = must fix | warning = should fix | info = suggestion | off = disable[/]")
        console.print()

        sev_choices = [
            Choice(value="error", name="error"),
            Choice(value="warning", name="warning"),
            Choice(value="info", name="info"),
            Choice(value="off", name="off"),
        ]

        for rule_id in sorted(DEFAULT_RULES.keys()):
            name = _id_to_name.get(rule_id, rule_id)
            desc = _rule_descriptions.get(rule_id, "")
            default_sev = DEFAULT_RULES[rule_id]
            rule_sev = inquirer.select(
                message=f"{rule_id} ({name}) \u2014 {desc}",
                choices=sev_choices,
                default=default_sev,
            ).execute()
            custom_rules[rule_id] = rule_sev

    # Step 5: Build the YAML content
    lines = [
        "# ComposeArr configuration",
        f"# Generated by ComposeArr TUI for: {project_path.name}",
        f"# Preset: {preset}",
        "",
    ]

    # Rules section based on preset
    if preset == "custom":
        lines.extend([
            f"severity: {severity}",
            "",
            "rules:",
        ])
        for rule_id in sorted(custom_rules.keys()):
            sev_val = custom_rules[rule_id]
            desc = _rule_descriptions.get(rule_id, "")
            lines.append(f"  {rule_id}: {sev_val:<10s} # {desc}")
    elif preset == "homelab":
        lines.extend([
            f"severity: {severity}",
            "",
            "rules:",
            "  CA001: warning    # Warn on :latest tags (not critical for homelab)",
            "  CA003: off        # Don't flag registries — homelabs use many sources",
            "  CA101: error      # Secrets in compose files are critical",
            "  CA201: info       # Healthchecks nice-to-have, not essential",
            "  CA203: warning    # Restart policies recommended",
            "  CA301: error      # Port conflicts break services",
            "  CA401: error      # PUID/PGID must match for file permissions",
            "  CA403: warning    # Timezone consistency matters for logs",
            "  CA501: warning    # Memory limits recommended",
            "  CA502: info       # CPU limits nice-to-have for homelab",
            "  CA504: warning    # Logging config prevents disk fill",
            "  CA701: info       # Named volumes suggestion",
            "  CA702: error      # Undefined volume references",
            "  CA801: info       # Capability restrictions (educational)",
            "  CA802: error      # Privileged mode is dangerous",
            "  CA803: off        # Read-only root too advanced for homelab",
            "  CA804: info       # No-new-privileges suggestion",
            "  CA901: info       # Resource requests/limits mismatch",
            "  CA902: info       # Restart always (crash loop risk)",
            "  CA903: warning    # Tmpfs without size limit",
            "  CA904: off        # User namespace (too advanced for homelab)",
        ])
    elif preset == "arrstack":
        lines.extend([
            f"severity: {severity}",
            "",
            "rules:",
            "  CA001: error      # Pin image versions for reproducibility",
            "  CA101: error      # No secrets in compose files",
            "  CA201: warning    # Healthchecks recommended for arr services",
            "  CA203: error      # Restart policies essential for automation",
            "  CA301: error      # Port conflicts break the stack",
            "  CA401: error      # PUID/PGID must match across all arr apps",
            "  CA403: error      # Timezone must be consistent for scheduling",
            "  CA501: warning    # Memory limits prevent OOM kills",
            "  CA502: warning    # CPU limits prevent starvation",
            "  CA504: warning    # Logging config prevents disk fill",
            "  CA601: warning    # Hardlink-friendly volume mounts",
            "  CA701: info       # Named volumes suggestion",
            "  CA702: error      # Undefined volume references",
            "  CA801: info       # Capability restrictions (arr apps need some caps)",
            "  CA802: error      # Privileged mode is dangerous",
            "  CA803: off        # Read-only root not compatible with arr apps",
            "  CA804: info       # No-new-privileges suggestion",
            "  CA901: info       # Resource requests/limits mismatch",
            "  CA902: info       # Restart always (crash loop risk)",
            "  CA903: warning    # Tmpfs without size limit",
            "  CA904: off        # User namespace (not needed for arr apps)",
        ])
    elif preset == "production":
        lines.extend([
            f"severity: {severity}",
            "",
            "rules:",
            "  CA001: error      # Never use :latest in production",
            "  CA002: error      # Always pin digests",
            "  CA003: error      # Only trusted registries",
            "  CA101: error      # No inline secrets",
            "  CA201: error      # Healthchecks required",
            "  CA202: error      # No fake healthchecks",
            "  CA203: error      # Restart policies required",
            "  CA301: error      # No port conflicts",
            "  CA302: error      # No privileged ports without reason",
            "  CA401: error      # PUID/PGID consistency",
            "  CA403: error      # Timezone consistency",
            "  CA501: error      # Memory limits required",
            "  CA502: error      # CPU limits required",
            "  CA504: error      # Logging config required",
            "  CA505: error      # Log rotation required",
            "  CA701: warning    # Named volumes preferred in production",
            "  CA702: error      # All volumes must be defined",
            "  CA801: warning    # Capability restrictions recommended",
            "  CA802: error      # Privileged mode forbidden in production",
            "  CA803: warning    # Read-only root recommended where possible",
            "  CA804: warning    # No-new-privileges recommended",
            "  CA901: warning    # Resource requests/limits must match",
            "  CA902: warning    # No unlimited restart policies",
            "  CA903: error      # Tmpfs must have size limits",
            "  CA904: info       # User namespace (advanced hardening)",
        ])
    else:
        # Minimal
        lines.extend([
            f"severity: {severity}",
            "",
            "# Uncomment and customize rules as needed:",
            "# rules:",
            "#   CA001: warning    # :latest tag usage",
            "#   CA101: error      # Inline secrets",
            "#   CA201: info       # Missing healthchecks",
        ])

    # Add stack_path so auto-detect remembers this location
    lines.extend([
        "",
        "# Your Docker stack directory — auto-detect will find it instantly",
        f"stack_path: {project_path}",
        "",
        "ignore_paths:",
        '  - "**/test/**"',
        '  - "**/backup/**"',
        "",
        "trusted_registries:",
    ])
    for reg in registries:
        lines.append(f"  - {reg}")
    lines.append("")

    content = "\n".join(lines)

    # Preview
    console.print(f"\n  [{C_TEXT}]Config preview:[/]")
    console.print()
    for line in content.splitlines():
        if line.startswith("#"):
            console.print(f"  [{C_MUTED}]{line}[/]")
        elif ":" in line and not line.strip().startswith("-"):
            console.print(f"  [{C_TEAL}]{line}[/]")
        else:
            console.print(f"  [{C_TEXT}]{line}[/]")
    console.print()

    # Confirm save
    save = inquirer.select(
        message=f"Save to {dest}?",
        choices=[
            Choice(value="save", name=f"\u2713 Save \u2014 write config to {dest.name}"),
            Choice(value="cancel", name="\u2716  Cancel \u2014 discard and go back"),
        ],
        default="save",
    ).execute()

    if save == "cancel":
        console.print(f"\n  [{C_MUTED}]Config not saved.[/]")
        return

    dest.write_text(content, encoding="utf-8")

    # Also ensure user-level config points to this stack so discovery always works
    user_config = Path.home() / ".composearr.yml"
    if not user_config.is_file():
        try:
            user_config.write_text(
                f"# ComposeArr user config — points to your stack\n"
                f"stack_path: {project_path}\n",
                encoding="utf-8",
            )
        except Exception:
            pass  # Non-critical — stack config still works from the project dir

    # ── Post-save messaging ──────────────────────────────────
    console.print()
    console.print(Rule(f"[bold {C_TEAL}]Config Saved[/]", style=C_DIM))
    console.print()
    console.print(f"  [{C_OK}]\u2713[/] [{C_TEXT}]Saved to:[/] [{C_TEAL}]{dest}[/]")
    console.print()
    console.print(f"  [{C_TEXT}]ComposeArr will automatically load this file on every launch.[/]")
    console.print(f"  [{C_TEXT}]You can also edit it manually with any text editor \u2014 it\u2019s just YAML.[/]")
    console.print(f"  [{C_MUTED}]We\u2019ll be caring aggressively about it from here on out.[/]")
    console.print()

    # Config format reference guide
    console.print(Rule(f"[bold {C_TEAL}]Config Reference Guide[/]", style=C_DIM))
    console.print()
    console.print(f"  [{C_TEXT}]Your .composearr.yml supports these settings:[/]")
    console.print()
    console.print(f"  [{C_TEAL}]stack_path:[/]           [{C_MUTED}]Path to your Docker stack directory[/]")
    console.print(f"                        [{C_MUTED}]Example: stack_path: C:/DockerContainers[/]")
    console.print()
    console.print(f"  [{C_TEAL}]severity:[/]             [{C_MUTED}]Default minimum severity for audits[/]")
    console.print(f"                        [{C_MUTED}]Values: error | warning | info[/]")
    console.print()
    console.print(f"  [{C_TEAL}]rules:[/]                [{C_MUTED}]Per-rule severity overrides[/]")
    console.print(f"                        [{C_MUTED}]Values per rule: error | warning | info | off[/]")
    console.print(f"                        [{C_MUTED}]Example:[/]")
    console.print(f"                        [{C_MUTED}]  rules:[/]")
    console.print(f"                        [{C_MUTED}]    CA001: warning   # :latest tag usage[/]")
    console.print(f"                        [{C_MUTED}]    CA101: error     # inline secrets[/]")
    console.print(f"                        [{C_MUTED}]    CA201: off       # disable healthcheck rule[/]")
    console.print()
    console.print(f"  [{C_TEAL}]ignore:[/]               [{C_MUTED}]Skip specific files or services[/]")
    console.print(f"                        [{C_MUTED}]  ignore:[/]")
    console.print(f"                        [{C_MUTED}]    files:[/]")
    console.print(f"                        [{C_MUTED}]      - \"**/test/**\"[/]")
    console.print(f"                        [{C_MUTED}]      - \"**/backup/**\"[/]")
    console.print(f"                        [{C_MUTED}]    services:[/]")
    console.print(f"                        [{C_MUTED}]      - watchtower[/]")
    console.print()
    console.print(f"  [{C_TEAL}]trusted_registries:[/]   [{C_MUTED}]Registries that won't trigger CA003[/]")
    console.print(f"                        [{C_MUTED}]  trusted_registries:[/]")
    console.print(f"                        [{C_MUTED}]    - docker.io[/]")
    console.print(f"                        [{C_MUTED}]    - ghcr.io[/]")
    console.print(f"                        [{C_MUTED}]    - lscr.io[/]")
    console.print()
    console.print(f"  [{C_TEAL}]defaults:[/]             [{C_MUTED}]Default audit options[/]")
    console.print(f"                        [{C_MUTED}]  defaults:[/]")
    console.print(f"                        [{C_MUTED}]    severity: warning[/]")
    console.print(f"                        [{C_MUTED}]    group_by: file    # rule | file | severity[/]")
    console.print(f"                        [{C_MUTED}]    format: console   # console | json | sarif | github[/]")
    console.print()
    console.print(f"  [{C_TEXT}]All rules:[/]")
    _print_rules_quick_ref(console)
    console.print()
    console.print(f"  [{C_MUTED}]Tip: Run Config \u2192 Validate to check your config for errors anytime.[/]")
