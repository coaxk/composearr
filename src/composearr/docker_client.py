"""Docker client for runtime inspection — optional dependency.

Supports multiple Docker connection methods:
  - Docker Desktop (Windows/macOS) via named pipe or Unix socket
  - Docker Engine on Linux via /var/run/docker.sock
  - Docker Engine on WSL2 via /var/run/docker.sock inside WSL
  - Custom DOCKER_HOST environment variable

Install the optional dependency: pip install composearr[docker]
"""

from __future__ import annotations

import os
import sys
from dataclasses import dataclass, field
from typing import Any

# Docker SDK is optional
try:
    import docker
    _HAS_DOCKER = True
except ImportError:
    _HAS_DOCKER = False


@dataclass
class DockerVolume:
    """Volume information from Docker."""

    name: str
    driver: str = "local"
    mountpoint: str = ""
    created: str = ""


@dataclass
class DockerNetwork:
    """Network information from Docker."""

    name: str
    id: str = ""
    driver: str = "bridge"
    scope: str = "local"
    created: str = ""


@dataclass
class DockerContainer:
    """Running container information."""

    name: str
    service_name: str = ""
    image: str = ""
    status: str = ""
    ports: dict = field(default_factory=dict)
    env: list[str] = field(default_factory=list)
    labels: dict[str, str] = field(default_factory=dict)


def _detect_platform() -> str:
    """Detect the Docker platform context."""
    if sys.platform == "win32":
        # Check if running inside WSL
        try:
            with open("/proc/version", "r") as f:
                if "microsoft" in f.read().lower():
                    return "wsl"
        except (FileNotFoundError, OSError):
            pass
        return "windows"
    elif sys.platform == "darwin":
        return "macos"
    return "linux"


def _build_connection_urls() -> list[str]:
    """Build a list of Docker connection URLs to try, ordered by platform likelihood."""
    urls: list[str] = []

    # 1. Always respect DOCKER_HOST if set
    docker_host = os.environ.get("DOCKER_HOST")
    if docker_host:
        urls.append(docker_host)

    platform = _detect_platform()

    if platform == "windows":
        # Docker Desktop on Windows uses a named pipe
        urls.append("npipe:////./pipe/docker_engine")
        # Also try TCP (Docker Desktop exposes this if enabled)
        urls.append("tcp://localhost:2375")
    elif platform == "wsl":
        # WSL2 — Docker Engine runs natively inside WSL
        urls.append("unix:///var/run/docker.sock")
        # Or Docker Desktop WSL integration
        urls.append("unix:///var/run/docker.sock")
    elif platform == "macos":
        # Docker Desktop on macOS
        urls.append("unix:///var/run/docker.sock")
        # Colima / Rancher Desktop alternative socket locations
        home = os.path.expanduser("~")
        urls.append(f"unix://{home}/.colima/docker.sock")
        urls.append(f"unix://{home}/.rd/docker.sock")
    else:
        # Linux — standard socket
        urls.append("unix:///var/run/docker.sock")
        # Rootless Docker
        uid = os.getuid() if hasattr(os, "getuid") else None
        if uid:
            urls.append(f"unix:///run/user/{uid}/docker.sock")

    return urls


def _get_platform_help() -> str:
    """Return platform-specific help text for Docker connection issues."""
    platform = _detect_platform()

    if platform == "windows":
        return (
            "Docker connection options for Windows:\n"
            "  1. Docker Desktop: Make sure Docker Desktop is running\n"
            "  2. WSL2 + Docker Engine: Run ComposeArr from inside your WSL distro\n"
            "     (wsl -d Ubuntu, then run composearr from there)\n"
            "  3. Set DOCKER_HOST: e.g. DOCKER_HOST=tcp://localhost:2375\n"
            "\n"
            "If you run Docker Engine inside WSL2 (not Docker Desktop),\n"
            "ComposeArr needs to run from inside WSL to access the Docker socket."
        )
    elif platform == "wsl":
        return (
            "Docker connection from WSL2:\n"
            "  1. Docker Engine in WSL: sudo service docker start\n"
            "  2. Docker Desktop integration: Enable WSL integration in\n"
            "     Docker Desktop → Settings → Resources → WSL Integration\n"
            "  3. Check socket: ls -la /var/run/docker.sock\n"
            "  4. Permissions: sudo usermod -aG docker $USER (then restart shell)"
        )
    elif platform == "macos":
        return (
            "Docker connection options for macOS:\n"
            "  1. Docker Desktop: Make sure Docker Desktop is running\n"
            "  2. Colima: colima start\n"
            "  3. Rancher Desktop: Make sure Rancher Desktop is running\n"
            "  4. Check socket: ls -la /var/run/docker.sock"
        )
    else:
        return (
            "Docker connection options for Linux:\n"
            "  1. Start Docker: sudo systemctl start docker\n"
            "  2. Check socket: ls -la /var/run/docker.sock\n"
            "  3. Permissions: sudo usermod -aG docker $USER (then restart shell)\n"
            "  4. Rootless Docker: check ~/.config/docker/daemon.json"
        )


