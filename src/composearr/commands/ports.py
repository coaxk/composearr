"""Port allocation table — shows all ports across a Docker stack."""

from __future__ import annotations

import csv
import io
import json
from collections import defaultdict
from pathlib import Path

from rich import box
from rich.console import Console
from rich.style import Style
from rich.table import Table
from rich.text import Text

from composearr.models import PortMapping
from composearr.scanner.discovery import discover_compose_files
from composearr.scanner.parser import parse_compose_file
from composearr.scanner.port_parser import parse_port_mapping

# Color tokens
C_TEAL = "#2dd4bf"
C_MUTED = "#71717a"
C_OK = "#22c55e"
C_ERR = "#ef4444"
C_WARN = "#f59e0b"
C_TEXT = "#fafafa"
C_DIM = "#3f3f46"
C_BORDER = "#27272a"


def collect_ports(root: Path) -> list[PortMapping]:
    """Collect all port mappings from compose files under root."""
    compose_files, _ = discover_compose_files(root)
    all_ports: list[PortMapping] = []

    for path in compose_files:
        cf = parse_compose_file(path)
        if cf.parse_error:
            continue

        for svc_name, svc_config in cf.services.items():
            config = dict(svc_config) if hasattr(svc_config, "items") else {}
            ports = config.get("ports", [])
            for port_spec in ports:
                mappings = parse_port_mapping(port_spec, str(cf.path), svc_name)
                all_ports.extend(mappings)

    return all_ports


def find_conflicts(ports: list[PortMapping]) -> dict[str, list[PortMapping]]:
    """Find port conflicts — same host_port + protocol used by multiple services."""
    by_port: dict[str, list[PortMapping]] = defaultdict(list)
    for pm in ports:
        key = f"{pm.host_port}/{pm.protocol}"
        by_port[key].append(pm)

    return {k: v for k, v in by_port.items() if len(v) > 1}


def suggest_available_port(used_ports: set[int], near: int = 8080) -> int:
    """Find the next available port near the requested one."""
    port = near
    while port in used_ports and port < 65535:
        port += 1
    return port


def render_port_table(
    ports: list[PortMapping],
    root: Path,
    console: Console,
    *,
    show_conflicts_only: bool = False,
) -> None:
    """Render a Rich table of port allocations."""
    conflicts = find_conflicts(ports)
    conflict_keys = set(conflicts.keys())

    if show_conflicts_only:
        display_ports = []
        for pm in ports:
            key = f"{pm.host_port}/{pm.protocol}"
            if key in conflict_keys:
                display_ports.append(pm)
    else:
        display_ports = ports

    if not display_ports:
        console.print(f"  [{C_OK}]\u2713[/] [{C_TEXT}]No port mappings found[/]")
        return

    # Sort by host port
    display_ports.sort(key=lambda p: (p.host_port, p.protocol, p.service))

    table = Table(
        box=box.SIMPLE_HEAD,
        border_style=Style(color=C_BORDER),
        header_style=C_MUTED,
        padding=(0, 2),
        show_edge=False,
    )
    table.add_column("", width=2)
    table.add_column("HOST PORT", style=f"bold {C_TEXT}", no_wrap=True)
    table.add_column("CONTAINER", style=C_TEXT, no_wrap=True)
    table.add_column("PROTO", style=C_MUTED, no_wrap=True)
    table.add_column("SERVICE", style=f"bold {C_TEAL}", no_wrap=True)
    table.add_column("FILE", style=C_DIM)

    used_ports = {pm.host_port for pm in ports}

    for pm in display_ports:
        key = f"{pm.host_port}/{pm.protocol}"
        is_conflict = key in conflict_keys

        try:
            rel = str(Path(pm.file_path).relative_to(root))
        except ValueError:
            rel = pm.file_path

        dot_color = C_ERR if is_conflict else C_OK
        dot = f"[{dot_color}]\u25cf[/]"
        host_port_str = str(pm.host_port)
        if is_conflict:
            host_port_str = f"[{C_ERR}]{pm.host_port}[/]"

        bind = ""
        if pm.host_ip and pm.host_ip not in ("0.0.0.0", "::"):
            bind = f"[{C_MUTED}]{pm.host_ip}:[/]"

        table.add_row(
            dot,
            f"{bind}{host_port_str}",
            str(pm.container_port),
            pm.protocol,
            pm.service,
            rel,
        )

    # Header
    conflict_count = len(conflict_keys)
    total = len(display_ports)
    console.print()
    console.print(
        f"  [{C_TEXT}]Port Allocations[/]  "
        f"[{C_MUTED}]{total} mappings[/]"
        + (f"  [{C_ERR}]{conflict_count} conflicts[/]" if conflict_count else f"  [{C_OK}]no conflicts[/]")
    )
    console.print()
    console.print(table)

    # Conflict details
    if conflicts:
        console.print()
        console.print(f"  [{C_ERR}]\u2501\u2501 Conflicts[/]")
        console.print()
        for port_key, mappings in sorted(conflicts.items()):
            services = [f"{m.service}" for m in mappings]
            suggested = suggest_available_port(used_ports, mappings[0].host_port + 1)
            console.print(
                f"    [{C_ERR}]\u25cf[/] [{C_ERR}]{port_key}[/]  "
                f"used by: [{C_TEXT}]{', '.join(services)}[/]"
            )
            console.print(
                f"      [{C_OK}]\u2192[/] [{C_TEAL}]Suggested alternative: port {suggested}[/]"
            )
            used_ports.add(suggested)  # Reserve for next suggestion
    console.print()


def format_ports_json(ports: list[PortMapping], root: Path) -> str:
    """Export port allocations as JSON."""
    conflicts = find_conflicts(ports)
    conflict_keys = set(conflicts.keys())

    entries = []
    for pm in sorted(ports, key=lambda p: p.host_port):
        try:
            rel = str(Path(pm.file_path).relative_to(root))
        except ValueError:
            rel = pm.file_path

        key = f"{pm.host_port}/{pm.protocol}"
        entries.append({
            "host_port": pm.host_port,
            "container_port": pm.container_port,
            "protocol": pm.protocol,
            "host_ip": pm.host_ip,
            "service": pm.service,
            "file": rel,
            "conflict": key in conflict_keys,
        })

    data = {
        "total_mappings": len(entries),
        "conflicts": len(conflict_keys),
        "ports": entries,
    }
    return json.dumps(data, indent=2)


def format_ports_csv(ports: list[PortMapping], root: Path) -> str:
    """Export port allocations as CSV."""
    conflicts = find_conflicts(ports)
    conflict_keys = set(conflicts.keys())

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["host_port", "container_port", "protocol", "host_ip", "service", "file", "conflict"])

    for pm in sorted(ports, key=lambda p: p.host_port):
        try:
            rel = str(Path(pm.file_path).relative_to(root))
        except ValueError:
            rel = pm.file_path

        key = f"{pm.host_port}/{pm.protocol}"
        writer.writerow([
            pm.host_port, pm.container_port, pm.protocol,
            pm.host_ip, pm.service, rel,
            "yes" if key in conflict_keys else "no",
        ])

    return output.getvalue()
