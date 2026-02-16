"""CA5xx — Resource and operational rules."""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

from composearr.data.known_services import detect_service
from composearr.models import LintIssue, Scope, Severity
from composearr.rules.base import BaseRule
from composearr.scanner.parser import find_line_number

if TYPE_CHECKING:
    from composearr.models import ComposeFile


def _parse_memory(value: str) -> int | None:
    """Parse a Docker memory string (e.g. '512M', '2G') to bytes."""
    if not value:
        return None
    value = str(value).strip().upper()
    match = re.match(r"^(\d+(?:\.\d+)?)\s*(B|K|KB|M|MB|G|GB|T|TB)?$", value)
    if not match:
        return None
    num = float(match.group(1))
    unit = match.group(2) or "B"
    multipliers = {"B": 1, "K": 1024, "KB": 1024, "M": 1024**2, "MB": 1024**2,
                   "G": 1024**3, "GB": 1024**3, "T": 1024**4, "TB": 1024**4}
    return int(num * multipliers.get(unit, 1))


def _parse_cpus(value: str | int | float) -> float | None:
    """Parse a Docker CPU limit (e.g. '0.5', '2.0', 2) to float."""
    try:
        return float(value)
    except (ValueError, TypeError):
        return None


def _get_deploy_limits(service_config: dict) -> dict:
    """Extract deploy.resources.limits from a service config."""
    deploy = service_config.get("deploy", {})
    if not isinstance(deploy, dict):
        return {}
    resources = deploy.get("resources", {})
    if not isinstance(resources, dict):
        return {}
    limits = resources.get("limits", {})
    if not isinstance(limits, dict):
        return {}
    return limits


class MissingMemoryLimit(BaseRule):
    id = "CA501"
    name = "missing-memory-limit"
    severity = Severity.WARNING
    scope = Scope.SERVICE
    description = "No memory limit defined (unbounded resource usage)"
    category = "resources"

    def check_service(
        self,
        service_name: str,
        service_config: dict,
        compose_file: ComposeFile,
    ) -> list[LintIssue]:
        limits = _get_deploy_limits(service_config)
        if limits.get("memory"):
            return []

        line = find_line_number(compose_file.raw_content, f"{service_name}:")
        image = service_config.get("image", "")
        profile = detect_service(image)
        suggested_mem = profile.typical_memory if profile else "256M"
        app_name = profile.name if profile else "this service"

        return [
            self._make_issue(
                "No memory limit defined — container can consume unlimited RAM",
                str(compose_file.path),
                line=line,
                service=service_name,
                fix_available=True,
                suggested_fix=(
                    f"Add memory limit to prevent resource exhaustion:\n"
                    f"  deploy:\n"
                    f"    resources:\n"
                    f"      limits:\n"
                    f"        memory: {suggested_mem}\n"
                    f"\n"
                    f"Suggested {suggested_mem} for {app_name}. "
                    f"Adjust based on your actual usage."
                ),
            )
        ]


class MissingCpuLimit(BaseRule):
    id = "CA502"
    name = "missing-cpu-limit"
    severity = Severity.WARNING
    scope = Scope.SERVICE
    description = "No CPU limit defined (can starve other containers)"
    category = "resources"

    def check_service(
        self,
        service_name: str,
        service_config: dict,
        compose_file: ComposeFile,
    ) -> list[LintIssue]:
        limits = _get_deploy_limits(service_config)
        if limits.get("cpus"):
            return []

        line = find_line_number(compose_file.raw_content, f"{service_name}:")
        image = service_config.get("image", "")
        profile = detect_service(image)
        suggested_cpu = profile.typical_cpu if profile else "0.5"
        app_name = profile.name if profile else "this service"

        return [
            self._make_issue(
                "No CPU limit defined — container can starve other services",
                str(compose_file.path),
                line=line,
                service=service_name,
                fix_available=True,
                suggested_fix=(
                    f"Add CPU limit to prevent resource starvation:\n"
                    f"  deploy:\n"
                    f"    resources:\n"
                    f"      limits:\n"
                    f"        cpus: '{suggested_cpu}'\n"
                    f"\n"
                    f"Suggested {suggested_cpu} CPUs for {app_name}. "
                    f"Adjust based on your host capacity."
                ),
            )
        ]


