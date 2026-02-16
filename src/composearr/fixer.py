"""Apply suggested fixes to compose files using ruamel.yaml for round-trip editing."""

from __future__ import annotations

import re
import shutil
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path

from ruamel.yaml import YAML

from composearr.models import LintIssue

yaml = YAML()
yaml.preserve_quotes = True


class FixResult:
    """Result of applying fixes."""

    __slots__ = ("applied", "skipped", "errors", "backup_paths", "verified_files", "verification_errors")

    def __init__(self) -> None:
        self.applied: int = 0
        self.skipped: int = 0
        self.errors: int = 0
        self.backup_paths: list[Path] = []
        self.verified_files: list[Path] = []
        self.verification_errors: list[tuple[Path, str]] = []


def verify_yaml_file(path: Path) -> tuple[bool, str]:
    """Re-read a YAML file and verify its structure is valid.

    Returns (ok, error_message). If ok is True, error_message is empty.
    """
    try:
        content = path.read_text(encoding="utf-8")
        data = yaml.load(content)
        if data is None:
            return False, "File parsed as empty/null"
        if not isinstance(data, dict):
            return False, f"Root element is {type(data).__name__}, expected mapping"
        if "services" not in data:
            return False, "Missing 'services' key"
        services = data["services"]
        if services is not None and not isinstance(services, dict):
            return False, f"'services' is {type(services).__name__}, expected mapping"
        return True, ""
    except Exception as e:
        return False, str(e)


@dataclass
class FilePreview:
    """Preview of changes for a single file."""

    file_path: Path
    original: str
    modified: str
    issues: list[LintIssue]
    fix_count: int


def preview_fixes(issues: list[LintIssue]) -> list[FilePreview]:
    """Generate previews of what fixes would change, without writing anything.

    Returns a list of FilePreview objects with before/after content.
    """
    from io import StringIO

    by_file: dict[str, list[LintIssue]] = defaultdict(list)
    for issue in issues:
        if issue.fix_available and issue.suggested_fix:
            by_file[issue.file_path].append(issue)

    previews: list[FilePreview] = []

    for file_path, file_issues in by_file.items():
        path = Path(file_path)
        if not path.is_file():
            continue

        try:
            original = path.read_text(encoding="utf-8")
            data = yaml.load(original)

            if data is None or "services" not in data:
                continue

            fix_count = 0
            for issue in file_issues:
                if _apply_single_fix(data, issue):
                    fix_count += 1

            if fix_count > 0:
                buf = StringIO()
                yaml.dump(data, buf)
                modified = buf.getvalue()

                previews.append(FilePreview(
                    file_path=path,
                    original=original,
                    modified=modified,
                    issues=file_issues,
                    fix_count=fix_count,
                ))

            # Re-load original data to undo in-memory changes
            # (yaml.load mutates data in-place, we need a fresh copy for the actual apply)
        except Exception:
            continue

    return previews


def apply_fixes(
    issues: list[LintIssue],
    root: Path,
    *,
    backup: bool = True,
) -> FixResult:
    """Apply fixes to compose files.

    Returns a FixResult with counts and backup file paths.
    """
    result = FixResult()

    # Group by file so we only read/write each file once
    by_file: dict[str, list[LintIssue]] = defaultdict(list)
    for issue in issues:
        if issue.fix_available and issue.suggested_fix:
            by_file[issue.file_path].append(issue)

    for file_path, file_issues in by_file.items():
        path = Path(file_path)
        if not path.is_file():
            result.errors += len(file_issues)
            continue

        try:
            content = path.read_text(encoding="utf-8")
            data = yaml.load(content)

            if data is None or "services" not in data:
                result.skipped += len(file_issues)
                continue

            if backup:
                bak_path = path.with_suffix(path.suffix + ".bak")
                shutil.copy2(path, bak_path)
                result.backup_paths.append(bak_path)

            modified = False
            for issue in file_issues:
                fix_ok = _apply_single_fix(data, issue)
                if fix_ok:
                    result.applied += 1
                    modified = True
                else:
                    result.skipped += 1

            if modified:
                with open(path, "w", encoding="utf-8", newline="") as f:
                    yaml.dump(data, f)

                # Verify the written file is structurally valid
                ok, err_msg = verify_yaml_file(path)
                if ok:
                    result.verified_files.append(path)
                else:
                    result.verification_errors.append((path, err_msg))

        except Exception:
            result.errors += len(file_issues)

    return result


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
    elif rule_id == "CA404":
        return _fix_duplicate_env(services, service)
    elif rule_id == "CA501":
        return _fix_memory_limit(services, service)
    elif rule_id == "CA502":
        return _fix_cpu_limit(services, service)
    elif rule_id == "CA504":
        return _fix_logging_config(services, service)
    elif rule_id == "CA505":
        return _fix_log_rotation(services, service)
    elif rule_id == "CA702":
        return _fix_undefined_volume(data, issue)
    elif rule_id == "CA802":
        return _fix_privileged_mode(services, service)
    elif rule_id == "CA804":
        return _fix_no_new_privileges(services, service)
    elif rule_id == "CA902":
        return _fix_restart_always(services, service)
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


