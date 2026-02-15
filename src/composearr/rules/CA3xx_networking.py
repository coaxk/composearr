"""CA3xx — Networking rules (includes cross-file port conflict detection)."""

from __future__ import annotations

from collections import defaultdict
from typing import TYPE_CHECKING

from composearr.models import LintIssue, PortMapping, Scope, Severity
from composearr.rules.base import BaseRule
from composearr.scanner.parser import find_line_number
from composearr.scanner.port_parser import parse_port_mapping

if TYPE_CHECKING:
    from composearr.models import ComposeFile


class PortConflict(BaseRule):
    id = "CA301"
    name = "port-conflict"
    severity = Severity.ERROR
    scope = Scope.PROJECT
    description = "Same host port used by multiple services (cross-file)"
    category = "networking"

    def check_service(self, service_name: str, service_config: dict, compose_file: ComposeFile) -> list[LintIssue]:
        return []  # This is a project-scope rule

    def check_project(self, compose_files: list[ComposeFile]) -> list[LintIssue]:
        # Collect all port mappings
        port_users: dict[tuple[int, str, str], list[tuple[str, str]]] = defaultdict(list)

        for cf in compose_files:
            for svc_name, svc_config in cf.services.items():
                ports = svc_config.get("ports", [])
                if not ports:
                    continue
                for port_spec in ports:
                    for pm in parse_port_mapping(port_spec, str(cf.path), svc_name):
                        key = (pm.host_port, pm.protocol, pm.host_ip)
                        port_users[key].append((svc_name, str(cf.path)))

        issues: list[LintIssue] = []
        for (port, proto, ip), users in port_users.items():
            if len(users) <= 1:
                continue

            services_str = ", ".join(f"{svc} ({path.split('/')[-2] if '/' in path else path})" for svc, path in users)
            issues.append(
                self._make_issue(
                    f"Port {port}/{proto} used by multiple services: {services_str}",
                    users[0][1],
                    suggested_fix=f"Change one service to use a different host port",
                )
            )

        return issues
