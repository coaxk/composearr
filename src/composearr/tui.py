"""Interactive TUI menu for ComposeArr."""

from __future__ import annotations

import importlib.resources
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path

from InquirerPy import inquirer
from InquirerPy.base.control import Choice
from rich.console import Console
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

# ── ASCII Art ──────────────────────────────────────────────────

# Plain-text fallback for terminals without true-color support
_ROLL_SAFE_FALLBACK = (
    f"[{C_MUTED}]"
    "\n                         :                ~~;::=~;,~=;,;=:,,,=%#%@@%%##**"
    "\n                         :.               ~~;::=~;,-=-:;=:,,,~~~=+=+++++="
    "\n                         ,.               -~;:,=~;,-=-;:=;,,,~~==~~=+++++"
    "\n ,.           .:;;;:,.   ,.               -~-;,~=-,;=-::=;,,,-=~=~~=+++++"
    "\n :,         :~++**####+; ,,               ;=-;,~=-:;=~;:=-,,,-~~==~=++++%"
    "\n   ,   ,. :~+*#*##%%%%@@+,,            .. ;=-;,-=-:;=~;:=-,:,-=~==++++**%"
    "\n   ;. =%+~+*#%%%@@@@@@@@@+.          .... :=-;,-=-::=~;:~~::,-~-=%@*++**%"
    "\n -:+=+%+=*%%%@@@@@@@@@@@@@- .   . ....... :=-;:-=~;:=~;:~~::,-=~~@@###%#%"
    "\n ##*#%*++%@%@@*+====;;~====...............,=~-:-=~;:=~-:~=::,;=~~%@%%####"
    "\n ***%***#%%@@;         ;~~~, .............,=~-:;=~;:~=-:-=;::;=~~%@@++===" "="
    "\n +#%#**#%@@@-          ,--~-..............,=~-:;=~;:~=-:-=;::;=~~#@@+=+**"
    "\n -+#*#**==~;.         .,;-~+: ............,~~-;;=~-:~=-:;=;::;=~-#@@###%%"
    "\n :-#*##*#=~=;,  .     .,:-~+=............,,~~-;;=~-:-=~;;=-;::=~-#@@#@#%#"
    "\n ==***#@@@%+~;,::,.....,:--~=,...........,.~=-;:==-:-=~;;=-:::=~-*@@#@#@#"
    "\n ;=**#%%@#+=~,:-;:,.   ,;---+#..........,,.~=-;;==-;-=~;;=-;::~~-*@@#@#@#"
    "\n ~~#**%@%++;  +-,    .,;-~=#@%.......,,,,,.-=~;;==~;-=~-;=~;;:~~~+@@#@@@@"
    "\n =-*#**%++- ,+%-..-+#%@%#*%@%*,....,,,,,,,.-=~-;==~;-=~-;=~;;:~==#@@@@@@@"
    "\n =,+**#=;; .~+*-;~+#%@@@@=#@++..,.,,,,,,,,.;=~-;~=~;-==-;==;;;~==#@@@@@@@"
    "\n #;+###*~ :~-;~~+#@@%~@%= ,#@#:.,,,,,,,,,,.;+~-;~=~--==-;==;;;-=~+@@@@@@@"
    "\n %@#*##=. :::;;~==~==*#;.  ;+=-.,,,,,,,,,,,;+~-;~+~--==~;==;;;-=;-@@@@@@@"
    "\n **###%*. ;::;.--::~++,..   :=+.,,,,,,,,,,,;+~-;~+=-;==~;~+-;;-=-~@@@@@@@"
    "\n ==**###, ~;;, ,;=.   :-    :#*.,,,,,,,,,,,:==~;-+=--=+~-~+-;;-=~~%@@@@@@"
    "\n ;~***##: :,,..,;=-::~+=~~+*%@=.,,,,,,,,,,,:==~;-+=~;=+~-~+--;-=~~%@@@@@@"
    "\n ==*##%#.  .. ,:,.,+#@*~@@@@@@-.,,,,,,,,,,,:==~-;+=~-=+=-~+~---=-~@@@@@@@"
    "\n ;~#*#%%,.:.    .-:,=@##@%+*%*,,,,,,,,,,,,,,==~--+=~-=+=-~+~---=-=@#%@@@@"
    "\n ::~++#@:.::.,..,-:~*@@@+=+*=;,,,,,,,,,,,,::==~--++~-=+=~~+=---=*%@%@@@@@"
    "\n +=*%%@@, ,,.. ,-;,+*@%#+;:;~:,,,,,,,,,,::::~=~-;++=-=+=~-+=---=%%~+@@@@@"
    "\n %%%##@- .,,.  ,--;=*@@@@%#@#,,,,,,,,,,,::::~==~;++=-~+=~-+=---=@**~%@@@@"
    "\n ==~~++ .,,....,;;~+@@@@@@@@=.,,:::,,,:,:::,~+~~;++=-~*=~~++---=%@+=+=*+~"
    "\n +**#+  .,,.,,,:,;-#@@@@@@@@+:,,,,:::::,:::,-+~~-++=~~*+=~++~--=%#+%%%###"
    "\n @@@*;.  ,,,..,:,:-#@@@@@@@@@#+~-;:,::::::::-+=~-=+=~~*+=~++~--~#+~+%%@@@"
    "\n @@-;,:  ,,,,,::,:~%@@@@@@@@@%##***~:,::::::-+=~-=*+~~*+=~+*~--~**###++*%"
    "\n %: *~-.  ,,:,,,:;=@@@@@@@@@@@#+++##*=;:::::;+==--*+=~*+=~=*~~~~*#**%###@"
    "\n ,.::~=:..,,,..,:-+@@@@@@@@@@@%*=+++##*=;:::;+==-~*+=~*+=~=*~~~~*%*#@%+=#"
    "\n ::~:~=:,..,.  .;-*@@@@@%#%@%@@#====*###*-:::++=~~*+=~++=~=*=~~~*@%%@@#%@"
    "\n[/]"
)


