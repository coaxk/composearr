"""Update compose files to use local .env instead of central paths."""

from __future__ import annotations

import re
from pathlib import Path

from ruamel.yaml import YAML

yaml = YAML()
yaml.preserve_quotes = True


def update_env_file_reference(
    compose_path: Path,
    *,
    new_env_path: str = ".env",
    dry_run: bool = False,
) -> bool:
    """Update env_file references in a compose file to use a local path.

    Replaces any absolute or remote env_file paths with the given
    relative path (default: '.env').

    Args:
        compose_path: Path to the compose file.
        new_env_path: New env_file path to use.
        dry_run: If True, don't write changes.

    Returns:
        True if changes were made (or would be made in dry_run).
    """
    if not compose_path.is_file():
        return False

    try:
        content = compose_path.read_text(encoding="utf-8")
        data = yaml.load(content)
    except Exception:
        return False

    if not isinstance(data, dict) or "services" not in data:
        return False

    changed = False
    services = data.get("services") or {}

    for _svc_name, svc_config in services.items():
        if not isinstance(svc_config, dict):
            continue

        if "env_file" in svc_config:
            old_value = svc_config["env_file"]
            new_value = _update_env_file_value(old_value, new_env_path)

            if old_value != new_value:
                svc_config["env_file"] = new_value
                changed = True

    if changed and not dry_run:
        with open(compose_path, "w", encoding="utf-8") as f:
            yaml.dump(data, f)

    return changed


def _update_env_file_value(old_value: object, new_path: str) -> object:
    """Replace env_file value(s) with the new path.

    Handles both list and string forms:
    - env_file: /some/path/.env -> env_file: .env
    - env_file:
        - /some/path/.env -> env_file:
                               - .env
    """
    if isinstance(old_value, list):
        new_list = []
        for item in old_value:
            if isinstance(item, str) and _is_absolute_or_remote_env(item):
                new_list.append(new_path)
            else:
                new_list.append(item)
        return new_list
    elif isinstance(old_value, str):
        if _is_absolute_or_remote_env(old_value):
            return new_path
    return old_value


def _is_absolute_or_remote_env(path_str: str) -> bool:
    """Check if a path is an absolute path or remote reference."""
    path_str = path_str.strip()
    # Absolute paths (Unix or Windows)
    if path_str.startswith("/") or re.match(r"^[A-Za-z]:", path_str):
        return True
    # Variable interpolation patterns
    if "${" in path_str:
        return True
    return False


def add_env_file_directive(
    compose_path: Path,
    env_path: str = ".env",
    *,
    dry_run: bool = False,
) -> bool:
    """Add env_file directive to services that don't have one.

    Args:
        compose_path: Path to the compose file.
        env_path: The env_file path to add.
        dry_run: If True, don't write changes.

    Returns:
        True if changes were made.
    """
    if not compose_path.is_file():
        return False

    try:
        content = compose_path.read_text(encoding="utf-8")
        data = yaml.load(content)
    except Exception:
        return False

    if not isinstance(data, dict) or "services" not in data:
        return False

    changed = False
    services = data.get("services") or {}

    for _svc_name, svc_config in services.items():
        if not isinstance(svc_config, dict):
            continue

        if "env_file" not in svc_config:
            svc_config["env_file"] = [env_path]
            changed = True

    if changed and not dry_run:
        with open(compose_path, "w", encoding="utf-8") as f:
            yaml.dump(data, f)

    return changed


def get_current_env_file_paths(compose_path: Path) -> list[str]:
    """Get all env_file paths referenced in a compose file.

    Returns a flat list of all env_file path strings across all services.
    """
    if not compose_path.is_file():
        return []

    try:
        content = compose_path.read_text(encoding="utf-8")
        data = yaml.load(content)
    except Exception:
        return []

    if not isinstance(data, dict) or "services" not in data:
        return []

    paths: list[str] = []
    services = data.get("services") or {}

    for _svc_name, svc_config in services.items():
        if not isinstance(svc_config, dict):
            continue

        env_file = svc_config.get("env_file")
        if isinstance(env_file, list):
            paths.extend(str(p) for p in env_file)
        elif isinstance(env_file, str):
            paths.append(env_file)

    return paths