class ResourceLimitsUnusual(BaseRule):
    id = "CA503"
    name = "resource-limits-unusual"
    severity = Severity.INFO
    scope = Scope.SERVICE
    description = "Resource limits seem unusual for this application"
    category = "resources"

    def check_service(
        self,
        service_name: str,
        service_config: dict,
        compose_file: ComposeFile,
    ) -> list[LintIssue]:
        limits = _get_deploy_limits(service_config)
        if not limits:
            return []  # CA501/CA502 handle missing limits

        image = service_config.get("image", "")
        profile = detect_service(image)
        if not profile:
            return []  # Can only compare against known apps

        issues: list[LintIssue] = []
        line = find_line_number(compose_file.raw_content, f"{service_name}:")

        # Check memory
        current_mem = limits.get("memory")
        if current_mem:
            current_bytes = _parse_memory(str(current_mem))
            typical_bytes = _parse_memory(profile.typical_memory)
            if current_bytes and typical_bytes:
                ratio = current_bytes / typical_bytes
                if ratio > 4.0:
                    issues.append(self._make_issue(
                        f"Memory limit {current_mem} is {ratio:.0f}x higher than typical "
                        f"for {profile.name} ({profile.typical_memory})",
                        str(compose_file.path),
                        line=line,
                        service=service_name,
                        suggested_fix=(
                            f"Typical memory for {profile.name}: {profile.typical_memory}. "
                            f"Current: {current_mem}. Review if this is intentional."
                        ),
                    ))
                elif ratio < 0.25:
                    issues.append(self._make_issue(
                        f"Memory limit {current_mem} is very low for {profile.name} "
                        f"(typical: {profile.typical_memory}) — may cause OOM kills",
                        str(compose_file.path),
                        line=line,
                        service=service_name,
                        suggested_fix=(
                            f"Typical memory for {profile.name}: {profile.typical_memory}. "
                            f"Current: {current_mem}. Consider increasing to avoid OOM."
                        ),
                    ))

        # Check CPU
        current_cpu = limits.get("cpus")
        if current_cpu:
            current_val = _parse_cpus(current_cpu)
            typical_val = _parse_cpus(profile.typical_cpu)
            if current_val and typical_val:
                ratio = current_val / typical_val
                if ratio > 4.0:
                    issues.append(self._make_issue(
                        f"CPU limit {current_cpu} is {ratio:.0f}x higher than typical "
                        f"for {profile.name} ({profile.typical_cpu})",
                        str(compose_file.path),
                        line=line,
                        service=service_name,
                        suggested_fix=(
                            f"Typical CPU for {profile.name}: {profile.typical_cpu}. "
                            f"Current: {current_cpu}. Review if this is intentional."
                        ),
                    ))

        return issues


class NoLoggingConfig(BaseRule):
    id = "CA504"
    name = "no-logging-config"
    severity = Severity.WARNING
    scope = Scope.SERVICE
    description = "No logging configuration (defaults to unbounded json-file)"
    category = "resources"

    def check_service(
        self,
        service_name: str,
        service_config: dict,
        compose_file: ComposeFile,
    ) -> list[LintIssue]:
        logging = service_config.get("logging")
        if logging:
            return []

        line = find_line_number(compose_file.raw_content, f"{service_name}:")

        return [
            self._make_issue(
                "No logging configuration — defaults to unbounded json-file, can fill disk",
                str(compose_file.path),
                line=line,
                service=service_name,
                fix_available=True,
                suggested_fix=(
                    "Add logging configuration to prevent disk fill:\n"
                    "  logging:\n"
                    "    driver: json-file\n"
                    "    options:\n"
                    '      max-size: "10m"\n'
                    '      max-file: "3"\n'
                    "\n"
                    "Limits each container's logs to 30MB total (10MB x 3 files)."
                ),
            )
        ]


class NoLogRotation(BaseRule):
    id = "CA505"
    name = "no-log-rotation"
    severity = Severity.WARNING
    scope = Scope.SERVICE
    description = "Logging driver configured but no rotation limits"
    category = "resources"

    def check_service(
        self,
        service_name: str,
        service_config: dict,
        compose_file: ComposeFile,
    ) -> list[LintIssue]:
        logging = service_config.get("logging")
        if not logging or not isinstance(logging, dict):
            return []  # CA504 handles missing logging entirely

        driver = logging.get("driver", "json-file")
        if driver not in ("json-file", "local"):
            return []  # Other drivers (syslog, fluentd, etc.) handle rotation differently

        options = logging.get("options", {})
        if not isinstance(options, dict):
            options = {}

        has_max_size = "max-size" in options
        has_max_file = "max-file" in options

        if has_max_size and has_max_file:
            return []

        line = find_line_number(compose_file.raw_content, f"{service_name}:")
        missing = []
        if not has_max_size:
            missing.append("max-size")
        if not has_max_file:
            missing.append("max-file")

        return [
            self._make_issue(
                f"Logging driver '{driver}' has no rotation limits "
                f"(missing: {', '.join(missing)}) — logs can grow unbounded",
                str(compose_file.path),
                line=line,
                service=service_name,
                fix_available=True,
                suggested_fix=(
                    "Add rotation limits to your logging configuration:\n"
                    "  logging:\n"
                    f"    driver: {driver}\n"
                    "    options:\n"
                    '      max-size: "10m"\n'
                    '      max-file: "3"'
                ),
            )
        ]
