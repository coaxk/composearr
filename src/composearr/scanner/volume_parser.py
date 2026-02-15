"""Volume parser for Docker Compose volume specifications."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class VolumeMount:
    """A parsed volume mount."""

    source: str
    target: str
    read_only: bool = False
    volume_type: str = "bind"  # bind, volume, tmpfs
    service: str = ""
    file_path: str = ""


def parse_volume(vol_spec: str | dict, file_path: str = "", service: str = "") -> VolumeMount | None:
    """Parse a Docker Compose volume specification.

    Handles:
    - Short syntax: "/host:/container", "/host:/container:ro"
    - Named volumes: "mydata:/data"
    - Long syntax: {type: bind, source: /host, target: /container, read_only: true}
    - tmpfs: {type: tmpfs, target: /tmp}
    - SELinux labels: "/host:/container:z", "/host:/container:Z"
    """
    if isinstance(vol_spec, dict):
        return _parse_long_syntax(vol_spec, file_path, service)

    spec = str(vol_spec).strip()
    if not spec:
        return None

    # Parse options suffix
    read_only = False
    parts = spec.split(":")

    if len(parts) >= 3:
        # Check for ro/rw/z/Z options in last part
        options = parts[-1]
        if options in ("ro", "rw", "z", "Z", "ro,z", "ro,Z", "rw,z", "rw,Z"):
            read_only = "ro" in options
            parts = parts[:-1]

    if len(parts) == 2:
        source, target = parts[0], parts[1]
    elif len(parts) == 1:
        # Anonymous volume or single path
        return VolumeMount(
            source="",
            target=parts[0],
            volume_type="volume",
            service=service,
            file_path=file_path,
        )
    else:
        return None

    # Determine type
    vol_type = "bind" if source.startswith(("/", ".", "~")) else "volume"

    return VolumeMount(
        source=source,
        target=target,
        read_only=read_only,
        volume_type=vol_type,
        service=service,
        file_path=file_path,
    )


def _parse_long_syntax(spec: dict, file_path: str, service: str) -> VolumeMount | None:
    """Parse long-form volume syntax."""
    target = spec.get("target")
    if not target:
        return None

    return VolumeMount(
        source=spec.get("source", ""),
        target=target,
        read_only=spec.get("read_only", False),
        volume_type=spec.get("type", "volume"),
        service=service,
        file_path=file_path,
    )