def _load_ansi_art(console: Console) -> Text | str:
    """Load true-color ANSI art if terminal supports it, otherwise fallback."""
    # Check if terminal supports true-color (24-bit)
    color_system = console.color_system
    if color_system != "truecolor":
        return _ROLL_SAFE_FALLBACK

    try:
        ref = importlib.resources.files("composearr") / "assets" / "rollsafe.ansi"
        raw = ref.read_text(encoding="utf-8")
        return Text.from_ansi(raw)
    except Exception:
        return _ROLL_SAFE_FALLBACK

# Plain-text fallback whale for terminals without true-color support
_WHALE_FALLBACK = (
    f"[{C_INFO}]"
    "\n                    ##         ."
    "\n              ## ## ##        =="
    "\n           ## ## ## ## ##    ==="
    '\n       /"""""""""""""""""\\___/ ==='
    "\n      {                       /  ===-"
    "\n       \\______ O           __/"
    "\n         \\    \\         __/"
    "\n          \\____\\_______/"
    "\n[/]"
)


def _load_whale_art(console: Console) -> Text | str:
    """Load true-color whale ANSI art if available, otherwise fallback."""
    color_system = console.color_system
    if color_system != "truecolor":
        return _WHALE_FALLBACK

    try:
        ref = importlib.resources.files("composearr") / "assets" / "whale.ansi"
        raw = ref.read_text(encoding="utf-8")
        return Text.from_ansi(raw)
    except Exception:
        return _WHALE_FALLBACK


def _render_figlet_title(console: Console) -> str | None:
    """Render ComposeArr version banner in Big Money-nw FIGlet font.

    Returns Rich markup string, or None if terminal is too narrow.
    """
    try:
        import pyfiglet
    except ImportError:
        return None

    term_width = console.width or 80
    title_text = f"ComposeArr v{__version__}"

    # Generate with wide width, check if it fits
    art = pyfiglet.figlet_format(title_text, font="big_money-nw", width=300)
    lines = [l.rstrip() for l in art.split("\n")]
    while lines and not lines[-1]:
        lines.pop()

    max_width = max((len(l) for l in lines), default=0)

    if max_width > term_width:
        # Try just "ComposeArr" if full title is too wide
        art = pyfiglet.figlet_format("ComposeArr", font="big_money-nw", width=300)
        lines = [l.rstrip() for l in art.split("\n")]
        while lines and not lines[-1]:
            lines.pop()
        max_width = max((len(l) for l in lines), default=0)

        if max_width > term_width:
            return None  # Terminal too narrow for any FIGlet

        # Append version below in plain text
        lines.append(f"  v{__version__}")

    joined = "\n".join(lines)
    return f"[{C_TEAL}]{joined}[/]"


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


