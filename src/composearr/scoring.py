"""Stack Health Score calculation."""

from __future__ import annotations

from dataclasses import dataclass, field

from composearr.models import LintIssue, Severity


# Rule ID prefix -> category mapping
_CATEGORY_MAP = {
    "CA0": "security",      # Images, registries
    "CA1": "security",      # Secrets
    "CA2": "reliability",   # Healthchecks, restart policies
    "CA3": "network",       # Ports, topology
    "CA4": "consistency",   # PUID/PGID, TZ, env vars
    "CA5": "reliability",   # Resource limits, logging
    "CA6": "consistency",   # Arrstack-specific
    "CA7": "reliability",   # Volume best practices
    "CA8": "security",      # Security hardening
    "CA9": "reliability",   # Advanced resource/operational
}


def _categorize(rule_id: str) -> str:
    """Map a rule ID to its score category."""
    prefix = rule_id[:3]
    return _CATEGORY_MAP.get(prefix, "reliability")


@dataclass
class ScoreBreakdown:
    """Score breakdown by category."""

    security: int = 100
    reliability: int = 100
    consistency: int = 100
    network: int = 100

    @property
    def overall(self) -> int:
        """Weighted average — security matters most."""
        return (
            self.security * 3
            + self.reliability * 3
            + self.consistency * 2
            + self.network * 2
        ) // 10


@dataclass
class StackScore:
    """Complete stack score with grade and breakdown."""

    overall: int
    grade: str
    breakdown: ScoreBreakdown
    error_count: int = 0
    warning_count: int = 0
    info_count: int = 0
    total_services: int = 0


def score_to_grade(score: int) -> str:
    """Convert numeric score (0-100) to letter grade."""
    if score >= 97:
        return "A+"
    if score >= 93:
        return "A"
    if score >= 90:
        return "A-"
    if score >= 87:
        return "B+"
    if score >= 83:
        return "B"
    if score >= 80:
        return "B-"
    if score >= 77:
        return "C+"
    if score >= 73:
        return "C"
    if score >= 70:
        return "C-"
    if score >= 67:
        return "D+"
    if score >= 63:
        return "D"
    if score >= 60:
        return "D-"
    return "F"


def _category_score(issues: list[LintIssue], total_services: int) -> int:
    """Calculate score for a category, normalized by service count."""
    if total_services == 0:
        return 100

    # Points lost per issue, scaled by severity
    points_lost = 0.0
    for issue in issues:
        if issue.severity == Severity.ERROR:
            points_lost += 10
        elif issue.severity == Severity.WARNING:
            points_lost += 3
        else:
            points_lost += 0.5

    # Normalize: more services = more possible issues, so scale deductions
    # A stack with 30 services and 5 warnings shouldn't score much lower than
    # a stack with 3 services and 0 warnings
    scale = max(1.0, total_services / 5.0)
    normalized = points_lost / scale

    return max(0, min(100, int(100 - normalized)))


def calculate_stack_score(
    issues: list[LintIssue],
    total_services: int = 0,
) -> StackScore:
    """Calculate the stack health score from audit issues.

    Args:
        issues: All issues from the audit (including cross-file).
        total_services: Total number of services scanned.

    Returns:
        StackScore with overall grade and category breakdown.
    """
    error_count = sum(1 for i in issues if i.severity == Severity.ERROR)
    warning_count = sum(1 for i in issues if i.severity == Severity.WARNING)
    info_count = sum(1 for i in issues if i.severity == Severity.INFO)

    # Bucket issues by category
    by_category: dict[str, list[LintIssue]] = {
        "security": [],
        "reliability": [],
        "consistency": [],
        "network": [],
    }
    for issue in issues:
        cat = _categorize(issue.rule_id)
        by_category.setdefault(cat, []).append(issue)

    breakdown = ScoreBreakdown(
        security=_category_score(by_category["security"], total_services),
        reliability=_category_score(by_category["reliability"], total_services),
        consistency=_category_score(by_category["consistency"], total_services),
        network=_category_score(by_category["network"], total_services),
    )

    overall = breakdown.overall

    # Hard cap: any unresolved error means max B
    if error_count > 0 and overall > 83:
        overall = 83

    grade = score_to_grade(overall)

    return StackScore(
        overall=overall,
        grade=grade,
        breakdown=breakdown,
        error_count=error_count,
        warning_count=warning_count,
        info_count=info_count,
        total_services=total_services,
    )
