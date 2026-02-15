"""CA6xx — Arr Stack rules (TRaSH Guides compliance)."""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

from composearr.models import LintIssue, Scope, Severity
from composearr.rules.base import BaseRule

if TYPE_CHECKING:
    from composearr.models import ComposeFile

# Known *arr service image patterns
_ARR_PATTERNS = re.compile(
    r"(sonarr|radarr|lidarr|readarr|whisparr|bazarr|prowlarr|"
    r"qbittorrent|sabnzbd|nzbget|deluge|transmission|rtorrent)",
    re.IGNORECASE,
)


def _is_arr_service(service_config: dict) -> bool:
    """Check if a service is part of the *arr media stack."""
    image = str(service_config.get("image", ""))
    return bool(_ARR_PATTERNS.search(image))


def _get_volume_paths(service_config: dict) -> list[str]:
    """Extract volume mount strings from a service config."""
    volumes = service_config.get("volumes", [])
    result: list[str] = []
    for vol in volumes:
        if isinstance(vol, str):
            result.append(vol)
        elif isinstance(vol, dict):
            source = vol.get("source", "")
            target = vol.get("target", "")
            if source and target:
                result.append(f"{source}:{target}")
    return result


class HardlinkPathMismatch(BaseRule):
    id = "CA601"
    name = "hardlink-path-mismatch"
    severity = Severity.WARNING
    scope = Scope.PROJECT
    description = "Arr services don't share a common /data root mount (TRaSH)"
    category = "arrstack"

    def check_service(self, service_name: str, service_config: dict, compose_file: ComposeFile) -> list[LintIssue]:
        return []

    def check_project(self, compose_files: list[ComposeFile]) -> list[LintIssue]:
        # Find all arr services and their volume configurations
        arr_services_with_split: list[str] = []

        for cf in compose_files:
            for svc_name, svc_config in cf.services.items():
                config = dict(svc_config) if hasattr(svc_config, "items") else {}
                if not _is_arr_service(config):
                    continue

                volumes = _get_volume_paths(config)
                has_unified = any(":/data" in v and not v.endswith(":/data/") for v in volumes)
                has_split = any(
                    ":/downloads" in v or ":/media" in v or
                    ":/tv" in v or ":/movies" in v
                    for v in volumes
                )

                if has_split and not has_unified:
                    arr_services_with_split.append(svc_name)

        if not arr_services_with_split:
            return []

        services_str = ", ".join(arr_services_with_split)
        return [
            self._make_issue(
                f"Services not using unified /data mount: {services_str}",
                "cross-file",
                suggested_fix="Use a single /data mount for all arr services (TRaSH Guides)",
                learn_more="https://trash-guides.info/Hardlinks/How-to-setup-for/Docker/",
            )
        ]