class DockerClient:
    """Client for inspecting Docker runtime state.

    Tries multiple connection methods automatically based on the detected
    platform. Supports Docker Desktop (Windows/macOS), Docker Engine on
    Linux, and Docker Engine inside WSL2.

    Requires the ``docker`` package (install with ``pip install composearr[docker]``).
    All methods return empty results gracefully when Docker is unavailable.
    """

    def __init__(self) -> None:
        self._client: Any = None
        self.error: str = ""
        self.platform: str = _detect_platform()

        if not _HAS_DOCKER:
            self.error = "Docker SDK not installed (pip install composearr[docker])"
            return

        # Try docker.from_env() first (respects DOCKER_HOST + defaults)
        try:
            self._client = docker.from_env()
            self._client.ping()
            return
        except Exception:
            self._client = None

        # Try each known connection URL for this platform
        for url in _build_connection_urls():
            try:
                self._client = docker.DockerClient(base_url=url)
                self._client.ping()
                return  # Connected!
            except Exception:
                self._client = None
                continue

        # Nothing worked
        self.error = (
            f"Could not connect to Docker on {self.platform}.\n"
            f"{_get_platform_help()}"
        )

    @property
    def available(self) -> bool:
        return self._client is not None

    # ── Volumes ──────────────────────────────────────────────────

    def get_volumes(self) -> list[DockerVolume]:
        if not self._client:
            return []
        try:
            return [
                DockerVolume(
                    name=v.name,
                    driver=v.attrs.get("Driver", "local"),
                    mountpoint=v.attrs.get("Mountpoint", ""),
                    created=v.attrs.get("CreatedAt", ""),
                )
                for v in self._client.volumes.list()
            ]
        except Exception:
            return []

    # ── Networks ─────────────────────────────────────────────────

    _SYSTEM_NETWORKS = frozenset({"bridge", "host", "none", "ingress"})

    def get_networks(self) -> list[DockerNetwork]:
        if not self._client:
            return []
        try:
            results = []
            for n in self._client.networks.list():
                if n.name in self._SYSTEM_NETWORKS:
                    continue
                results.append(DockerNetwork(
                    name=n.name,
                    id=n.id[:12] if n.id else "",
                    driver=n.attrs.get("Driver", "bridge"),
                    scope=n.attrs.get("Scope", "local"),
                    created=n.attrs.get("Created", ""),
                ))
            return results
        except Exception:
            return []

    # ── Containers ───────────────────────────────────────────────

    def get_containers(self, all_states: bool = False) -> list[DockerContainer]:
        """Get containers. By default only running; set all_states for all."""
        if not self._client:
            return []
        try:
            results = []
            for c in self._client.containers.list(all=all_states):
                tags = c.image.tags if c.image.tags else []
                image_str = tags[0] if tags else (c.image.id[:19] if c.image else "unknown")

                results.append(DockerContainer(
                    name=c.name,
                    service_name=c.labels.get("com.docker.compose.service", c.name),
                    image=image_str,
                    status=c.status,
                    ports=c.ports or {},
                    env=c.attrs.get("Config", {}).get("Env", []),
                    labels=dict(c.labels) if c.labels else {},
                ))
            return results
        except Exception:
            return []