def _detect_tz(services: dict, skip_service: str | None = None) -> str:
    """Detect timezone from sibling services, system, or fall back to Etc/UTC."""
    # Check sibling services for an existing TZ
    for svc_name, svc_config in services.items():
        if svc_name == skip_service or not isinstance(svc_config, dict):
            continue
        env = svc_config.get("environment")
        if isinstance(env, dict) and "TZ" in env:
            return str(env["TZ"])
        if isinstance(env, list):
            for entry in env:
                s = str(entry)
                if s.startswith("TZ=") and len(s) > 3:
                    return s[3:]

    # Try system timezone
    try:
        import time
        local_tz = time.tzname[0]
        # tzname gives abbreviations like "EST" — not useful for TZ env var
        # Try reading /etc/timezone or using datetime
        from datetime import datetime, timezone
        from zoneinfo import ZoneInfo
        # On Python 3.9+ we can detect the local zone
        import sys
        if sys.platform == "win32":
            # Windows: use tzlocal if available, else fall back
            try:
                from tzlocal import get_localzone
                return str(get_localzone())
            except ImportError:
                pass
        else:
            # Linux/macOS: read /etc/timezone or /etc/localtime
            from pathlib import Path
            tz_file = Path("/etc/timezone")
            if tz_file.is_file():
                tz_val = tz_file.read_text().strip()
                if tz_val:
                    return tz_val
    except Exception:
        pass

    return "Etc/UTC"


def _fix_missing_tz(services: dict, service: str | None) -> bool:
    """Add TZ environment variable to a service."""
    if not service:
        return False

    svc_config = services.get(service)
    if not svc_config:
        return False

    tz_value = _detect_tz(services, skip_service=service)
    env = svc_config.get("environment")

    if env is None:
        svc_config["environment"] = {"TZ": tz_value}
        return True

    if isinstance(env, dict):
        if "TZ" not in env:
            env["TZ"] = tz_value
            return True
    elif isinstance(env, list):
        has_tz = any(
            str(e).startswith("TZ=") for e in env
        )
        if not has_tz:
            env.append(f"TZ={tz_value}")
            return True

    return False


def _fix_duplicate_env(services: dict, service: str | None) -> bool:
    """Remove duplicate environment variables, keeping the last value."""
    if not service:
        return False

    svc_config = services.get(service)
    if not svc_config:
        return False

    env = svc_config.get("environment")
    if not isinstance(env, list):
        return False

    seen: dict[str, int] = {}
    duplicates_found = False
    for i, entry in enumerate(env):
        s = str(entry)
        if "=" in s:
            key = s.partition("=")[0].strip()
            if key in seen:
                duplicates_found = True
            seen[key] = i

    if not duplicates_found:
        return False

    # Keep only the last occurrence of each key
    keep_indices = set(seen.values())
    svc_config["environment"] = [e for i, e in enumerate(env) if i in keep_indices]
    return True


def _ensure_deploy_limits(svc_config: dict) -> dict:
    """Ensure deploy.resources.limits exists and return the limits dict."""
    if "deploy" not in svc_config:
        svc_config["deploy"] = {}
    deploy = svc_config["deploy"]
    if not isinstance(deploy, dict):
        return {}
    if "resources" not in deploy:
        deploy["resources"] = {}
    resources = deploy["resources"]
    if not isinstance(resources, dict):
        return {}
    if "limits" not in resources:
        resources["limits"] = {}
    limits = resources["limits"]
    if not isinstance(limits, dict):
        return {}
    return limits


