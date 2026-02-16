"""Audit history tracking and trend analysis."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import List, Optional


@dataclass
class AuditHistoryEntry:
    """Single audit history entry."""

    timestamp: str  # ISO format
    stack_path: str
    files_scanned: int
    services_scanned: int

    # Issue counts
    errors: int
    warnings: int
    infos: int
    total_issues: int
    fixable_issues: int

    # Score
    score: int
    grade: str

    # Category breakdown
    security_score: int
    reliability_score: int
    consistency_score: int
    network_score: int

    # Top rules by issue count — [(rule_id, count), ...]
    top_rules: list = field(default_factory=list)

    # Duration
    duration_seconds: float = 0.0


@dataclass
class AuditTrend:
    """Trend analysis between two audits."""

    previous_score: int
    current_score: int
    score_delta: int

    previous_issues: int
    current_issues: int
    issues_delta: int

    previous_grade: str
    current_grade: str

    improved: bool

    def summary(self) -> str:
        """Human-readable trend summary."""
        if self.improved:
            return (
                f"Improved: {self.previous_grade} -> {self.current_grade} "
                f"(+{self.score_delta} points, {self.issues_delta:+d} issues)"
            )
        elif self.score_delta < 0:
            return (
                f"Declined: {self.previous_grade} -> {self.current_grade} "
                f"({self.score_delta} points, {self.issues_delta:+d} issues)"
            )
        else:
            return f"Stable: {self.current_grade} ({self.issues_delta:+d} issues)"


class AuditHistory:
    """Manages audit history storage and retrieval."""

    def __init__(self, stack_path: Path) -> None:
        self.stack_path = Path(stack_path).resolve()
        self.history_dir = self.stack_path / ".composearr" / "history"

    def _ensure_dir(self) -> None:
        """Create history directory if needed."""
        self.history_dir.mkdir(parents=True, exist_ok=True)

    def save_audit(
        self,
        issues: list,
        score: object,
        files_scanned: int,
        services_scanned: int,
        duration_seconds: float = 0.0,
    ) -> Path:
        """Save audit results to history.

        Args:
            issues: List of LintIssue objects.
            score: StackScore object with overall, grade, breakdown, etc.
            files_scanned: Number of compose files scanned.
            services_scanned: Total services found.
            duration_seconds: How long the audit took.

        Returns:
            Path to the saved history file.
        """
        self._ensure_dir()

        # Count fixable issues
        fixable = sum(1 for i in issues if getattr(i, "fix_available", False))

        # Get top 5 rules by issue count
        rule_counts: dict[str, int] = {}
        for issue in issues:
            rid = getattr(issue, "rule_id", "unknown")
            rule_counts[rid] = rule_counts.get(rid, 0) + 1
        top_rules = sorted(rule_counts.items(), key=lambda x: x[1], reverse=True)[:5]

        # Extract score fields safely
        breakdown = getattr(score, "breakdown", None)

        entry = AuditHistoryEntry(
            timestamp=datetime.now().isoformat(),
            stack_path=str(self.stack_path),
            files_scanned=files_scanned,
            services_scanned=services_scanned,
            errors=getattr(score, "error_count", 0),
            warnings=getattr(score, "warning_count", 0),
            infos=getattr(score, "info_count", 0),
            total_issues=len(issues),
            fixable_issues=fixable,
            score=getattr(score, "overall", 0),
            grade=getattr(score, "grade", "?"),
            security_score=getattr(breakdown, "security", 100) if breakdown else 100,
            reliability_score=getattr(breakdown, "reliability", 100) if breakdown else 100,
            consistency_score=getattr(breakdown, "consistency", 100) if breakdown else 100,
            network_score=getattr(breakdown, "network", 100) if breakdown else 100,
            top_rules=top_rules,
            duration_seconds=duration_seconds,
        )

        # Save to file (microsecond precision to avoid collisions)
        filename = f"audit_{datetime.now().strftime('%Y%m%d_%H%M%S_%f')}.json"
        filepath = self.history_dir / filename

        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(asdict(entry), f, indent=2)

        return filepath

    def get_recent(self, limit: int = 10) -> List[AuditHistoryEntry]:
        """Get recent audit history entries, newest first."""
        if not self.history_dir.is_dir():
            return []

        files = sorted(self.history_dir.glob("audit_*.json"), reverse=True)

        entries: list[AuditHistoryEntry] = []
        for filepath in files[:limit]:
            try:
                with open(filepath, encoding="utf-8") as f:
                    data = json.load(f)
                # Ensure top_rules is list of lists (JSON round-trips tuples to lists)
                if "top_rules" in data:
                    data["top_rules"] = [
                        list(pair) if isinstance(pair, (list, tuple)) else pair
                        for pair in data.get("top_rules", [])
                    ]
                entries.append(AuditHistoryEntry(**data))
            except (json.JSONDecodeError, TypeError, KeyError):
                continue  # Skip corrupt files

        return entries

    def get_trend(self) -> Optional[AuditTrend]:
        """Get trend between last two audits. Returns None if < 2 audits."""
        recent = self.get_recent(limit=2)

        if len(recent) < 2:
            return None

        current = recent[0]
        previous = recent[1]

        score_delta = current.score - previous.score
        issues_delta = current.total_issues - previous.total_issues
        improved = score_delta > 0 or (score_delta == 0 and issues_delta < 0)

        return AuditTrend(
            previous_score=previous.score,
            current_score=current.score,
            score_delta=score_delta,
            previous_issues=previous.total_issues,
            current_issues=current.total_issues,
            issues_delta=issues_delta,
            previous_grade=previous.grade,
            current_grade=current.grade,
            improved=improved,
        )

    def get_score_history(self, limit: int = 30) -> List[tuple]:
        """Get (timestamp_str, score) pairs for sparkline/chart, oldest first."""
        recent = self.get_recent(limit=limit)
        return [(e.timestamp, e.score) for e in reversed(recent)]

    def entry_count(self) -> int:
        """Count total history entries without loading them."""
        if not self.history_dir.is_dir():
            return 0
        return len(list(self.history_dir.glob("audit_*.json")))

    def cleanup(self, max_entries: int = 100) -> int:
        """Remove oldest entries beyond max_entries. Returns count removed."""
        if not self.history_dir.is_dir():
            return 0

        files = sorted(self.history_dir.glob("audit_*.json"), reverse=True)
        removed = 0
        for filepath in files[max_entries:]:
            try:
                filepath.unlink()
                removed += 1
            except OSError:
                pass
        return removed


def make_sparkline(scores: list[int]) -> str:
    """Create a sparkline string from a list of scores (0-100)."""
    if not scores:
        return ""

    chars = "\u2581\u2582\u2583\u2584\u2585\u2586\u2587\u2588"
    min_score = min(scores)
    max_score = max(scores)
    score_range = max_score - min_score or 1

    return "".join(
        chars[min(7, int((score - min_score) / score_range * 7))]
        for score in scores
    )
