"""Advanced port parser handling IPv6, long syntax, ranges, UDP/SCTP."""

from __future__ import annotations

import re

from composearr.models import PortMapping


def parse_port_mapping(port_spec: str | dict | int, file_path: str = "", service: str = "") -> list[PortMapping]:
    """Parse a Docker Compose port specification into PortMapping objects.

    Handles:
    - Short syntax: "8080:80", "8080:80/udp", "127.0.0.1:8080:80"
    - IPv6: "[::1]:8080:80"
    - Ranges: "8080-8090:80-90"
    - Long syntax: {target: 80, published: 8080, protocol: tcp, host_ip: 0.0.0.0}
    - Integer: 80 (container port only)
    """
    if isinstance(port_spec, dict):
        return _parse_long_syntax(port_spec, file_path, service)

    if isinstance(port_spec, int):
        return []  # Container-only port, no host mapping

    spec = str(port_spec).strip()
    if not spec:
        return []

    # Strip protocol suffix
    protocol = "tcp"
    for proto in ("/udp", "/tcp", "/sctp"):
        if spec.endswith(proto):
            protocol = proto[1:]
            spec = spec[: -len(proto)]
            break

    # Handle IPv6 bracket notation: [::1]:8080:80
    ipv6_match = re.match(r"^\[([^\]]+)\]:(.+)$", spec)
    if ipv6_match:
        host_ip = ipv6_match.group(1)
        rest = ipv6_match.group(2)
        parts = rest.split(":")
        if len(parts) == 2:
            return _parse_host_container(parts[0], parts[1], protocol, host_ip, file_path, service)
        return []

    parts = spec.split(":")

    if len(parts) == 3:
        # ip:host:container
        return _parse_host_container(parts[1], parts[2], protocol, parts[0], file_path, service)
    elif len(parts) == 2:
        return _parse_host_container(parts[0], parts[1], protocol, "0.0.0.0", file_path, service)
    else:
        # Single port — container only, no conflict possible
        return []


def _parse_long_syntax(spec: dict, file_path: str, service: str) -> list[PortMapping]:
    """Parse long-form port syntax."""
    published = spec.get("published")
    target = spec.get("target")
    if published is None or target is None:
        return []

    return [
        PortMapping(
            host_port=int(published),
            container_port=int(target),
            protocol=str(spec.get("protocol", "tcp")),
            host_ip=str(spec.get("host_ip", "0.0.0.0")),
            service=service,
            file_path=file_path,
        )
    ]


def _parse_host_container(
    host_str: str,
    container_str: str,
    protocol: str,
    host_ip: str,
    file_path: str,
    service: str,
) -> list[PortMapping]:
    """Parse host:container port pair, handling ranges."""
    mappings: list[PortMapping] = []

    if "-" in host_str and "-" in container_str:
        try:
            h_start, h_end = host_str.split("-")
            c_start, c_end = container_str.split("-")
            for h, c in zip(
                range(int(h_start), int(h_end) + 1),
                range(int(c_start), int(c_end) + 1),
            ):
                mappings.append(PortMapping(h, c, protocol, host_ip, service, file_path))
        except ValueError:
            pass
    else:
        try:
            mappings.append(
                PortMapping(int(host_str), int(container_str), protocol, host_ip, service, file_path)
            )
        except ValueError:
            pass

    return mappings
