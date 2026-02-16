"""CA3xx — Networking rules (includes cross-file port conflict detection)."""

from __future__ import annotations

from collections import defaultdict
from typing import TYPE_CHECKING

from composearr.models import LintIssue, PortMapping, Scope, Severity
from composearr.rules.base import BaseRule
from composearr.scanner.parser import find_line_number, find_service_line
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


class DNSConfiguration(BaseRule):
    """Flag DNS configuration issues in containers."""

    id = "CA304"
    name = "dns-configuration"
    severity = Severity.WARNING
    scope = Scope.SERVICE
    description = "DNS configuration issue detected"
    category = "networking"

    def check_service(
        self,
        service_name: str,
        service_config: dict,
        compose_file: ComposeFile,
    ) -> list[LintIssue]:
        issues: list[LintIssue] = []
        dns = service_config.get("dns")
        network_mode = service_config.get("network_mode")
        line = find_service_line(compose_file.raw_content, service_name)

        # DNS config is ignored in host network mode
        if network_mode == "host" and dns:
            issues.append(self._make_issue(
                message="DNS configuration is ignored in host network mode",
                file_path=str(compose_file.path),
                line=line,
                service=service_name,
                suggested_fix=(
                    "Remove the dns: setting (host mode uses host DNS)\n"
                    "or change network_mode to bridge"
                ),
                learn_more="In host mode, the container uses the host's networking stack directly",
            ))

        # DNS config ignored with network_mode: none
        if network_mode == "none" and dns:
            issues.append(self._make_issue(
                message="DNS configuration is useless with network_mode: none",
                file_path=str(compose_file.path),
                line=line,
                service=service_name,
                suggested_fix="Remove dns: (no network = no DNS resolution)",
            ))

        # Check for common DNS problems
        if isinstance(dns, list):
            for server in dns:
                server_str = str(server)
                if server_str in ("127.0.0.1", "localhost", "::1"):
                    issues.append(self._make_issue(
                        message=f"DNS points to localhost ({server_str}) — may not resolve inside container",
                        file_path=str(compose_file.path),
                        line=line,
                        service=service_name,
                        severity=Severity.INFO,
                        suggested_fix=(
                            "Use the Docker host gateway or a public DNS:\n"
                            "dns:\n  - 8.8.8.8\n  - 1.1.1.1"
                        ),
                        learn_more="127.0.0.1 inside a container refers to the container itself, not the host",
                    ))
        elif isinstance(dns, str):
            if dns in ("127.0.0.1", "localhost", "::1"):
                issues.append(self._make_issue(
                    message=f"DNS points to localhost ({dns}) — may not resolve inside container",
                    file_path=str(compose_file.path),
                    line=line,
                    service=service_name,
                    severity=Severity.INFO,
                    suggested_fix="Use a public DNS: dns: 8.8.8.8",
                    learn_more="127.0.0.1 inside a container refers to the container itself, not the host",
                ))

        return issues

    def _make_issue(self, *, message, file_path, line, service,
                    severity=None, suggested_fix=None, learn_more=None,
                    fix_available=False):
        """Allow per-issue severity override for INFO-level localhost warnings."""
        return LintIssue(
            rule_id=self.id,
            rule_name=self.name,
            severity=severity or self.severity,
            message=message,
            file_path=file_path,
            line=line,
            service=service,
            fix_available=fix_available,
            suggested_fix=suggested_fix,
            learn_more=learn_more,
        )
