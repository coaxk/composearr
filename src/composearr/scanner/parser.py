"""Parse compose files with ruamel.yaml (comment-preserving)."""

from __future__ import annotations

from pathlib import Path

from ruamel.yaml import YAML
from ruamel.yaml.error import YAMLError

from composearr.models import ComposeFile
from composearr.security.input_validator import MAX_FILE_SIZE, validate_yaml_content

_yaml = YAML()
_yaml.preserve_quotes = True


def parse_compose_file(file_path: Path) -> ComposeFile:
    """Parse a compose file, returning a ComposeFile with data or error."""
    cf = ComposeFile(path=file_path)

    # File size check
    try:
        size = file_path.stat().st_size
        if size > MAX_FILE_SIZE:
            cf.parse_error = f"File too large ({size / (1024*1024):.1f} MB)"
            return cf
    except OSError:
        pass

    try:
        raw = file_path.read_text(encoding="utf-8")
    except OSError as e:
        cf.parse_error = f"Cannot read file: {e}"
        return cf

    # Content validation
    is_valid, err = validate_yaml_content(raw)
    if not is_valid:
        cf.parse_error = err
        return cf

    cf.raw_content = raw

    if not raw.strip():
        cf.parse_error = "File is empty"
        return cf

    try:
        data = _yaml.load(raw)
    except YAMLError as e:
        cf.parse_error = f"YAML parse error: {e}"
        return cf

    if not isinstance(data, dict):
        cf.parse_error = "File does not contain a YAML mapping"
        return cf

    cf.data = data
    return cf


def find_line_number(raw_content: str, key: str, value: str | None = None) -> int | None:
    """Find the line number of a key (and optionally value) in raw YAML content."""
    for i, line in enumerate(raw_content.splitlines(), start=1):
        stripped = line.strip()
        if value is not None:
            if key in stripped and value in stripped:
                return i
        elif key in stripped:
            return i
    return None


def find_service_line(raw_content: str, service_name: str) -> int | None:
    """Find the line where a service definition starts."""
    lines = raw_content.splitlines()
    in_services = False
    for i, line in enumerate(lines, start=1):
        stripped = line.strip()
        if stripped.startswith("services:"):
            in_services = True
            continue
        if in_services and not line.startswith(" ") and not line.startswith("\t") and stripped:
            in_services = False
        if in_services and stripped.startswith(f"{service_name}:"):
            return i
    return None
