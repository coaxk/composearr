"""Apply suggested fixes to compose files using ruamel.yaml for round-trip editing."""

from __future__ import annotations

import re
import shutil
from collections import defaultdict
from pathlib import Path

from ruamel.yaml import YAML

from composearr.models import LintIssue

yaml = YAML()
yaml.preserve_quotes = True


def apply_fixes(
    issues: list[LintIssue],
    root: Path,
    *,
    backup: bool = True,
) -> tuple[int, int, int]:
    """Apply fixes to compose files.

    Returns (applied, skipped, errors) counts.
    """
    applied = 0
    skipped = 0
    errors = 0

    # Group by file so we only read/write each file once
    by_file: dict[str, list[LintIssue]] = defaultdict(list)
    for issue in issues:
        if issue.fix_available and issue.suggested_fix:
            by_file[issue.file_path].append(issue)

    for file_path, file_issues in by_file.items():
        path = Path(file_path)
        if not path.is_file():
            errors += len(file_issues)
            continue

        try:
            content = path.read_text(encoding="utf-8")
            data = yaml.load(content)

            if data is None or "services" not in data:
                skipped += len(file_issues)
                continue

            if backup:
                shutil.copy2(path, path.with_suffix(path.suffix + ".bak"))

            modified = False
            for issue in file_issues:
                result = _apply_single_fix(data, issue)
                if result:
                    applied += 1
                    modified = True
                else:
                    skipped += 1

            if modified:
                with open(path, "w", encoding="utf-8") as f:
                    yaml.dump(data, f)

        except Exception:
            errors += len(file_issues)

    return applied, skipped, errors


def _apply_single_fix(data: dict, issue: LintIssue) -> bool:
    """Apply a single fix to the parsed YAML data. Returns True if applied."""
    services = data.get("services", {})
    if not services:
        return False

    rule_id = issue.rule_id
    service = issue.service

    if rule_id == "CA001":
        return _fix_image_tag(services, issue)
    elif rule_id == "CA203":
        return _fix_restart_policy(services, service)
    elif rule_id == "CA403":
        return _fix_missing_tz(services, service)
    elif rule_id == "CA101":
        # Moving secrets to .env is too complex for auto-fix
        return False
    elif rule_id == "CA201":
        # Adding healthchecks requires service-specific knowledge
        return False

    return False


def _fix_image_tag(services: dict, issue: LintIssue) -> bool:
    """Pin image to suggested tag."""
    if not issue.service or not issue.suggested_fix:
        return False

    svc_config = services.get(issue.service)
    if not svc_config or "image" not in svc_config:
        return False

    # Extract the recommended image:tag from the suggestion
    # Format: "Pin to image:tag (reason) — why"
    match = re.match(r"Pin to (\S+)", issue.suggested_fix)
    if not match:
        return False

    new_image = match.group(1)
    svc_config["image"] = new_image
    return True


def _fix_restart_policy(services: dict, service: str | None) -> bool:
    """Add restart: unless-stopped to a service."""
    if not service:
        return False

    svc_config = services.get(service)
    if not svc_config:
        return False

    if "restart" in svc_config:
        return False  # Already has a restart policy

    svc_config["restart"] = "unless-stopped"
    return True


def _fix_missing_tz(services: dict, service: str | None) -> bool:
    """Add TZ environment variable to a service."""
    if not service:
        return False

    svc_config = services.get(service)
    if not svc_config:
        return False

    env = svc_config.get("environment")

    if env is None:
        svc_config["environment"] = {"TZ": "Etc/UTC"}
        return True

    if isinstance(env, dict):
        if "TZ" not in env:
            env["TZ"] = "Etc/UTC"
            return True
    elif isinstance(env, list):
        has_tz = any(
            str(e).startswith("TZ=") for e in env
        )
        if not has_tz:
            env.append("TZ=Etc/UTC")
            return True

    return False
