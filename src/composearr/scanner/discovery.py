"""Discover compose files in a directory tree."""

from __future__ import annotations

import sys
from pathlib import Path

from composearr.scanner.platform_detect import classify_paths
from composearr.security.input_validator import MAX_COMPOSE_FILES, MAX_SCAN_DEPTH

COMPOSE_FILENAMES = {
    "compose.yaml",
    "compose.yml",
    "docker-compose.yaml",
    "docker-compose.yml",
}

# Common Docker stack locations to check for auto-detection
_COMMON_STACK_PATHS: list[Path] = [
    Path.home() / "docker",
    Path.home() / "Docker",
    Path.home() / "stacks",
]

# Add platform-specific paths
if sys.platform == "win32":
    _COMMON_STACK_PATHS.extend([
        Path("C:/DockerContainers"),
        Path("D:/DockerContainers"),
        Path("C:/docker"),
        Path("D:/docker"),
    ])
else:
    _COMMON_STACK_PATHS.extend([
        Path("/opt/stacks"),
        Path("/opt/docker"),
        Path("/srv/docker"),
    ])


def detect_stack_directory() -> Path | None:
    """Auto-detect a Docker stack directory from common locations.

    Returns the first directory that contains compose files, or None.
    """
    for path in _COMMON_STACK_PATHS:
        try:
            if not path.is_dir():
                continue
            # Quick check: does this directory have any compose files?
            for name in COMPOSE_FILENAMES:
                if any(path.rglob(name)):
                    return path.resolve()
        except (OSError, PermissionError):
            continue
    return None


def discover_compose_files(root_path: Path) -> tuple[list[Path], dict[str, list[Path]]]:
    """Recursively find all compose files under root_path.

    Returns (canonical_paths, managed_dict) where managed_dict maps
    platform name -> list of skipped paths managed by that platform.
    """
    root = root_path.resolve()

    if not root.is_dir():
        return [], {}

    found: list[Path] = []
    for path in root.rglob("*"):
        if path.name.lower() in COMPOSE_FILENAMES and path.is_file():
            rel = path.relative_to(root)
            parts = rel.parts

            # Skip hidden directories
            if any(p.startswith(".") for p in parts[:-1]):
                continue

            # Enforce max scan depth
            if len(parts) > MAX_SCAN_DEPTH:
                continue

            # Skip symlinks that point outside the root
            try:
                resolved = path.resolve()
                if not str(resolved).startswith(str(root)):
                    continue
            except (OSError, RuntimeError):
                continue

            found.append(path)

            # Enforce max file count
            if len(found) >= MAX_COMPOSE_FILES:
                break

    all_sorted = sorted(found, key=lambda p: str(p.relative_to(root)))
    return classify_paths(all_sorted, root)
