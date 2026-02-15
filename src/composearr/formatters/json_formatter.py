"""JSON output formatter for CI/CD integration."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from composearr.models import FormatOptions, ScanResult


def format_json(result: ScanResult, root_path: str, options: FormatOptions | None = None) -> str:
    """Format scan results as JSON."""
    issues = []
    for issue in result.all_issues:
        entry: dict = {
            "rule_id": issue.rule_id,
            "rule_name": issue.rule_name,
            "severity": issue.severity.value,
            "message": issue.message,
            "file": issue.file_path,
        }
        if issue.line is not None:
            entry["line"] = issue.line
        if issue.service:
            entry["service"] = issue.service
        if issue.suggested_fix:
            entry["suggested_fix"] = issue.suggested_fix
        if issue.fix_available:
            entry["fix_available"] = True
        issues.append(entry)

    output = {
        "version": "1.0",
        "root": root_path,
        "summary": {
            "files_scanned": len(result.compose_files),
            "services_scanned": result.total_services,
            "errors": result.error_count,
            "warnings": result.warning_count,
            "info": result.info_count,
            "fixable": result.fixable_count,
        },
        "issues": issues,
    }

    if result.skipped_managed:
        output["skipped_managed"] = result.skipped_managed

    return json.dumps(output, indent=2)
