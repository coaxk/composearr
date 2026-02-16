"""SARIF 2.1.0 output formatter for GitHub Advanced Security."""

from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING

from composearr import __version__
from composearr.models import Severity
from composearr.rules.base import get_all_rules

if TYPE_CHECKING:
    from composearr.models import FormatOptions, ScanResult


_SARIF_LEVELS = {
    Severity.ERROR: "error",
    Severity.WARNING: "warning",
    Severity.INFO: "note",
}


def format_sarif(result: ScanResult, root_path: str, options: FormatOptions | None = None) -> str:
    """Format scan results as SARIF 2.1.0 JSON."""
    all_rules = get_all_rules()
    rule_index = {r.id: idx for idx, r in enumerate(sorted(all_rules, key=lambda x: x.id))}

    rules = []
    for r in sorted(all_rules, key=lambda x: x.id):
        rule_def: dict = {
            "id": r.id,
            "name": r.name,
            "shortDescription": {"text": r.description},
            "defaultConfiguration": {
                "level": _SARIF_LEVELS.get(r.severity, "note"),
            },
            "properties": {
                "category": r.category,
            },
        }
        rules.append(rule_def)

    results = []
    for issue in result.all_issues:
        sarif_result: dict = {
            "ruleId": issue.rule_id,
            "ruleIndex": rule_index.get(issue.rule_id, 0),
            "level": _SARIF_LEVELS.get(issue.severity, "note"),
            "message": {"text": issue.message},
            "locations": [
                {
                    "physicalLocation": {
                        "artifactLocation": {
                            "uri": Path(issue.file_path).as_posix(),
                        },
                    },
                }
            ],
        }

        if issue.line:
            sarif_result["locations"][0]["physicalLocation"]["region"] = {
                "startLine": issue.line,
            }

        if issue.suggested_fix:
            sarif_result["fixes"] = [
                {
                    "description": {"text": issue.suggested_fix},
                }
            ]

        results.append(sarif_result)

    sarif = {
        "$schema": "https://raw.githubusercontent.com/oasis-tcs/sarif-spec/main/sarif-2.1/schema/sarif-schema-2.1.0.json",
        "version": "2.1.0",
        "runs": [
            {
                "tool": {
                    "driver": {
                        "name": "composearr",
                        "version": __version__,
                        "informationUri": "https://github.com/coaxk/composearr",
                        "rules": rules,
                    }
                },
                "results": results,
            }
        ],
    }

    return json.dumps(sarif, indent=2)
