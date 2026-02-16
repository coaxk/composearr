"""Discover compose files in a directory tree."""

from __future__ import annotations

import os
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

# ── Common stack locations (checked in order) ─────────────────

# Home-relative paths (all platforms)
_HOME_RELATIVE = [
    "docker",
    "Docker",
    "stacks",
    "Stacks",
    "docker-compose",
    "compose",
    "containers",
    "Containers",
    "homelab",
    "self-hosted",
    "selfhosted",
    "media-server",
    "server",
]

# Linux/macOS absolute paths
_LINUX_PATHS = [
    "/opt/stacks",
    "/opt/docker",
    "/opt/containers",
    "/opt/appdata",
    "/srv/docker",
    "/srv/stacks",
    "/srv/containers",
    "/home/docker",
    # Portainer / CasaOS / Cosmos / Umbrel / TrueNAS
    "/portainer/compose",
    "/var/lib/casaos/apps",
    "/cosmos",
    "/home/umbrel/umbrel/app-data",
    # NAS common mount points
    "/volume1/docker",
    "/share/Container",
    "/share/docker",
    "/mnt/user/appdata",
    "/mnt/docker",
    "/data/docker",
    "/data/compose",
]

# Windows absolute paths
_WINDOWS_PATHS = [
    "C:/docker",
    "C:/Docker",
    "C:/stacks",
    "C:/Stacks",
    "C:/containers",
    "C:/Containers",
    "C:/DockerContainers",
    "C:/docker-compose",
    "C:/compose",
    "C:/appdata",
    "D:/docker",
    "D:/Docker",
    "D:/stacks",
    "D:/containers",
    "D:/DockerContainers",
    "E:/docker",
    "E:/Docker",
    "E:/DockerContainers",
]

# Dirs to skip during smart scan (never descend into these)
_SKIP_DIRS = {
    ".git", ".hg", ".svn", "node_modules", "__pycache__", ".venv", "venv",
    ".cache", ".npm", ".cargo", ".rustup", ".local", ".config",
    "AppData", "Application Data", "Library", "Windows", "Program Files",
    "Program Files (x86)", "$Recycle.Bin", "System Volume Information",
    "Recovery", "PerfLogs",
}


def _has_compose_file(directory: Path) -> bool:
    """Quick check: does a directory contain at least one compose file?"""
    try:
        for child in directory.iterdir():
            if child.is_file() and child.name.lower() in COMPOSE_FILENAMES:
                return True
        # Check one level deeper (service-per-dir pattern)
        for child in directory.iterdir():
            if child.is_dir() and not child.name.startswith("."):
                for grandchild in child.iterdir():
                    if grandchild.is_file() and grandchild.name.lower() in COMPOSE_FILENAMES:
                        return True
    except (OSError, PermissionError):
        pass
    return False


def _build_common_paths() -> list[Path]:
    """Build the list of common stack paths for the current platform."""
    paths: list[Path] = []
    home = Path.home()

    for rel in _HOME_RELATIVE:
        paths.append(home / rel)

    if sys.platform == "win32":
        for p in _WINDOWS_PATHS:
            paths.append(Path(p))
    else:
        for p in _LINUX_PATHS:
            paths.append(Path(p))

    return paths


def _read_config_stack_path() -> Path | None:
    """Read stack_path from user or project .composearr.yml config."""
    from ruamel.yaml import YAML
    yaml = YAML()

    for config_path in [
        Path.home() / ".composearr.yml",
        Path.home() / ".composearr.yaml",
        Path.cwd() / ".composearr.yml",
        Path.cwd() / ".composearr.yaml",
    ]:
        try:
            if config_path.is_file():
                data = yaml.load(config_path)
                if isinstance(data, dict) and "stack_path" in data:
                    sp = Path(str(data["stack_path"])).expanduser().resolve()
                    if sp.is_dir():
                        return sp
        except Exception:
            continue
    return None


