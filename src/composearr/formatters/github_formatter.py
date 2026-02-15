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
        msg = f"{issue.rule_id}: {issue.message}"
        if issue.service:
            msg += f" ({issue.service})"
        lines.append(f"{parts[0]}::{msg}")

    return "\n".join(lines)