def _fix_memory_limit(services: dict, service: str | None) -> bool:
    """Add memory limit using known service profile."""
    if not service:
        return False

    svc_config = services.get(service)
    if not svc_config:
        return False

    limits = _ensure_deploy_limits(svc_config)
    if not isinstance(limits, dict):
        return False

    if limits.get("memory"):
        return False

    from composearr.data.known_services import detect_service
    image = svc_config.get("image", "")
    profile = detect_service(image)
    limits["memory"] = profile.typical_memory if profile else "256M"
    return True


def _fix_cpu_limit(services: dict, service: str | None) -> bool:
    """Add CPU limit using known service profile."""
    if not service:
        return False

    svc_config = services.get(service)
    if not svc_config:
        return False

    limits = _ensure_deploy_limits(svc_config)
    if not isinstance(limits, dict):
        return False

    if limits.get("cpus"):
        return False

    from composearr.data.known_services import detect_service
    image = svc_config.get("image", "")
    profile = detect_service(image)
    limits["cpus"] = profile.typical_cpu if profile else "0.5"
    return True


def _fix_logging_config(services: dict, service: str | None) -> bool:
    """Add logging configuration with sensible defaults."""
    if not service:
        return False

    svc_config = services.get(service)
    if not svc_config:
        return False

    if "logging" in svc_config:
        return False

    svc_config["logging"] = {
        "driver": "json-file",
        "options": {
            "max-size": "10m",
            "max-file": "3",
        },
    }
    return True


def _fix_log_rotation(services: dict, service: str | None) -> bool:
    """Add rotation limits to existing logging config."""
    if not service:
        return False

    svc_config = services.get(service)
    if not svc_config:
        return False

    logging = svc_config.get("logging")
    if not isinstance(logging, dict):
        return False

    if "options" not in logging:
        logging["options"] = {}
    options = logging["options"]
    if not isinstance(options, dict):
        return False

    modified = False
    if "max-size" not in options:
        options["max-size"] = "10m"
        modified = True
    if "max-file" not in options:
        options["max-file"] = "3"
        modified = True

    return modified


def _fix_privileged_mode(services: dict, service: str | None) -> bool:
    """Remove privileged: true from a service."""
    if not service:
        return False
    svc_config = services.get(service)
    if not svc_config or not isinstance(svc_config, dict):
        return False
    if "privileged" not in svc_config:
        return False
    del svc_config["privileged"]
    return True


def _fix_no_new_privileges(services: dict, service: str | None) -> bool:
    """Add no-new-privileges:true to security_opt."""
    if not service:
        return False
    svc_config = services.get(service)
    if not svc_config or not isinstance(svc_config, dict):
        return False
    security_opt = svc_config.get("security_opt", [])
    if not isinstance(security_opt, list):
        security_opt = []
    if any("no-new-privileges:true" in str(opt) for opt in security_opt):
        return False
    security_opt.append("no-new-privileges:true")
    svc_config["security_opt"] = security_opt
    return True


def _fix_restart_always(services: dict, service: str | None) -> bool:
    """Change restart: always to restart: unless-stopped."""
    if not service:
        return False
    svc_config = services.get(service)
    if not svc_config or not isinstance(svc_config, dict):
        return False
    if svc_config.get("restart") != "always":
        return False
    svc_config["restart"] = "unless-stopped"
    return True


def _fix_undefined_volume(data: dict, issue: LintIssue) -> bool:
    """Add a missing volume definition to the top-level volumes section."""
    if not issue.message:
        return False

    # Extract volume name from message: "Volume 'foo' referenced but..."
    match = re.match(r"Volume '([^']+)' referenced", issue.message)
    if not match:
        return False

    volume_name = match.group(1)

    # Ensure top-level volumes section exists
    if "volumes" not in data:
        data["volumes"] = {}
    volumes = data["volumes"]
    if volumes is None:
        data["volumes"] = {}
        volumes = data["volumes"]
    if not isinstance(volumes, dict):
        return False

    if volume_name in volumes:
        return False  # Already defined

    volumes[volume_name] = None  # Docker default (local driver)
    return True
