"""Config validation command."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from composearr.config import DEFAULT_RULES, _RULE_NAME_TO_ID, Config, load_config
from composearr.models import Severity


def validate_config_data(data: dict) -> list[str]:
    """Validate a config dict and return a list of issue strings."""
    issues: list[str] = []

    # Valid top-level keys
    valid_top_keys = {
        "rules", "ignore", "trusted_registries", "telemetry", "defaults",
        "stack_path", "severity", "ignore_paths",
    }
    for key in data:
        if key not in valid_top_keys:
            issues.append(f"Unknown top-level key: '{key}'")

    # Validate rules section
    if "rules" in data:
        rules = data["rules"]
        if not isinstance(rules, dict):
            issues.append("'rules' must be a mapping of rule names/IDs to severity levels")
        else:
            valid_severities = {"error", "warning", "info", "off"}
            all_rule_ids = set(DEFAULT_RULES.keys())
            all_rule_names = set(_RULE_NAME_TO_ID.keys())

            for name_or_id, severity in rules.items():
                name_str = str(name_or_id)
                sev_str = str(severity).lower()

                # Check if rule exists
                if name_str.upper() not in all_rule_ids and name_str.lower() not in all_rule_names:
                    issues.append(f"Unknown rule: '{name_str}'")

                # Check severity value
                if sev_str not in valid_severities:
                    issues.append(f"Invalid severity '{severity}' for rule '{name_str}'. Valid: error, warning, info, off")

    # Validate ignore section
    if "ignore" in data:
        ignore = data["ignore"]
        if isinstance(ignore, dict):
            valid_ignore_keys = {"files", "services"}
            for key in ignore:
                if key not in valid_ignore_keys:
                    issues.append(f"Unknown key in 'ignore': '{key}'. Valid: files, services")
                else:
                    if not isinstance(ignore[key], list):
                        issues.append(f"'ignore.{key}' must be a list")
        elif not isinstance(ignore, list):
            issues.append("'ignore' must be a list of glob patterns or a mapping with 'files'/'services' keys")

    # Validate trusted_registries
    if "trusted_registries" in data:
        tr = data["trusted_registries"]
        if not isinstance(tr, list):
            issues.append("'trusted_registries' must be a list of registry hostnames")
        else:
            for item in tr:
                if not isinstance(item, str):
                    issues.append(f"trusted_registries entry must be a string, got: {type(item).__name__}")

    # Validate defaults section
    if "defaults" in data:
        defaults = data["defaults"]
        if not isinstance(defaults, dict):
            issues.append("'defaults' must be a mapping")
        else:
            valid_default_keys = {"severity", "group_by", "format", "verbose", "no_network"}
            for key in defaults:
                if key not in valid_default_keys:
                    issues.append(f"Unknown key in 'defaults': '{key}'")

            if "severity" in defaults:
                try:
                    Severity(str(defaults["severity"]).lower())
                except ValueError:
                    issues.append(f"Invalid default severity: '{defaults['severity']}'. Valid: error, warning, info")

            if "group_by" in defaults:
                if str(defaults["group_by"]) not in ("rule", "file", "severity"):
                    issues.append(f"Invalid default group_by: '{defaults['group_by']}'. Valid: rule, file, severity")

            if "format" in defaults:
                if str(defaults["format"]) not in ("console", "json", "github", "sarif"):
                    issues.append(f"Invalid default format: '{defaults['format']}'. Valid: console, json, github, sarif")

    return issues


def render_effective_config(config: Config, console: "Console", project_path: Path | None = None) -> None:
    """Render the effective merged config."""
    from rich.table import Table
    from rich import box
    from rich.style import Style

    C_TEAL = "#2dd4bf"
    C_MUTED = "#71717a"
    C_TEXT = "#fafafa"
    C_ERR = "#ef4444"
    C_WARN = "#f59e0b"
    C_INFO = "#3b82f6"
    C_OK = "#22c55e"
    C_BORDER = "#27272a"

    sev_colors = {"error": C_ERR, "warning": C_WARN, "info": C_INFO, "off": C_MUTED}

    console.print()
    console.print(f"  [bold {C_TEXT}]Effective Configuration[/]")
    console.print()

    # Show config file sources
    user_config = Path.home() / ".composearr.yml"
    if user_config.is_file():
        console.print(f"  [{C_OK}]\u2713[/] [{C_TEXT}]User config:[/] [{C_TEAL}]{user_config}[/]")
    else:
        console.print(f"  [{C_MUTED}]\u2022[/] [{C_MUTED}]No user config at {user_config}[/]")

    if project_path:
        found_project = False
        for name in [".composearr.yml", ".composearr.yaml"]:
            p = project_path / name
            if p.is_file():
                console.print(f"  [{C_OK}]\u2713[/] [{C_TEXT}]Project config:[/] [{C_TEAL}]{p}[/]")
                found_project = True
                break
        if not found_project:
            console.print(f"  [{C_MUTED}]\u2022[/] [{C_MUTED}]No project config in {project_path}[/]")
    console.print()

    # Rules table
    table = Table(
        box=box.SIMPLE_HEAD,
        border_style=Style(color=C_BORDER),
        header_style=f"{C_MUTED}",
        padding=(0, 2),
        show_edge=False,
    )
    table.add_column("RULE", style=f"bold {C_TEXT}", no_wrap=True)
    table.add_column("SEVERITY", no_wrap=True)
    table.add_column("STATUS", no_wrap=True)

    for rule_id in sorted(config.rules.keys()):
        sev = config.rules[rule_id]
        color = sev_colors.get(sev, C_MUTED)
        enabled = config.is_rule_enabled(rule_id)
        status = f"[{C_OK}]enabled[/]" if enabled else f"[{C_MUTED}]disabled[/]"
        default_sev = DEFAULT_RULES.get(rule_id, "warning")
        modified = " *" if sev != default_sev else ""
        table.add_row(rule_id, f"[{color}]{sev}{modified}[/]", status)

    console.print(table)
    console.print()

    if config.ignore_patterns:
        console.print(f"  [bold {C_TEXT}]Ignored file patterns:[/]")
        for p in config.ignore_patterns:
            console.print(f"    [{C_MUTED}]\u2022[/] [{C_TEXT}]{p}[/]")
        console.print()

    if config.ignore_services:
        console.print(f"  [bold {C_TEXT}]Ignored services:[/]")
        for s in config.ignore_services:
            console.print(f"    [{C_MUTED}]\u2022[/] [{C_TEXT}]{s}[/]")
        console.print()

    console.print(f"  [{C_MUTED}]* = modified from default[/]")
    console.print()