# ── Path Resolution (session-aware) ───────────────────────────


def _resolve_path(console: Console, session: dict) -> str | None:
    """Resolve stack path — silently reuses session path if available.

    When the session already has a path, uses it directly (no prompt).
    When no path exists, prompts for auto-detect or manual entry.
    Use _change_path() to explicitly change the remembered path.
    """
    remembered = session.get("path")

    if remembered:
        # Silently reuse — the path is shown in settings dashboard / confirmed elsewhere
        console.print(f"  [{C_MUTED}]Using:[/] [{C_TEAL}]{remembered}[/]")
        return remembered

    # First time — need to find the stacks
    return _prompt_for_path(console, session)


def _prompt_for_path(console: Console, session: dict) -> str | None:
    """Prompt user to find their stacks (auto-detect or manual)."""
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
            default=session.get("path") or str(Path.cwd()),
            validate=lambda p: Path(p).is_dir() or "Directory not found",
        ).execute()

    session["path"] = path
    return path


def _change_path(console: Console, session: dict) -> str | None:
    """Explicitly change the remembered path."""
    remembered = session.get("path")
    path_mode = inquirer.select(
        message="Change stack directory:",
        choices=[
            Choice(value="auto", name="Re-scan (auto-detect)"),
            Choice(value="manual", name="Enter path manually"),
            *_nav_choices(),
        ],
        default="auto",
    ).execute()

    nav = _check_nav(path_mode)
    if nav:
        return remembered  # Keep current path on back/exit

    # Clear and re-resolve
    old_path = session.pop("path", None)
    result = _prompt_for_path(console, session)
    if result is None:
        # User cancelled — restore old path
        if old_path:
            session["path"] = old_path
        return old_path
    return result


def _auto_resolve_path(console: Console, session: dict) -> str | None:
    """Auto-resolve path silently for quick audit — no prompts if session has path."""
    remembered = session.get("path")
    if remembered:
        return remembered

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
        session["path"] = path
        return path

    # Fall back to manual prompt
    return _resolve_path(console, session)


# ── Main TUI Entry Point ──────────────────────────────────────


def launch_tui() -> None:
    """Launch interactive TUI menu."""
    console = make_console()
    session: dict = {}

    # Welcome screen with art (true-color ANSI if supported, ASCII fallback)
    art = _load_ansi_art(console)
    console.print()
    console.print(art)
    console.print()

    # Big Money-nw FIGlet title (adapts to terminal width)
    title_art = _render_figlet_title(console)
    if title_art:
        console.print(title_art)
    else:
        console.print(f"  [bold {C_TEAL}]ComposeArr[/] [{C_MUTED}]v{__version__}[/]")
    console.print(f"  [{C_MUTED}]Docker Compose Hygiene Linter[/]")
    console.print()

    while True:
        action = inquirer.select(
            message="What would you like to do?",
            choices=[
                Choice(value="quick", name="\u26a1 Quick Audit (smart defaults)"),
                Choice(value="audit", name="\u2699  Custom Audit (configure options)"),
                Choice(value="fix", name="\U0001f527 Fix issues"),
                Choice(value="ports", name="\U0001f4cb Port allocation table"),
                Choice(value="topology", name="\U0001f310 Network topology"),
                Choice(value="rules", name="\U0001f4d6 Rules & Explain"),
                Choice(value="config", name="\u2699  Config"),
                Choice(value=_EXIT, name="\u2716  Exit"),
            ],
            default="quick",
        ).execute()

        if action == _EXIT:
            whale = _load_whale_art(console)
            console.print()
            console.print(whale)
            console.print()
            console.print(f"  [{C_MUTED}]Goodbye![/]\n")
            break
        elif action == "quick":
            _tui_quick_audit(console, session)
        elif action == "audit":
            _tui_custom_audit(console, session)
        elif action == "fix":
            _tui_fix(console, session)
        elif action == "ports":
            _tui_ports(console, session)
        elif action == "topology":
            _tui_topology(console, session)
        elif action == "rules":
            _tui_rules_and_explain(console)
        elif action == "config":
            _tui_config(console, session)


