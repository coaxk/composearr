"""Analyze a central .env file and map variables to their respective stacks."""

from __future__ import annotations

import re
from pathlib import Path

from composearr.scanner.env_resolver import load_env_file

# Variables that should be included in every stack
COMMON_VARS = {"TZ", "PUID", "PGID", "UMASK"}

# Patterns that indicate secrets (case-insensitive check)
SECRET_PATTERNS = re.compile(
    r"(API_KEY|TOKEN|PASSWORD|SECRET|PASSPHRASE|CREDENTIALS|AUTH_KEY|DB_PASS)",
    re.IGNORECASE,
)


def parse_central_env(env_path: Path) -> dict[str, str]:
    """Parse a central .env file into key-value pairs.

    Returns empty dict if file doesn't exist or can't be read.
    """
    return load_env_file(env_path)


def extract_compose_var_references(compose_path: Path) -> set[str]:
    """Extract all environment variable names referenced in a compose file.

    Finds variables from:
    - environment: blocks (both mapping and list forms)
    - ${VAR} interpolation patterns
    - env_file references (to identify the file, not parse it)
    """
    if not compose_path.is_file():
        return set()

    try:
        content = compose_path.read_text(encoding="utf-8")
    except OSError:
        return set()

    refs: set[str] = set()

    # Match ${VAR}, ${VAR:-default}, ${VAR-default}
    for match in re.finditer(r"\$\{([A-Za-z_][A-Za-z0-9_]*)(?:[:-][^}]*)?\}", content):
        refs.add(match.group(1))

    # Match $VAR (bare dollar sign references, word boundary)
    for match in re.finditer(r"\$([A-Za-z_][A-Za-z0-9_]*)\b", content):
        refs.add(match.group(1))

    # Match environment mapping keys: "  KEY: value" or "  - KEY=value"
    for match in re.finditer(r"^\s+-\s+([A-Za-z_][A-Za-z0-9_]*)=", content, re.MULTILINE):
        refs.add(match.group(1))

    return refs


def is_common_var(var_name: str) -> bool:
    """Check if a variable is a common/shared variable."""
    return var_name in COMMON_VARS


def is_secret_var(var_name: str) -> bool:
    """Check if a variable name looks like a secret."""
    return bool(SECRET_PATTERNS.search(var_name))


def match_var_to_stack(var_name: str, stack_name: str) -> bool:
    """Check if a variable name is prefixed with a stack name.

    Examples:
        SONARR_API_KEY -> sonarr = True
        RADARR_API_KEY -> sonarr = False
        PLEX_TOKEN -> plex = True
    """
    prefix = stack_name.upper().replace("-", "_") + "_"
    return var_name.upper().startswith(prefix)


def map_vars_to_stacks(
    env_vars: dict[str, str],
    stacks_dir: Path,
) -> dict[str, dict[str, str]]:
    """Map central .env variables to their respective stacks.

    Strategy:
    1. Common variables (TZ, PUID, PGID, UMASK) go to ALL stacks
    2. Prefixed variables (SONARR_*, RADARR_*) go to matching stack
    3. Variables referenced in a stack's compose file go to that stack
    4. Remaining variables go to all stacks (safe default)

    Returns:
        {
            'sonarr': {'TZ': '...', 'PUID': '...', 'SONARR_API_KEY': '...'},
            'radarr': {'TZ': '...', 'PUID': '...', 'RADARR_API_KEY': '...'},
        }
    """
    if not stacks_dir.is_dir():
        return {}

    # Discover stack directories (contain compose.yaml)
    stack_dirs: list[Path] = []
    for child in sorted(stacks_dir.iterdir()):
        if child.is_dir() and not child.name.startswith("."):
            compose_file = child / "compose.yaml"
            if not compose_file.is_file():
                # Also check docker-compose.yml
                compose_file = child / "docker-compose.yml"
            if compose_file.is_file():
                stack_dirs.append(child)

    if not stack_dirs:
        return {}

    # Build per-stack variable references
    stack_refs: dict[str, set[str]] = {}
    for stack_dir in stack_dirs:
        compose_file = stack_dir / "compose.yaml"
        if not compose_file.is_file():
            compose_file = stack_dir / "docker-compose.yml"
        stack_refs[stack_dir.name] = extract_compose_var_references(compose_file)

    # Map variables to stacks
    result: dict[str, dict[str, str]] = {d.name: {} for d in stack_dirs}

    for var_name, value in env_vars.items():
        # Common vars go to all stacks
        if is_common_var(var_name):
            for stack_name in result:
                result[stack_name][var_name] = value
            continue

        # Check prefix match
        matched_by_prefix = False
        for stack_name in result:
            if match_var_to_stack(var_name, stack_name):
                result[stack_name][var_name] = value
                matched_by_prefix = True

        if matched_by_prefix:
            continue

        # Check compose file references
        matched_by_ref = False
        for stack_name, refs in stack_refs.items():
            if var_name in refs:
                result[stack_name][var_name] = value
                matched_by_ref = True

        if matched_by_ref:
            continue

        # Unmatched variables go to all stacks (safe default)
        for stack_name in result:
            result[stack_name][var_name] = value

    # Remove empty stacks
    return {k: v for k, v in result.items() if v}


def get_extraction_preview(
    env_vars: dict[str, str],
    stack_mapping: dict[str, dict[str, str]],
) -> dict[str, dict[str, list[str]]]:
    """Generate a preview of the extraction for user review.

    Returns per-stack breakdown:
        {
            'sonarr': {
                'common': ['TZ', 'PUID'],
                'stack_specific': ['SONARR_API_KEY'],
                'shared': ['DOCKER_HOST'],
            }
        }
    """
    preview: dict[str, dict[str, list[str]]] = {}

    for stack_name, stack_vars in stack_mapping.items():
        categorized: dict[str, list[str]] = {
            "common": [],
            "secrets": [],
            "stack_specific": [],
            "shared": [],
        }

        for var_name in sorted(stack_vars.keys()):
            if is_common_var(var_name):
                categorized["common"].append(var_name)
            elif is_secret_var(var_name):
                categorized["secrets"].append(var_name)
            elif match_var_to_stack(var_name, stack_name):
                categorized["stack_specific"].append(var_name)
            else:
                categorized["shared"].append(var_name)

        preview[stack_name] = categorized

    return preview
