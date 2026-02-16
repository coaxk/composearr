"""Batch operations for CI/CD — fix all issues across compose files without prompts."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from composearr.models import LintIssue, Severity


# Severity ordering for comparisons
_SEVERITY_ORDER = {"error": 2, "warning": 1, "info": 0}


@dataclass
class BatchResult:
    """Result of a batch fix operation."""

    files_processed: int = 0
    issues_found: int = 0
    issues_fixed: int = 0
    issues_unfixable: int = 0
    errors: list[str] = field(default_factory=list)
    fixed_rules: dict[str, int] = field(default_factory=dict)

    @property
    def success(self) -> bool:
        return len(self.errors) == 0

    @property
    def exit_code(self) -> int:
        """Return appropriate exit code for CI/CD."""
        if self.errors:
            return 2  # Errors during processing
        if self.issues_found > self.issues_fixed:
            return 1  # Some issues remain unfixed
        return 0


class BatchProcessor:
    """Process multiple compose files in batch mode (CI/CD friendly).

    Scans all compose files in a stack directory, runs all rules,
    and optionally auto-fixes everything. Designed for non-interactive
    pipelines where prompting is not possible.
    """

    def __init__(
        self,
        stack_path: Path,
        auto_approve: bool = False,
        create_backups: bool = True,
    ) -> None:
        self.stack_path = Path(stack_path).resolve()
        self.auto_approve = auto_approve
        self.create_backups = create_backups

    def scan(
        self,
        min_severity: str | None = None,
        rule_ids: list[str] | None = None,
    ) -> tuple[list[LintIssue], BatchResult]:
        """Scan all files and return issues + result summary."""
        from composearr.config import load_config
        from composearr.engine import run_audit

        result = BatchResult()
        config = load_config(self.stack_path)

        try:
            scan_result = run_audit(self.stack_path, config)
        except Exception as e:
            result.errors.append(f"Scan failed: {e}")
            return [], result

        result.files_processed = len(scan_result.compose_files)

        if result.files_processed == 0:
            result.errors.append(f"No compose files found in {self.stack_path}")
            return [], result

        all_issues = list(scan_result.all_issues)

        # Filter by severity
        if min_severity:
            min_level = _SEVERITY_ORDER.get(min_severity, 0)
            all_issues = [
                i for i in all_issues
                if _SEVERITY_ORDER.get(
                    i.severity.value if isinstance(i.severity, Severity) else str(i.severity),
                    0,
                ) >= min_level
            ]

        # Filter by rule IDs
        if rule_ids:
            all_issues = [i for i in all_issues if i.rule_id in rule_ids]

        result.issues_found = len(all_issues)
        fixable = [i for i in all_issues if i.fix_available]
        result.issues_unfixable = len(all_issues) - len(fixable)

        return all_issues, result

    def fix_all(
        self,
        min_severity: str | None = None,
        rule_ids: list[str] | None = None,
    ) -> BatchResult:
        """Scan and fix all issues."""
        from composearr.fixer import apply_fixes

        all_issues, result = self.scan(min_severity, rule_ids)

        if not self.auto_approve:
            return result

        fixable = [i for i in all_issues if i.fix_available]

        if fixable:
            try:
                fix_result = apply_fixes(fixable, create_backup=self.create_backups)
                result.issues_fixed = fix_result.applied

                for issue in fixable[:fix_result.applied]:
                    result.fixed_rules[issue.rule_id] = (
                        result.fixed_rules.get(issue.rule_id, 0) + 1
                    )
            except Exception as e:
                result.errors.append(f"Fix failed: {e}")

        return result