# ── Quick Audit ────────────────────────────────────────────────


def _tui_quick_audit(console: Console, session: dict) -> None:
    """One-click audit with smart defaults."""
    path = _auto_resolve_path(console, session)
    if path is None:
        return

    root = Path(path).resolve()
    console.print()

    reporter = RichProgressReporter(console)
    result = run_audit(root, progress=reporter)
    console.print()

    fmt_opts = FormatOptions(
        min_severity=Severity.ERROR,
        verbose=False,
        group_by="rule",
    )

    formatter = ConsoleFormatter(console)
    formatter.render(result, str(root), options=fmt_opts)

    # Post-audit actions
    _post_audit_menu(console, session, result, root)


def _post_audit_menu(console: Console, session: dict, result, root: Path) -> None:
    """After an audit completes, offer next actions."""
    has_fixable = any(i.fix_available for i in result.all_issues)

    choices = []
    if has_fixable:
        choices.append(Choice(value="fix", name="\U0001f527 Fix issues"))
    choices.extend([
        Choice(value="rerun", name="\u26a1 Re-run with different settings"),
        Choice(value="export", name="\U0001f4be Export results (JSON/SARIF)"),
        Choice(value="ports", name="\U0001f4cb View port allocation"),
        Choice(value="menu", name="\u2190 Back to main menu"),
    ])

    console.print()
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
        all_ports = collect_ports(root)
        render_port_table(all_ports, root, console)


