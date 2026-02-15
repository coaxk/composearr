"""CA3xx — Network topology rules (cross-file network reachability checks)."""

from __future__ import annotations

from collections import defaultdict
from typing import TYPE_CHECKING

from composearr.models import LintIssue, Scope, Severity
from composearr.rules.base import BaseRule
from composearr.scanner.parser import find_line_number

if TYPE_CHECKING:
    from composearr.models import ComposeFile


# ── Topology helpers ──────────────────────────────────────────


def _get_network_mode(svc_config: dict) -> str | None:
    """Return network_mode value or None if not set."""
    return svc_config.get("network_mode")


def _get_service_networks(svc_config: dict) -> list[str]:
    """Return list of network names a service belongs to."""
    networks = svc_config.get("networks")
    if networks is None:
        return []
    if isinstance(networks, list):
        return [str(n) for n in networks]
    if isinstance(networks, dict):
        return list(networks.keys())
    return []


def _get_depends_on(svc_config: dict) -> list[str]:
    """Return list of service dependencies."""
    deps = svc_config.get("depends_on")
    if deps is None:
        return []
    if isinstance(deps, list):
        return [str(d) for d in deps]
    if isinstance(deps, dict):
        return list(deps.keys())
    return []


def build_network_graph(compose_files: list[ComposeFile]) -> dict:
    """Build a network topology graph from all compose files.

    Returns a dict with:
        services: {name: {networks, network_mode, depends_on, file, config}}
        networks: {name: {services: [svc_names], file, internal}}
    """
    services: dict[str, dict] = {}
    networks: dict[str, dict] = defaultdict(lambda: {"services": [], "file": "", "internal": False})

    for cf in compose_files:
        # Collect top-level network definitions
        file_networks = cf.data.get("networks") or {}
        for net_name, net_config in file_networks.items():
            net_config = net_config or {}
            networks[net_name]["file"] = str(cf.path)
            if isinstance(net_config, dict) and net_config.get("internal"):
                networks[net_name]["internal"] = True

        for svc_name, svc_config in cf.services.items():
            svc_config = svc_config or {}
            mode = _get_network_mode(svc_config)
            svc_networks = _get_service_networks(svc_config)
            deps = _get_depends_on(svc_config)

            services[svc_name] = {
                "networks": svc_networks,
                "network_mode": mode,
                "depends_on": deps,
                "file": str(cf.path),
                "config": svc_config,
            }

            for net in svc_networks:
                networks[net]["services"].append(svc_name)

    return {"services": services, "networks": dict(networks)}


def can_communicate(graph: dict, svc_a: str, svc_b: str) -> bool:
    """Check if two services can communicate based on network topology."""
    services = graph["services"]
    if svc_a not in services or svc_b not in services:
        return False

    info_a = services[svc_a]
    info_b = services[svc_b]

    mode_a = info_a["network_mode"]
    mode_b = info_b["network_mode"]

    # network_mode: none = isolated
    if mode_a == "none" or mode_b == "none":
        return False

    # network_mode: host — both on host can communicate
    if mode_a == "host" and mode_b == "host":
        return True

    # network_mode: service:X — shares network with X
    if mode_a and mode_a.startswith("service:"):
        target = mode_a.split(":", 1)[1]
        if target == svc_b or can_communicate(graph, target, svc_b):
            return True
    if mode_b and mode_b.startswith("service:"):
        target = mode_b.split(":", 1)[1]
        if target == svc_a or can_communicate(graph, target, svc_a):
            return True

    nets_a = set(info_a["networks"])
    nets_b = set(info_b["networks"])

    # If neither has explicit networks and neither has network_mode,
    # they share the default bridge (can communicate)
    if not nets_a and not mode_a and not nets_b and not mode_b:
        return True

    # If one has host mode, it can reach services on default bridge
    # (when the other has no explicit networks/mode)
    if mode_a == "host" and not nets_b and not mode_b:
        return True
    if mode_b == "host" and not nets_a and not mode_a:
        return True

    # Shared custom network = can communicate
    if nets_a & nets_b:
        return True

    return False


# ── Rules ─────────────────────────────────────────────────────


class UnreachableDependency(BaseRule):
    id = "CA302"
    name = "unreachable-dependency"
    severity = Severity.ERROR
    scope = Scope.PROJECT
    description = "Service depends_on a service it cannot reach via network"
    category = "networking"

    def check_service(self, service_name: str, service_config: dict, compose_file: ComposeFile) -> list[LintIssue]:
        return []

    def check_project(self, compose_files: list[ComposeFile]) -> list[LintIssue]:
        graph = build_network_graph(compose_files)
        issues: list[LintIssue] = []

        for svc_name, info in graph["services"].items():
            for dep in info["depends_on"]:
                if dep not in graph["services"]:
                    continue  # Missing dependency is a compose error, not ours
                if not can_communicate(graph, svc_name, dep):
                    dep_nets = graph["services"][dep]["networks"]
                    dep_mode = graph["services"][dep]["network_mode"]
                    svc_nets = info["networks"]
                    svc_mode = info["network_mode"]

                    detail_parts = []
                    if svc_mode:
                        detail_parts.append(f"{svc_name} uses network_mode: {svc_mode}")
                    elif svc_nets:
                        detail_parts.append(f"{svc_name} is on: {', '.join(svc_nets)}")
                    if dep_mode:
                        detail_parts.append(f"{dep} uses network_mode: {dep_mode}")
                    elif dep_nets:
                        detail_parts.append(f"{dep} is on: {', '.join(dep_nets)}")
                    detail = " | ".join(detail_parts) if detail_parts else "different networks"

                    # Find line
                    line = find_line_number(info["file"], "depends_on")

                    # Suggest fix
                    if dep_nets:
                        fix_net = dep_nets[0]
                        fix = f"Add {svc_name} to the same network:\n    networks:\n      - {fix_net}"
                    else:
                        fix = f"Put both services on a shared network:\n    networks:\n      - shared"

                    issues.append(
                        self._make_issue(
                            f"{svc_name} depends on {dep} but cannot reach it ({detail})",
                            info["file"],
                            line=line,
                            service=svc_name,
                            fix_available=False,
                            suggested_fix=fix,
                        )
                    )
        return issues


class IsolatedServiceWithPorts(BaseRule):
    id = "CA303"
    name = "isolated-service-ports"
    severity = Severity.WARNING
    scope = Scope.PROJECT
    description = "Service with network_mode: none exposes ports (unreachable)"
    category = "networking"

    def check_service(self, service_name: str, service_config: dict, compose_file: ComposeFile) -> list[LintIssue]:
        return []

    def check_project(self, compose_files: list[ComposeFile]) -> list[LintIssue]:
        issues: list[LintIssue] = []
        for cf in compose_files:
            for svc_name, svc_config in cf.services.items():
                svc_config = svc_config or {}
                mode = _get_network_mode(svc_config)
                ports = svc_config.get("ports", [])
                if mode == "none" and ports:
                    line = find_line_number(str(cf.path), "network_mode")
                    issues.append(
                        self._make_issue(
                            f"{svc_name} has network_mode: none but exposes ports — ports are unreachable",
                            str(cf.path),
                            line=line,
                            service=svc_name,
                            suggested_fix="Remove ports or change network_mode",
                        )
                    )
        return issues
