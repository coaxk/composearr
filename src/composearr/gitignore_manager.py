"""Manage .gitignore files for stack directories."""

from __future__ import annotations

from pathlib import Path

# Default entries for a stack .gitignore
DEFAULT_ENTRIES = [".env"]


def ensure_env_in_gitignore(
    stack_dir: Path,
    entries: list[str] | None = None,
) -> bool:
    """Ensure .env (and optional extras) are in the stack's .gitignore.

    Creates .gitignore if it doesn't exist.
    Appends missing entries if it does exist.

    Args:
        stack_dir: Path to the stack directory.
        entries: List of patterns to ensure are present.
                 Defaults to ['.env'].

    Returns:
        True if the file was created or modified.
    """
    if entries is None:
        entries = DEFAULT_ENTRIES

    gitignore_path = stack_dir / ".gitignore"

    if gitignore_path.exists():
        return _update_gitignore(gitignore_path, entries)
    else:
        return _create_gitignore(gitignore_path, entries)


def _create_gitignore(gitignore_path: Path, entries: list[str]) -> bool:
    """Create a new .gitignore with the given entries."""
    lines = [
        "# Environment files - contain secrets",
    ]
    lines.extend(entries)
    lines.append("")  # trailing newline

    gitignore_path.write_text("\n".join(lines), encoding="utf-8")
    return True


def _update_gitignore(gitignore_path: Path, entries: list[str]) -> bool:
    """Add missing entries to an existing .gitignore."""
    content = gitignore_path.read_text(encoding="utf-8")
    existing_lines = set(content.splitlines())

    missing = [e for e in entries if e not in existing_lines]

    if not missing:
        return False

    # Append missing entries
    if not content.endswith("\n"):
        content += "\n"

    content += "\n".join(missing) + "\n"
    gitignore_path.write_text(content, encoding="utf-8")
    return True


def check_gitignore_status(stack_dir: Path) -> dict[str, bool]:
    """Check if .env is properly gitignored in a stack directory.

    Returns:
        {
            'gitignore_exists': True/False,
            'env_ignored': True/False,
        }
    """
    gitignore_path = stack_dir / ".gitignore"

    if not gitignore_path.exists():
        return {"gitignore_exists": False, "env_ignored": False}

    content = gitignore_path.read_text(encoding="utf-8")
    lines = content.splitlines()

    env_ignored = any(
        line.strip() == ".env" or line.strip() == "*.env"
        for line in lines
        if not line.strip().startswith("#")
    )

    return {"gitignore_exists": True, "env_ignored": env_ignored}