def _export_results(console: Console, result, root: Path) -> None:
    """Export audit results to file."""
    fmt = inquirer.select(
        message="Export format:",
        choices=[
            Choice(value="json", name="JSON"),
            Choice(value="sarif", name="SARIF (GitHub Advanced Security)"),
            Choice(value="github", name="GitHub Actions annotations"),
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

    # Default audit settings
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
        path_display = settings["path"]
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

        console.print(f"  [bold {C_TEXT}]Audit Settings[/]")
        console.print(f"    [{C_MUTED}]Path:[/]     [{C_TEAL}]{path_display}[/]")
        console.print(f"    [{C_MUTED}]Severity:[/] [{C_TEXT}]{settings['severity']}[/]")
        console.print(f"    [{C_MUTED}]Group by:[/] [{C_TEXT}]{settings['group_by']}[/]")
        console.print(f"    [{C_MUTED}]Format:[/]   [{C_TEXT}]{settings['format']}[/]")
        console.print(f"    [{C_MUTED}]Options:[/]  [{C_TEXT}]{opts_display}[/]")
        console.print(f"    [{C_MUTED}]Rules:[/]    [{C_TEXT}]{rules_display}[/]")
        console.print()

        action = inquirer.select(
            message="",
            choices=[
                Choice(value="run", name=f"\u25b6 Run audit"),
                Choice(value="path", name=f"  Change path"),
                Choice(value="severity", name=f"  Change severity"),
                Choice(value="group_by", name=f"  Change grouping"),
                Choice(value="format", name=f"  Change format"),
                Choice(value="options", name=f"  Toggle options (verbose, no-network)"),
                Choice(value="rules", name=f"  Filter rules"),
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
                ],
                default=settings["severity"],
            ).execute()
            settings["severity"] = val

        elif action == "group_by":
            val = inquirer.select(
                message="Group issues by:",
                choices=[
                    Choice(value="rule", name="Rule (default)"),
                    Choice(value="file", name="File"),
                    Choice(value="severity", name="Severity"),
                ],
                default=settings["group_by"],
            ).execute()
            settings["group_by"] = val

        elif action == "format":
            val = inquirer.select(
                message="Output format:",
                choices=[
                    Choice(value="console", name="Console (rich terminal output)"),
                    Choice(value="json", name="JSON (machine-readable)"),
                    Choice(value="sarif", name="SARIF (GitHub Advanced Security)"),
                    Choice(value="github", name="GitHub Actions annotations"),
                ],
                default=settings["format"],
            ).execute()
            settings["format"] = val

        elif action == "options":
            selected = inquirer.checkbox(
                message="Toggle options (space to toggle):",
                choices=[
                    Choice(value="verbose", name="Verbose — full file context", enabled=settings["verbose"]),
                    Choice(value="no_network", name="No network — skip tag lookups", enabled=settings["no_network"]),
                ],
            ).execute()
            settings["verbose"] = "verbose" in selected
            settings["no_network"] = "no_network" in selected

        elif action == "rules":
            filter_mode = inquirer.select(
                message="Rule filter:",
                choices=[
                    Choice(value="all", name="All rules"),
                    Choice(value="select", name="Select specific rules"),
                    Choice(value="exclude", name="Exclude specific rules"),
                ],
                default="all",
            ).execute()

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
                Choice(value="both", name="Save to file AND print to screen"),
                Choice(value="file", name="Save to file only"),
                Choice(value="screen", name="Print to screen only"),
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


# ── Fix Issues ─────────────────────────────────────────────────


def _tui_fix(console: Console, session: dict) -> None:
    """Fix flow — scan, review, apply."""
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
        return

    console.print(f"  [{C_TEXT}]Found[/] [bold {C_TEAL}]{len(fixable)}[/] [{C_TEXT}]fixable issues[/]")
    console.print()

    # Group by file for display
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
            fix_preview = issue.suggested_fix.split("\n")[0]
            console.print(f"      [{C_OK}]\u2192[/] [{C_TEAL}]{fix_preview}[/]")
        console.print()

    # Apply or not?
    action = inquirer.select(
        message="Apply fixes?",
        choices=[
            Choice(value="apply_backup", name="\u2713 Apply with backups (.bak files)"),
            Choice(value="apply_no_backup", name="\u2713 Apply without backups"),
            Choice(value="cancel", name="\u2716 Cancel \u2014 don't modify files"),
        ],
        default="apply_backup",
    ).execute()

    if action == "cancel":
        console.print(f"\n  [{C_MUTED}]No files modified[/]")
        return

    from composearr.fixer import apply_fixes
    backup = action == "apply_backup"
    fix_result = apply_fixes(fixable, root, backup=backup)

    console.print()
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


# ── Ports ──────────────────────────────────────────────────────


def _tui_ports(console: Console, session: dict) -> None:
    """Port allocation table."""
    from composearr.commands.ports import collect_ports, render_port_table

    path = _resolve_path(console, session)
    if path is None:
        return

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

    path = _resolve_path(console, session)
    if path is None:
        return

    root = Path(path).resolve()

    from rich.progress import Progress, SpinnerColumn, TextColumn
    with Progress(
        SpinnerColumn(style=C_TEAL),
        TextColumn(f"[{C_MUTED}]Analyzing network topology\u2026[/]"),
        console=console,
        transient=True,
    ) as progress:
        progress.add_task("", total=None)
        # Pre-load to trigger the spinner
        from composearr.scanner.discovery import discover_compose_files
        from composearr.scanner.parser import parse_compose_file
        paths, _ = discover_compose_files(root)
        _ = [parse_compose_file(p) for p in paths]

    render_topology(root, console)


# ── Rules & Explain (combined — flatter) ──────────────────────


def _tui_rules_and_explain(console: Console) -> None:
    """View rules list, then optionally explain one."""
    from rich.table import Table
    from rich import box
    from rich.style import Style

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

    # Offer to explain a rule
    choices = [
        Choice(value=r.id, name=f"{r.id}  {r.name}")
        for r in all_rules
    ]
    choices.append(Choice(value=_BACK, name="\u2190 Back to menu"))

    rule_id = inquirer.select(
        message="Explain a rule? (or go back)",
        choices=choices,
        default=_BACK,
    ).execute()

    if rule_id != _BACK:
        from composearr.commands.explain import render_explanation
        render_explanation(rule_id, console)


# ── Config ─────────────────────────────────────────────────────


def _tui_config(console: Console, session: dict) -> None:
    """Config view/validate."""
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
