"""Configuration system for ComposeArr."""

from __future__ import annotations

import fnmatch
import re
from dataclasses import dataclass, field
from pathlib import Path

from ruamel.yaml import YAML

from composearr.models import Severity

_yaml = YAML()
_yaml.preserve_quotes = True

# Rule name -> ID mapping for inline suppression by name
_RULE_NAME_TO_ID: dict[str, str] = {
    "no-latest-tag": "CA001",
    "no-inline-secrets": "CA101",
    "require-healthcheck": "CA201",
    "no-fake-healthcheck": "CA202",
    "require-restart-policy": "CA203",
    "port-conflict": "CA301",
    "puid-pgid-mismatch": "CA401",
    "umask-inconsistent": "CA402",
    "missing-timezone": "CA403",
    "hardlink-path-mismatch": "CA601",
}

# Default rule severities
DEFAULT_RULES: dict[str, str] = {
    "CA001": "warning",
    "CA101": "error",
    "CA201": "warning",
    "CA202": "warning",
    "CA203": "warning",
    "CA301": "error",
    "CA401": "error",
    "CA402": "warning",
    "CA403": "warning",
    "CA601": "warning",
}


@dataclass
class Config:
    """ComposeArr configuration."""

    rules: dict[str, str] = field(default_factory=lambda: dict(DEFAULT_RULES))
    ignore_patterns: list[str] = field(default_factory=list)
    ignore_services: list[str] = field(default_factory=list)

    def is_rule_enabled(self, rule_id: str) -> bool:
        return self.rules.get(rule_id, "warning") != "off"

    def get_severity(self, rule_id: str) -> Severity | None:
        sev_str = self.rules.get(rule_id, DEFAULT_RULES.get(rule_id, "warning"))
        if sev_str == "off":
            return None
        try:
            return Severity(sev_str)
        except ValueError:
            return Severity.WARNING

    def should_ignore_file(self, file_path: str) -> bool:
        for pattern in self.ignore_patterns:
            if fnmatch.fnmatch(file_path, pattern):
                return True
        return False

    def should_ignore_service(self, service_name: str) -> bool:
        return service_name in self.ignore_services

    def merge(self, other: dict) -> None:
        """Merge a config dict (from YAML) into this config."""
        if "rules" in other and isinstance(other["rules"], dict):
            for name_or_id, severity in other["rules"].items():
                # Accept both rule names and IDs
                rule_id = _RULE_NAME_TO_ID.get(str(name_or_id), str(name_or_id).upper())
                self.rules[rule_id] = str(severity)

        if "ignore" in other:
            ignore = other["ignore"]
            if isinstance(ignore, list):
                for item in ignore:
                    if isinstance(item, str):
                        self.ignore_patterns.append(item)
            if isinstance(ignore, dict):
                # Handle structured ignore
                services = ignore.get("services", [])
                if isinstance(services, list):
                    self.ignore_services.extend(str(s) for s in services)
                files = ignore.get("files", [])
                if isinstance(files, list):
                    self.ignore_patterns.extend(str(f) for f in files)


def load_config(project_path: Path | None = None) -> Config:
    """Load config from hierarchy: defaults -> user -> project."""
    config = Config()

    # User config
    user_config = Path.home() / ".composearr.yml"
    if user_config.is_file():
        _merge_file(config, user_config)

    # Project config
    if project_path:
        for name in [".composearr.yml", ".composearr.yaml"]:
            project_config = project_path / name
            if project_config.is_file():
                _merge_file(config, project_config)
                break

    return config


def _merge_file(config: Config, path: Path) -> None:
    """Merge a YAML config file into the config."""
    try:
        data = _yaml.load(path)
        if isinstance(data, dict):
            config.merge(data)
    except Exception:
        pass  # Gracefully ignore broken config files


# ── Inline suppression ─────────────────────────────────────────────

_IGNORE_PATTERN = re.compile(r"#\s*composearr-ignore:\s*(.+)")
_IGNORE_SERVICE_PATTERN = re.compile(r"#\s*composearr-ignore-service")
_IGNORE_FILE_PATTERN = re.compile(r"#\s*composearr-ignore-file")


def parse_file_suppressions(raw_content: str) -> tuple[bool, set[str], dict[int, set[str]]]:
    """Parse inline suppression comments from a YAML file.

    Returns:
        (file_ignored, service_ignored_set, line_suppressions_dict)
        - file_ignored: True if # composearr-ignore-file found
        - service_ignored_set: service names marked with composearr-ignore-service
        - line_suppressions_dict: {line_number: set of rule IDs suppressed}
    """
    file_ignored = False
    line_suppressions: dict[int, set[str]] = {}

    for i, line in enumerate(raw_content.splitlines(), start=1):
        # File-level suppression
        if _IGNORE_FILE_PATTERN.search(line):
            file_ignored = True
            break

        # Line-level suppression
        match = _IGNORE_PATTERN.search(line)
        if match:
            rules_str = match.group(1).strip()
            rule_ids = set()
            for r in rules_str.split(","):
                r = r.strip()
                # Accept both rule names and IDs
                rule_id = _RULE_NAME_TO_ID.get(r, r.upper() if r.startswith("CA") or r.startswith("ca") else r)
                rule_ids.add(rule_id)

            # Suppression applies to the next non-comment line, or this line if inline
            line_suppressions[i] = rule_ids
            line_suppressions[i + 1] = rule_ids  # Also apply to next line

    return file_ignored, set(), line_suppressions
