"""Detect management platform directories and filter duplicates."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass
class ManagedPlatform:
    name: str
    path_patterns: list[str]


KNOWN_PLATFORMS: list[ManagedPlatform] = [
    ManagedPlatform("Komodo", ["komodo/periphery/repos"]),
    ManagedPlatform("Dockge", ["dockge/stacks", "opt/stacks"]),
    ManagedPlatform("Portainer", ["portainer/compose", "portainer/data"]),
    ManagedPlatform("Yacht", ["yacht/compose"]),
    ManagedPlatform("CasaOS", ["casaos/apps"]),
    ManagedPlatform("Cosmos", ["cosmos/compose"]),
    ManagedPlatform("Coolify", ["coolify/"]),
]


def classify_paths(
    paths: list[Path], root: Path
) -> tuple[list[Path], dict[str, list[Path]]]:
    """Separate canonical paths from management platform paths.

    Returns (canonical_paths, managed_dict) where managed_dict maps
    platform name -> list of skipped paths.
    """
    canonical: list[Path] = []
    managed: dict[str, list[Path]] = {}

    for path in paths:
        try:
            rel = path.relative_to(root).as_posix().lower()
        except ValueError:
            rel = path.as_posix().lower()

        platform = _detect_platform(rel)
        if platform:
            managed.setdefault(platform, []).append(path)
        else:
            canonical.append(path)

    return canonical, managed


def _detect_platform(rel_path_lower: str) -> str | None:
    """Return platform name if path is inside a known managed directory."""
    for platform in KNOWN_PLATFORMS:
        for pattern in platform.path_patterns:
            if pattern in rel_path_lower:
                return platform.name
    return None
