"""The Orphanage — find Docker resources not referenced in any compose file."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from composearr.docker_client import DockerClient, DockerNetwork, DockerVolume


@dataclass
class OrphanageReport:
    """Report of orphaned Docker resources."""

    orphaned_volumes: list[DockerVolume] = field(default_factory=list)
    orphaned_networks: list[DockerNetwork] = field(default_factory=list)
    total_volumes: int = 0
    total_networks: int = 0
    docker_available: bool = False
    error: str = ""

    @property
    def total_orphans(self) -> int:
        return len(self.orphaned_volumes) + len(self.orphaned_networks)

    @property
    def has_orphans(self) -> bool:
        return self.total_orphans > 0


class OrphanageFinder:
    """Find Docker resources that aren't referenced in compose files."""

    def __init__(self, stack_path: Path, docker: DockerClient | None = None) -> None:
        self.stack_path = Path(stack_path).resolve()
        self.docker = docker or DockerClient()

    def find_orphans(self) -> OrphanageReport:
        if not self.docker.available:
            return OrphanageReport(
                docker_available=False,
                error=self.docker.error,
            )

        # Collect all resource names defined in compose files
        defined_volumes, defined_networks = self._collect_defined_resources()

        # Get actual Docker resources
        docker_volumes = self.docker.get_volumes()
        docker_networks = self.docker.get_networks()

        # Find orphans (Docker resources not in any compose file)
        orphaned_volumes = [
            v for v in docker_volumes
            if not self._is_referenced(v.name, defined_volumes)
        ]
        orphaned_networks = [
            n for n in docker_networks
            if not self._is_referenced(n.name, defined_networks)
        ]

        return OrphanageReport(
            orphaned_volumes=orphaned_volumes,
            orphaned_networks=orphaned_networks,
            total_volumes=len(docker_volumes),
            total_networks=len(docker_networks),
            docker_available=True,
        )

    def _collect_defined_resources(self) -> tuple[set[str], set[str]]:
        """Scan compose files and collect defined volume/network names."""
        from composearr.scanner.discovery import discover_compose_files
        from composearr.scanner.parser import parse_compose_file

        volumes: set[str] = set()
        networks: set[str] = set()

        paths, _ = discover_compose_files(self.stack_path)
        for file_path in paths:
            cf = parse_compose_file(file_path)
            if cf.parse_error or not cf.data:
                continue

            data = cf.data

            # Top-level volumes
            top_volumes = data.get("volumes")
            if isinstance(top_volumes, dict):
                volumes.update(str(k) for k in top_volumes.keys())

            # Top-level networks
            top_networks = data.get("networks")
            if isinstance(top_networks, dict):
                networks.update(str(k) for k in top_networks.keys())

            # Service-level references
            for svc_name, svc_config in cf.services.items():
                if not isinstance(svc_config, dict):
                    continue

                # Named volumes from service volume mounts
                for vol in svc_config.get("volumes", []):
                    if isinstance(vol, str) and ":" in vol:
                        source = vol.split(":")[0]
                        if not source.startswith("/") and not source.startswith("."):
                            volumes.add(source)
                    elif isinstance(vol, dict):
                        source = str(vol.get("source", ""))
                        if source and not source.startswith("/") and not source.startswith("."):
                            volumes.add(source)

                # Networks from service config
                svc_nets = svc_config.get("networks")
                if isinstance(svc_nets, list):
                    networks.update(str(n) for n in svc_nets)
                elif isinstance(svc_nets, dict):
                    networks.update(svc_nets.keys())

        return volumes, networks

    @staticmethod
    def _is_referenced(docker_name: str, defined_names: set[str]) -> bool:
        """Check if a Docker resource name matches any compose-defined name.

        Handles Docker Compose project prefixes (e.g. ``myproject_myvolume``).
        """
        if docker_name in defined_names:
            return True
        # Docker Compose prefixes volume/network names with the project name
        for defined in defined_names:
            if docker_name.endswith(f"_{defined}"):
                return True
        return False
