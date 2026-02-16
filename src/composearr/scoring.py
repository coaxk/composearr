"""Stack Health Score calculation."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

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


class StackTier(Enum):
    """Stack complexity tiers — power levels ascending."""
    STARTER = "STARTER"           # 1-5 services
    HOMELAB = "HOMELAB"           # 6-15 services
    ENTHUSIAST = "ENTHUSIAST"     # 16-30 services
    POWER_USER = "POWER_USER"     # 31-60 services
    ENTERPRISE = "ENTERPRISE"     # 61-100 services
    DATACENTER = "DATACENTER"     # 101-200 services
    MECHA_NECKBEARD = "MECHA_NECKBEARD"  # 201+ services


TIER_CONFIG = {
    StackTier.STARTER: {
        "range": (1, 5),
        "emoji": "\U0001f331",
        "multiplier": 1.0,
        "description": "Learning the ropes",
        "power_level": "Krillin",
    },
    StackTier.HOMELAB: {
        "range": (6, 15),
        "emoji": "\U0001f3e0",
        "multiplier": 1.1,
        "description": "Typical homelab",
        "power_level": "Yamcha",
    },
    StackTier.ENTHUSIAST: {
        "range": (16, 30),
        "emoji": "\u26a1",
        "multiplier": 1.3,
        "description": "Serious homelabber",
        "power_level": "Piccolo",
    },
    StackTier.POWER_USER: {
        "range": (31, 60),
        "emoji": "\U0001f4aa",
        "multiplier": 1.5,
        "description": "Advanced infrastructure",
        "power_level": "Vegeta",
    },
    StackTier.ENTERPRISE: {
        "range": (61, 100),
        "emoji": "\U0001f3e2",
        "multiplier": 1.7,
        "description": "Production-grade",
        "power_level": "Goku",
    },
    StackTier.DATACENTER: {
        "range": (101, 200),
        "emoji": "\U0001f3ed",
        "multiplier": 2.0,
        "description": "Absolute madlad territory",
        "power_level": "Super Saiyan",
    },
    StackTier.MECHA_NECKBEARD: {
        "range": (201, float("inf")),
        "emoji": "\U0001f916",
        "multiplier": 3.0,
        "description": "THE FINAL BOSS \u2014 Are you even human?",
        "power_level": "Ultra Instinct",
    },
}


def get_stack_tier(service_count: int) -> StackTier:
    """Get tier based on service count."""
    for tier, config in TIER_CONFIG.items():
        min_svc, max_svc = config["range"]
        if min_svc <= service_count <= max_svc:
            return tier
    return StackTier.MECHA_NECKBEARD


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
    """Complete stack score with grade, breakdown, and tier weighting."""

    overall: int
    grade: str
    breakdown: ScoreBreakdown
    error_count: int = 0
    warning_count: int = 0
    info_count: int = 0
    total_services: int = 0
    # Sprint 7: tier weighting
    tier: StackTier = StackTier.STARTER
    tier_multiplier: float = 1.0
    weighted_score: int = 0
    file_count: int = 0

    def get_display_grade(self) -> str:
        """Get display grade with tier emoji."""
        emoji = TIER_CONFIG[self.tier]["emoji"]
        if self.tier == StackTier.MECHA_NECKBEARD and self.is_legendary():
            return f"{emoji} MECHA NECKBEARD LEGENDARY"
        if self.is_legendary():
            return f"{emoji} LEGENDARY"
        return f"{emoji} {self.grade}"

    def is_legendary(self) -> bool:
        """Check legendary status: perfect score, 16+ services, zero errors."""
        return (
            self.overall >= 100
            and self.total_services >= 16
            and self.error_count == 0
        )

    def approaching_next_tier(self) -> tuple[bool, StackTier | None, int]:
        """Check if approaching next tier (within 10 services)."""
        tiers = list(StackTier)
        current_idx = tiers.index(self.tier)
        if current_idx >= len(tiers) - 1:
            return False, None, 0
        next_tier = tiers[current_idx + 1]
        next_min = TIER_CONFIG[next_tier]["range"][0]
        services_needed = next_min - self.total_services
        if 0 < services_needed <= 10:
            return True, next_tier, services_needed
        return False, None, 0


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
    file_count: int = 0,
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

    tier = get_stack_tier(total_services)
    tier_multiplier = TIER_CONFIG[tier]["multiplier"]
    weighted_score = int(overall * tier_multiplier)

    return StackScore(
        overall=overall,
        grade=grade,
        breakdown=breakdown,
        error_count=error_count,
        warning_count=warning_count,
        info_count=info_count,
        total_services=total_services,
        tier=tier,
        tier_multiplier=tier_multiplier,
        weighted_score=weighted_score,
        file_count=file_count,
    )
