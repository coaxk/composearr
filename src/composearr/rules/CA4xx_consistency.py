"""CA4xx — Consistency rules (includes cross-file PUID/PGID and UMASK checks)."""

from __future__ import annotations

from collections import defaultdict
from typing import TYPE_CHECKING

from composearr.models import LintIssue, Scope, Severity
from composearr.rules.base import BaseRule
from composearr.scanner.parser import find_line_number

if TYPE_CHECKING:
    from composearr.models import ComposeFile


def _get_env_value(service_config: dict, var_name: str) -> str | None:
    """Extract an environment variable value from a service config."""
    env = service_config.get("environment")
    if not env:
        return None

    if isinstance(env, list):
        for item in env:
            s = str(item)
            if "=" in s:
                key, _, value = s.partition("=")
                if key.strip() == var_name:
                    return value.strip()
    elif isinstance(env, dict):
        val = env.get(var_name)
        if val is not None:
            return str(val)

    return None


class PuidPgidMismatch(BaseRule):
    id = "CA401"
    name = "puid-pgid-mismatch"
    severity = Severity.ERROR
    scope = Scope.PROJECT
    description = "PUID/PGID values differ across services (cross-file)"
    category = "consistency"

    def check_service(self, service_name: str, service_config: dict, compose_file: ComposeFile) -> list[LintIssue]:
        return []

    def check_project(self, compose_files: list[ComposeFile]) -> list[LintIssue]:
        puid_groups: dict[str, list[str]] = defaultdict(list)

        for cf in compose_files:
            for svc_name, svc_config in cf.services.items():
                config = dict(svc_config) if hasattr(svc_config, "items") else {}
                puid = _get_env_value(config, "PUID")
                if puid:
                    puid_groups[puid].append(svc_name)

        if len(puid_groups) <= 1:
            return []

        # Build descriptive message
        parts = []
        for puid_val, services in sorted(puid_groups.items(), key=lambda x: -len(x[1])):
            svc_list = ", ".join(services[:5])
            if len(services) > 5:
                svc_list += f" +{len(services) - 5} more"
            parts.append(f"PUID={puid_val} in {svc_list}")

        message = "PUID values differ across stack: " + " | ".join(parts)
        return [
            self._make_issue(
                message,
                "cross-file",
                suggested_fix="All media stack services should use the same PUID",
                learn_more="https://trash-guides.info/Hardlinks/How-to-setup-for/Docker/",
            )
        ]


class UmaskInconsistent(BaseRule):
    id = "CA402"
    name = "umask-inconsistent"
    severity = Severity.WARNING
    scope = Scope.PROJECT
    description = "UMASK values differ across *arr services"
    category = "consistency"

    def check_service(self, service_name: str, service_config: dict, compose_file: ComposeFile) -> list[LintIssue]:
        return []

    def check_project(self, compose_files: list[ComposeFile]) -> list[LintIssue]:
        umask_groups: dict[str, list[str]] = defaultdict(list)

        for cf in compose_files:
            for svc_name, svc_config in cf.services.items():
                config = dict(svc_config) if hasattr(svc_config, "items") else {}
                umask = _get_env_value(config, "UMASK")
                if umask:
                    umask_groups[umask].append(svc_name)

        if len(umask_groups) <= 1:
            return []

        parts = []
        for umask_val, services in sorted(umask_groups.items(), key=lambda x: -len(x[1])):
            parts.append(f"UMASK={umask_val} in {', '.join(services)}")

        message = "UMASK inconsistent: " + " | ".join(parts)
        return [
            self._make_issue(
                message,
                "cross-file",
                suggested_fix="TRaSH recommends UMASK=002 for group write / hardlinks",
                learn_more="https://trash-guides.info/Hardlinks/How-to-setup-for/Docker/",
            )
        ]


class MissingTimezone(BaseRule):
    id = "CA403"
    name = "missing-timezone"
    severity = Severity.WARNING
    scope = Scope.SERVICE
    description = "TZ environment variable not set"
    category = "consistency"

    def check_service(
        self,
        service_name: str,
        service_config: dict,
        compose_file: ComposeFile,
    ) -> list[LintIssue]:
        tz = _get_env_value(service_config, "TZ")
        if tz is None:
            line = find_line_number(compose_file.raw_content, f"{service_name}:")
            return [
                self._make_issue(
                    "TZ environment variable not set",
                    str(compose_file.path),
                    line=line,
                    service=service_name,
                    fix_available=True,
                    suggested_fix="Add TZ environment variable (e.g. TZ=Australia/Sydney)",
                )
            ]
        return []
