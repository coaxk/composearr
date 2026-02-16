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
        all_used_ports: set[int] = set()

        for cf in compose_files:
            for svc_name, svc_config in cf.services.items():
                ports = svc_config.get("ports", [])
                if not ports:
                    continue
                for port_spec in ports:
                    for pm in parse_port_mapping(port_spec, str(cf.path), svc_name):
                        key = (pm.host_port, pm.protocol, pm.host_ip)
                        port_users[key].append((svc_name, str(cf.path)))
                        all_used_ports.add(pm.host_port)

        issues: list[LintIssue] = []
        for (port, proto, ip), users in port_users.items():
            if len(users) <= 1:
                continue

            services_str = ", ".join(f"{svc} (in {path})" for svc, path in users)
            next_port = self._find_next_port(port, all_used_ports)
            fix = f"Change one service to port {next_port}:\n    ports:\n      - \"{next_port}:{port}\""
            issues.append(
                self._make_issue(
                    f"Port {port}/{proto} used by multiple services: {services_str}",
                    users[0][1],
                    suggested_fix=fix,
                )
            )

        return issues

    @staticmethod
    def _find_next_port(base_port: int, used_ports: set[int]) -> int:
        """Find next available port starting from base."""
        port = base_port + 1
        while port in used_ports and port < 65535:
            port += 1
        return port
