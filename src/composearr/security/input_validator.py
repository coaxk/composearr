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


# Maximum number of lines in a compose file
MAX_YAML_LINES = 10_000

# Maximum nesting depth indicator (repeated spaces)
MAX_NESTING_DEPTH = 50


def validate_yaml_content(content: str) -> tuple[bool, str]:
    """Basic validation of YAML content before parsing.

    Returns (is_valid, error_message).
    """
    # Check for null bytes (binary file)
    if "\x00" in content:
        return False, "File appears to be binary (contains null bytes)"

    # Check for excessive line count
    line_count = content.count("\n") + 1
    if line_count > MAX_YAML_LINES:
        return False, f"File has {line_count} lines (limit: {MAX_YAML_LINES})"

    # Check for YAML alias bombs (e.g., billion laughs attack)
    alias_count = content.count("*") + content.count("<<:")
    if alias_count > 100:
        return False, "File contains excessive YAML aliases (potential alias bomb)"

    return True, ""
