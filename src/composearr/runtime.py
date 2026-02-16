"""Runtime comparison — compare compose definitions vs running containers."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from composearr.docker_client import DockerClient, DockerContainer


@dataclass
class RuntimeDiff:
    """A single difference between compose and runtime state."""

    service: str
    category: str  # "missing", "extra", "image", "env", "status"
    expected: str
    actual: str
    severity: str  # "error", "warning", "info"


@dataclass
class RuntimeReport:
    """Full runtime comparison report."""

    diffs: list[RuntimeDiff] = field(default_factory=list)
    compose_services: int = 0
    running_services: int = 0
    docker_available: bool = False
    error: str = ""

    @property
    def has_diffs(self) -> bool:
        return len(self.diffs) > 0


class RuntimeComparator:
    """Compare Docker Compose definitions against actual running containers."""

    def __init__(self, stack_path: Path, docker: DockerClient | None = None) -> None:
        self.stack_path = Path(stack_path).resolve()
        self.docker = docker or DockerClient()

    def compare(self) -> RuntimeReport:
        if not self.docker.available:
            return RuntimeReport(
                docker_available=False,
                error=self.docker.error,
            )

        compose_services = self._get_compose_services()
        containers = self._get_running_map()

        diffs: list[RuntimeDiff] = []

        # Check each compose service against running containers
        for svc_name, svc_config in compose_services.items():
            container = containers.get(svc_name)

            if container is None:
                diffs.append(RuntimeDiff(
                    service=svc_name,
                    category="missing",
                    expected="running",
                    actual="not running",
                    severity="warning",
                ))
                continue

            # Compare image
            expected_image = svc_config.get("image", "")
            if expected_image and container.image:
                # Normalize for comparison: strip registry prefix matching
                if not self._images_match(expected_image, container.image):
                    diffs.append(RuntimeDiff(
                        service=svc_name,
                        category="image",
                        expected=expected_image,
                        actual=container.image,
                        severity="error",
                    ))

            # Check status
            if container.status not in ("running", "restarting"):
                diffs.append(RuntimeDiff(
                    service=svc_name,
                    category="status",
                    expected="running",
                    actual=container.status,
                    severity="warning",
                ))

        # Check for extra containers not in compose
        for svc_name, container in containers.items():
            if svc_name not in compose_services:
                diffs.append(RuntimeDiff(
                    service=svc_name,
                    category="extra",
                    expected="not defined",
                    actual=f"running ({container.image})",
                    severity="info",
                ))

        return RuntimeReport(
            diffs=diffs,
            compose_services=len(compose_services),
            running_services=len(containers),
            docker_available=True,
        )

    def _get_compose_services(self) -> dict[str, dict]:
        """Get all services from compose files in the stack."""
        from composearr.scanner.discovery import discover_compose_files
        from composearr.scanner.parser import parse_compose_file

        services: dict[str, dict] = {}
        paths, _ = discover_compose_files(self.stack_path)
        for file_path in paths:
            cf = parse_compose_file(file_path)
            if cf.parse_error:
                continue
            for name, config in cf.services.items():
                if isinstance(config, dict):
                    services[name] = config

        return services

    def _get_running_map(self) -> dict[str, DockerContainer]:
        """Get running containers indexed by compose service name."""
        containers = self.docker.get_containers()
        return {c.service_name: c for c in containers}

    @staticmethod
    def _images_match(compose_image: str, runtime_image: str) -> bool:
        """Compare images accounting for tag/registry differences.

        Examples that match:
            nginx == nginx:latest
            nginx:1.25 == docker.io/library/nginx:1.25
        """
        def _normalize(img: str) -> str:
            # Strip known registry prefixes
            for prefix in ("docker.io/library/", "docker.io/"):
                if img.startswith(prefix):
                    img = img[len(prefix):]
            # Add implicit :latest
            if ":" not in img and "@" not in img:
                img += ":latest"
            return img

        return _normalize(compose_image) == _normalize(runtime_image)
