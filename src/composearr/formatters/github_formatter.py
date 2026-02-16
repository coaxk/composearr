"""GitHub Actions annotation formatter."""

from __future__ import annotations

from typing import TYPE_CHECKING

from composearr.models import Severity

if TYPE_CHECKING:
    from composearr.models import FormatOptions, ScanResult


_GH_LEVELS = {
    Severity.ERROR: "error",
    Severity.WARNING: "warning",
    Severity.INFO: "notice",
}


def _escape_annotation(text: str) -> str:
    """Escape special characters for GitHub Actions annotations."""
    return text.replace("%", "%25").replace("\n", "%0A").replace("\r", "%0D").replace("::", ": :")


def format_github(result: ScanResult, root_path: str, options: FormatOptions | None = None) -> str:
    """Format scan results as GitHub Actions annotations.

    Format: ::{level} file={path},line={line}::{message}
    """
    lines = []
    for issue in result.all_issues:
        level = _GH_LEVELS.get(issue.severity, "notice")
        parts = [f"::{level} file={issue.file_path}"]
        if issue.line:
            parts[0] += f",line={issue.line}"
        msg = f"{issue.rule_id}: {_escape_annotation(issue.message)}"
        if issue.service:
            msg += f" ({_escape_annotation(issue.service)})"
        lines.append(f"{parts[0]}::{msg}")

    return "\n".join(lines)
