"""Inline suppression parser for ComposeArr.

Supports two comment formats:
    # composearr-ignore: CA001,CA201
    # composearr: ignore CA001,CA201
    # composearr-ignore-file
    # composearr-ignore-service
"""

from __future__ import annotations

import re

# Import rule name mapping for accepting rule names as well as IDs
from composearr.config import _RULE_NAME_TO_ID

_IGNORE_PATTERNS = [
    re.compile(r"#\s*composearr-ignore:\s*(.+)"),
    re.compile(r"#\s*composearr:\s*ignore\s+(.+)"),
]
_IGNORE_FILE_PATTERN = re.compile(r"#\s*composearr-ignore-file")
_IGNORE_SERVICE_PATTERN = re.compile(r"#\s*composearr-ignore-service")


class SuppressionParser:
    """Parse inline suppression comments from compose YAML content."""

    def parse(self, raw_content: str) -> tuple[bool, set[str], dict[int, set[str]]]:
        """Parse suppression comments from raw YAML content.

        Returns:
            (file_ignored, service_ignored_set, line_suppressions_dict)
            - file_ignored: True if # composearr-ignore-file found
            - service_ignored_set: service names marked with composearr-ignore-service
            - line_suppressions_dict: {line_number: set of rule IDs suppressed}
        """
        file_ignored = False
        line_suppressions: dict[int, set[str]] = {}

        for i, line in enumerate(raw_content.splitlines(), start=1):
            # File-level suppression
            if _IGNORE_FILE_PATTERN.search(line):
                file_ignored = True
                break

            # Line-level suppression — try both patterns
            for pattern in _IGNORE_PATTERNS:
                match = pattern.search(line)
                if match:
                    rules_str = match.group(1).strip()
                    rule_ids = set()
                    for r in rules_str.split(","):
                        r = r.strip()
                        rule_id = _RULE_NAME_TO_ID.get(
                            r, r.upper() if r.startswith("CA") or r.startswith("ca") else r
                        )
                        rule_ids.add(rule_id)

                    # Suppression applies to this line and the next line
                    line_suppressions.setdefault(i, set()).update(rule_ids)
                    line_suppressions.setdefault(i + 1, set()).update(rule_ids)
                    break  # Don't try second pattern if first matched

        return file_ignored, set(), line_suppressions
