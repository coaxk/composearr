"""Input validation for paths, configs, and file sizes."""

from __future__ import annotations

from pathlib import Path

# Maximum file size to parse (10 MB)
MAX_FILE_SIZE = 10 * 1024 * 1024

# Maximum depth for recursive scanning
MAX_SCAN_DEPTH = 10

# Maximum number of compose files to scan
MAX_COMPOSE_FILES = 500


def validate_scan_path(path: Path) -> tuple[bool, str]:
    """Validate a scan path is safe to process.

    Returns (is_valid, error_message).
    """
    if not path.exists():
        return False, f"Path does not exist: {path}"

    if not path.is_dir():
        return False, f"Path is not a directory: {path}"

    try:
        resolved = path.resolve()
    except (OSError, RuntimeError):
        return False, f"Cannot resolve path: {path}"

    return True, ""


def validate_file_size(path: Path) -> tuple[bool, str]:
    """Check file is within size limits.

    Returns (is_valid, error_message).
    """
    try:
        size = path.stat().st_size
    except OSError:
        return False, f"Cannot read file: {path}"

    if size > MAX_FILE_SIZE:
        mb = size / (1024 * 1024)
        return False, f"File too large ({mb:.1f} MB > {MAX_FILE_SIZE // (1024 * 1024)} MB limit): {path}"

    return True, ""


def validate_yaml_content(content: str) -> tuple[bool, str]:
    """Basic validation of YAML content before parsing.

    Returns (is_valid, error_message).
    """
    # Check for null bytes (binary file)
    if "\x00" in content:
        return False, "File appears to be binary (contains null bytes)"

    return True, ""