def _smart_scan(progress_callback=None) -> list[Path]:
    """Scan likely locations for directories containing compose files.

    Strategy: check top-level children of home dir and drive roots, then go
    one level deeper into anything that looks like a project directory.
    Fast — avoids deep recursion into AppData, node_modules, etc.

    Returns a list of candidate stack root directories (not individual files).
    """
    import time

    candidates: list[Path] = []
    visited: set[str] = set()
    deadline = time.monotonic() + 10  # 10-second hard limit

    # Dirs that are definitely NOT stack roots — skip entirely
    skip_names = _SKIP_DIRS | {
        "Desktop", "Documents", "Downloads", "Music", "Pictures", "Videos",
        "Favorites", "Contacts", "Searches", "Links", "Saved Games",
        "3D Objects", "Fonts", "Templates", "PrintHood", "NetHood",
        "SendTo", "Start Menu", "Recent", "Local Settings",
        "IntelGraphicsProfiles", "MicrosoftEdgeBackups", "OneDrive",
        "Creative Cloud Files", "Dropbox", "Google Drive",
        "go", "miniconda3", "anaconda3", "scoop",
    }

    def _is_stack_root(directory: Path) -> bool:
        """Check if a dir is a stack root (has compose files directly or in subdirs)."""
        try:
            children = list(directory.iterdir())
        except (OSError, PermissionError):
            return False

        # Direct compose file?
        for c in children:
            try:
                if c.is_file() and c.name.lower() in COMPOSE_FILENAMES:
                    return True
            except (OSError, PermissionError):
                continue

        # Service-per-directory pattern? (subdir/compose.yaml)
        for c in children:
            try:
                if not c.is_dir() or c.name.startswith(".") or c.name in skip_names:
                    continue
                for grandchild in c.iterdir():
                    if grandchild.is_file() and grandchild.name.lower() in COMPOSE_FILENAMES:
                        return True
            except (OSError, PermissionError):
                continue

        return False

    def _scan_children(parent: Path, max_depth: int = 1, depth: int = 0) -> None:
        """Scan children of a directory up to max_depth."""
        if time.monotonic() > deadline or len(candidates) >= 10:
            return

        try:
            entries = sorted(parent.iterdir(), key=lambda e: e.name.lower())
        except (OSError, PermissionError):
            return

        for entry in entries:
            if time.monotonic() > deadline or len(candidates) >= 10:
                return

            try:
                is_dir = entry.is_dir()
            except (OSError, PermissionError):
                continue

            if not is_dir or entry.name.startswith(".") or entry.name in skip_names:
                continue

            resolved = str(entry.resolve())
            if resolved in visited:
                continue
            visited.add(resolved)

            if progress_callback:
                progress_callback(str(entry))

            if _is_stack_root(entry):
                candidates.append(entry.resolve())
                continue  # Don't recurse into a found stack

            # Go deeper if allowed
            if depth < max_depth:
                _scan_children(entry, max_depth, depth + 1)

    # Scan home dir — only 1 level deep (home/docker, home/stacks, etc.)
    home = Path.home()
    visited.add(str(home.resolve()))
    if progress_callback:
        progress_callback(str(home))
    _scan_children(home, max_depth=1)

    # Scan drive roots / system dirs — 2 levels deep
    if sys.platform == "win32":
        for letter in "CDEFGH":
            drive = Path(f"{letter}:/")
            try:
                if drive.is_dir():
                    _scan_children(drive, max_depth=2)
            except (OSError, PermissionError):
                continue
    else:
        for extra in [Path("/opt"), Path("/srv"), Path("/mnt"), Path("/data"),
                      Path("/home"), Path("/volume1"), Path("/share")]:
            try:
                if extra.is_dir():
                    _scan_children(extra, max_depth=2)
            except (OSError, PermissionError):
                continue

    return candidates


def _count_compose_files(directory: Path) -> int:
    """Count compose files in a directory (quick, shallow)."""
    count = 0
    try:
        for name in COMPOSE_FILENAMES:
            count += sum(1 for _ in directory.rglob(name))
    except (OSError, PermissionError):
        pass
    return count


def detect_stack_directory(progress_callback=None) -> Path | None:
    """Auto-detect a Docker stack directory (single best result).

    Convenience wrapper around detect_all_stack_directories for CLI use.
    Returns the highest-ranked candidate, or None.
    """
    candidates = detect_all_stack_directories(progress_callback=progress_callback)
    return candidates[0]["path"] if candidates else None


def detect_all_stack_directories(progress_callback=None) -> list[dict]:
    """Auto-detect ALL potential Docker stack directories.

    Detection sources (all checked, results merged):
    1. stack_path from .composearr.yml config
    2. Current working directory (if it contains compose files)
    3. Common well-known locations (Docker Desktop, Portainer, CasaOS, NAS, etc.)
    4. Smart scan — shallow search of home dir and drive roots

    Returns list of dicts: [{"path": Path, "source": str, "compose_count": int}, ...]
    sorted by compose_count descending (most files = most likely the main stack).
    """
    seen: set[str] = set()
    candidates: list[dict] = []

    def _add(path: Path, source: str) -> None:
        resolved = path.resolve()
        key = str(resolved).lower()  # Case-insensitive on Windows
        if key in seen:
            return
        seen.add(key)
        count = _count_compose_files(resolved)
        if count > 0:
            candidates.append({"path": resolved, "source": source, "compose_count": count})

    # 1. Config-saved path
    config_path = _read_config_stack_path()
    if config_path:
        _add(config_path, "config")

    # 2. Current working directory
    try:
        cwd = Path.cwd().resolve()
        if _has_compose_file(cwd):
            _add(cwd, "cwd")
    except (OSError, PermissionError):
        pass

    # 3. Common well-known locations
    for path in _build_common_paths():
        try:
            if path.is_dir() and _has_compose_file(path):
                _add(path, "common")
        except (OSError, PermissionError):
            continue

    # 4. Smart scan (only if we haven't found enough yet)
    if len(candidates) < 5:
        smart_results = _smart_scan(progress_callback=progress_callback)
        for c in smart_results:
            _add(c, "scan")

    # Sort: config first, then by compose file count descending
    def _sort_key(item: dict) -> tuple:
        source_rank = {"config": 0, "cwd": 1, "common": 2, "scan": 3}
        return (source_rank.get(item["source"], 9), -item["compose_count"])

    candidates.sort(key=_sort_key)
    return candidates


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
