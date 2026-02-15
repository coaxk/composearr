"""Load and resolve .env files."""

from __future__ import annotations

import re
from pathlib import Path

from dotenv import dotenv_values

# Pattern for ${VAR}, ${VAR:-default}, ${VAR-default}
_VAR_PATTERN = re.compile(r"\$\{([^}]+)\}")


def load_env_file(env_path: Path) -> dict[str, str]:
    """Parse a .env file into a key-value dict.

    Returns empty dict if file doesn't exist or can't be read.
    """
    if not env_path.is_file():
        return {}

    try:
        raw = dotenv_values(env_path)
        return {k: (v or "") for k, v in raw.items()}
    except Exception:
        return {}


def discover_env_files(compose_dir: Path) -> list[Path]:
    """Find .env files associated with a compose file's directory."""
    envs: list[Path] = []
    env_path = compose_dir / ".env"
    if env_path.is_file():
        envs.append(env_path)
    return envs


def resolve_variable(value: str, env_vars: dict[str, str]) -> str:
    """Resolve ${VAR} and ${VAR:-default} patterns in a string."""

    def _replace(match: re.Match) -> str:
        expr = match.group(1)

        # ${VAR:-default}
        if ":-" in expr:
            var_name, default = expr.split(":-", 1)
            return env_vars.get(var_name, default)

        # ${VAR-default}
        if "-" in expr and ":" not in expr:
            var_name, default = expr.split("-", 1)
            return env_vars.get(var_name, default)

        # ${VAR}
        return env_vars.get(expr, match.group(0))

    return _VAR_PATTERN.sub(_replace, value)
