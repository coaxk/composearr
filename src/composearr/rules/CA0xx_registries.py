"""CA003 — Untrusted registry detection."""

from __future__ import annotations

from typing import TYPE_CHECKING

from composearr.models import LintIssue, Scope, Severity
from composearr.rules.base import BaseRule
from composearr.scanner.parser import find_line_number

if TYPE_CHECKING:
    from composearr.models import ComposeFile

# Default trusted registries/prefixes
TRUSTED_REGISTRIES = {
    "docker.io",
    "docker.io/library",
    "lscr.io",
    "lscr.io/linuxserver",
    "ghcr.io/linuxserver",
    "ghcr.io/hotio",
    "cr.hotio.dev",
    "ghcr.io",
    "mcr.microsoft.com",
    "gcr.io",
    "quay.io",
}


def _parse_registry(image: str) -> str | None:
    """Extract registry from image reference. Returns None for Docker Hub official images."""
    # Strip tag/digest
    clean = image.split(":")[0].split("@")[0]

    # Docker Hub official images (no slash or single slash with no dots)
    if "/" not in clean:
        return "docker.io/library"

    first_part = clean.split("/")[0]

    # If first part has a dot or colon, it's a registry
    if "." in first_part or ":" in first_part:
        return first_part

    # Docker Hub org image (e.g., linuxserver/sonarr)
    return "docker.io"


class UntrustedRegistry(BaseRule):
    id = "CA003"
    name = "untrusted-registry"
    severity = Severity.INFO
    scope = Scope.SERVICE
    description = "Image pulled from non-default registry"
    category = "images"

    def check_service(
        self,
        service_name: str,
        service_config: dict,
        compose_file: ComposeFile,
    ) -> list[LintIssue]:
        image = service_config.get("image")
        if not image:
            return []

        image_str = str(image)
        registry = _parse_registry(image_str)

        if registry is None:
            return []

        # Check if registry is trusted
        for trusted in TRUSTED_REGISTRIES:
            if registry == trusted or registry.startswith(f"{trusted}/"):
                return []

        # Also check the full prefix (e.g., "ghcr.io/linuxserver")
        clean = image_str.split(":")[0].split("@")[0]
        for trusted in TRUSTED_REGISTRIES:
            if clean.startswith(f"{trusted}/"):
                return []

        line = find_line_number(compose_file.raw_content, "image:", image_str)
        return [
            self._make_issue(
                f"Image from non-standard registry: {registry}",
                str(compose_file.path),
                line=line,
                service=service_name,
                suggested_fix=f"Verify {registry} is trusted. Consider using Docker Hub, GHCR, or LSCR",
                learn_more="https://docs.docker.com/docker-hub/official_images/",
            )
        ]
