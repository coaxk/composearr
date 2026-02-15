"""Network topology visualization command."""

from __future__ import annotations

from pathlib import Path

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich import box
from rich.style import Style
from rich.text import Text

from composearr.engine import run_audit
from composearr.rules.CA3xx_network_topology import (
    build_network_graph,
    can_communicate,
)


# ── Color tokens ──────────────────────────────────────────────

C_TEAL = "#2dd4bf"
C_MUTED = "#71717a"
C_OK = "#22c55e"
C_ERR = "#ef4444"
C_WARN = "#f59e0b"
C_TEXT = "#fafafa"
C_INFO = "#3b82f6"


def render_topology(root: Path, console: Console) -> None:
    """Render a visual network topology map."""
    from composearr.scanner.discovery import discover_compose_files
    from composearr.scanner.parser import parse_compose_file

    paths, _ = discover_compose_files(root)
    compose_files = [parse_compose_file(p) for p in paths]
    compose_files = [cf for cf in compose_files if not cf.parse_error]

    if not compose_files:
        console.print(f"  [{C_MUTED}]No compose files found[/]")
        return

    graph = build_network_graph(compose_files)
    services = graph["services"]
    networks = graph["networks"]

    if not services:
        console.print(f"  [{C_MUTED}]No services found[/]")
        return

    # ── Network overview table ────────────────────────────────
    console.print()
    console.print(f"  [{C_TEXT}]Network Topology[/]  [{C_MUTED}]{len(services)} services, {len(networks)} networks[/]")
    console.print()

    # Show networks and their members
    net_table = Table(
        box=box.SIMPLE_HEAD,
        border_style=Style(color="#27272a"),
        header_style=C_MUTED,
        padding=(0, 2),
        show_edge=False,
    )
    net_table.add_column("", width=2)
    net_table.add_column("NETWORK", style=f"bold {C_TEXT}", no_wrap=True)
    net_table.add_column("TYPE", style=C_MUTED, no_wrap=True)
    net_table.add_column("SERVICES", style=C_TEXT)

    # Services on default bridge (no explicit network, no network_mode)
    default_services = [
        name for name, info in services.items()
        if not info["networks"] and not info["network_mode"]
    ]
    if default_services:
        net_table.add_row(
            f"[{C_OK}]\u25cf[/]",
            "default",
            "bridge",
            ", ".join(sorted(default_services)),
        )

    # Named networks
    for net_name in sorted(networks.keys()):
        net_info = networks[net_name]
        members = net_info["services"]
        if not members:
            continue
        net_type = "internal" if net_info.get("internal") else "bridge"
        net_table.add_row(
            f"[{C_INFO}]\u25cf[/]",
            net_name,
            net_type,
            ", ".join(sorted(members)),
        )

    # Special modes
    host_services = [n for n, i in services.items() if i["network_mode"] == "host"]
    if host_services:
        net_table.add_row(
            f"[{C_WARN}]\u25cf[/]",
            "host",
            "host",
            ", ".join(sorted(host_services)),
        )

    none_services = [n for n, i in services.items() if i["network_mode"] == "none"]
    if none_services:
        net_table.add_row(
            f"[{C_ERR}]\u25cf[/]",
            "none",
            "isolated",
            ", ".join(sorted(none_services)),
        )

    shared_services = [
        (n, i["network_mode"].split(":", 1)[1])
        for n, i in services.items()
        if i["network_mode"] and i["network_mode"].startswith("service:")
    ]
    for svc_name, target in shared_services:
        net_table.add_row(
            f"[{C_TEAL}]\u25cf[/]",
            f"service:{target}",
            "shared",
            svc_name,
        )

    console.print(net_table)

    # ── Dependency reachability ────────────────────────────────
    deps_exist = any(info["depends_on"] for info in services.values())
    if deps_exist:
        console.print()
        console.print(f"  [{C_TEXT}]Dependency Reachability[/]")
        console.print()

        dep_table = Table(
            box=box.SIMPLE_HEAD,
            border_style=Style(color="#27272a"),
            header_style=C_MUTED,
            padding=(0, 2),
            show_edge=False,
        )
        dep_table.add_column("", width=2)
        dep_table.add_column("SERVICE", style=f"bold {C_TEXT}", no_wrap=True)
        dep_table.add_column("DEPENDS ON", style=C_TEXT, no_wrap=True)
        dep_table.add_column("REACHABLE", no_wrap=True)

        for svc_name in sorted(services.keys()):
            info = services[svc_name]
            for dep in info["depends_on"]:
                if dep in services:
                    reachable = can_communicate(graph, svc_name, dep)
                    if reachable:
                        status = f"[{C_OK}]\u2713 yes[/]"
                        dot = f"[{C_OK}]\u25cf[/]"
                    else:
                        status = f"[{C_ERR}]\u2716 NO[/]"
                        dot = f"[{C_ERR}]\u25cf[/]"
                else:
                    status = f"[{C_WARN}]? not found[/]"
                    dot = f"[{C_WARN}]\u25cf[/]"
                dep_table.add_row(dot, svc_name, dep, status)

        console.print(dep_table)

    console.print()


def format_topology_json(root: Path) -> str:
    """Return network topology as JSON."""
    import json
    from composearr.scanner.discovery import discover_compose_files
    from composearr.scanner.parser import parse_compose_file

    paths, _ = discover_compose_files(root)
    compose_files = [parse_compose_file(p) for p in paths]
    compose_files = [cf for cf in compose_files if not cf.parse_error]

    graph = build_network_graph(compose_files)

    # Serialize — strip non-serializable config
    output = {
        "services": {},
        "networks": graph["networks"],
        "reachability": [],
    }

    for name, info in graph["services"].items():
        output["services"][name] = {
            "networks": info["networks"],
            "network_mode": info["network_mode"],
            "depends_on": info["depends_on"],
            "file": info["file"],
        }
        for dep in info["depends_on"]:
            if dep in graph["services"]:
                output["reachability"].append({
                    "from": name,
                    "to": dep,
                    "reachable": can_communicate(graph, name, dep),
                })

    return json.dumps(output, indent=2)
