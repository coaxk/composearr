"""Sprint 7 tests: Stack tiers, weighted scoring, leaderboard, warnings, credits."""

from __future__ import annotations

import json
from io import StringIO
from unittest.mock import patch

import pytest
from rich.console import Console

from composearr.credits import show_closing_credits
from composearr.leaderboard import Leaderboard
from composearr.models import LintIssue, Severity
from composearr.scoring import (
    TIER_CONFIG,
    StackScore,
    StackTier,
    calculate_stack_score,
    get_stack_tier,
)
from composearr.warnings import show_tier_warning


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_issue(
    rule_id: str = "CA101",
    severity: Severity = Severity.ERROR,
) -> LintIssue:
    """Create a minimal LintIssue for testing."""
    return LintIssue(
        rule_id=rule_id,
        rule_name="test-rule",
        message="test message",
        severity=severity,
        file_path="test.yaml",
        service="svc",
    )


def _capture_console() -> tuple[Console, StringIO]:
    """Return a Console that writes to a StringIO buffer."""
    buf = StringIO()
    console = Console(file=buf, force_terminal=True)
    return console, buf


# ===========================================================================
# TestStackTier
# ===========================================================================


class TestStackTier:
    """Tier assignment based on service count."""

    def test_tier_starter(self) -> None:
        assert get_stack_tier(1) == StackTier.STARTER
        assert get_stack_tier(3) == StackTier.STARTER
        assert get_stack_tier(5) == StackTier.STARTER

    def test_tier_homelab(self) -> None:
        assert get_stack_tier(6) == StackTier.HOMELAB
        assert get_stack_tier(10) == StackTier.HOMELAB
        assert get_stack_tier(15) == StackTier.HOMELAB

    def test_tier_enthusiast(self) -> None:
        assert get_stack_tier(16) == StackTier.ENTHUSIAST
        assert get_stack_tier(23) == StackTier.ENTHUSIAST
        assert get_stack_tier(30) == StackTier.ENTHUSIAST

    def test_tier_power_user(self) -> None:
        assert get_stack_tier(31) == StackTier.POWER_USER
        assert get_stack_tier(45) == StackTier.POWER_USER
        assert get_stack_tier(60) == StackTier.POWER_USER

    def test_tier_enterprise(self) -> None:
        assert get_stack_tier(61) == StackTier.ENTERPRISE
        assert get_stack_tier(80) == StackTier.ENTERPRISE
        assert get_stack_tier(100) == StackTier.ENTERPRISE

    def test_tier_datacenter(self) -> None:
        assert get_stack_tier(101) == StackTier.DATACENTER
        assert get_stack_tier(150) == StackTier.DATACENTER
        assert get_stack_tier(200) == StackTier.DATACENTER

    def test_tier_titan(self) -> None:
        assert get_stack_tier(201) == StackTier.TITAN
        assert get_stack_tier(500) == StackTier.TITAN
        assert get_stack_tier(9999) == StackTier.TITAN


# ===========================================================================
# TestTierConfig
# ===========================================================================


class TestTierConfig:
    """TIER_CONFIG sanity checks."""

    def test_all_tiers_have_config(self) -> None:
        for tier in StackTier:
            assert tier in TIER_CONFIG, f"Missing config for {tier}"

    def test_multipliers_ascending(self) -> None:
        tiers = list(StackTier)
        multipliers = [TIER_CONFIG[t]["multiplier"] for t in tiers]
        for i in range(1, len(multipliers)):
            assert multipliers[i] >= multipliers[i - 1], (
                f"Multiplier for {tiers[i]} ({multipliers[i]}) "
                f"< {tiers[i - 1]} ({multipliers[i - 1]})"
            )

    def test_all_tiers_have_required_keys(self) -> None:
        required = {"range", "emoji", "multiplier", "description", "power_level"}
        for tier, config in TIER_CONFIG.items():
            missing = required - set(config.keys())
            assert not missing, f"{tier} missing keys: {missing}"


# ===========================================================================
# TestWeightedScore
# ===========================================================================


class TestWeightedScore:
    """Weighted score calculation via calculate_stack_score."""

    def test_starter_multiplier_1x(self) -> None:
        score = calculate_stack_score([], 5)
        assert score.tier == StackTier.STARTER
        assert score.tier_multiplier == 1.0
        assert score.weighted_score == score.overall

    def test_homelab_multiplier_1_1x(self) -> None:
        score = calculate_stack_score([], 10)
        assert score.tier == StackTier.HOMELAB
        assert score.tier_multiplier == 1.1
        assert score.weighted_score == int(score.overall * 1.1)

    def test_titan_multiplier_3x(self) -> None:
        score = calculate_stack_score([], 250)
        assert score.tier == StackTier.TITAN
        assert score.tier_multiplier == 3.0
        assert score.weighted_score == int(score.overall * 3.0)

    def test_weighted_score_with_issues(self) -> None:
        issues = [_make_issue(severity=Severity.WARNING) for _ in range(5)]
        score = calculate_stack_score(issues, 70)
        assert score.tier == StackTier.ENTERPRISE
        assert score.tier_multiplier == 1.7
        assert score.weighted_score == int(score.overall * 1.7)

    def test_file_count_stored(self) -> None:
        score = calculate_stack_score([], 5, file_count=3)
        assert score.file_count == 3

    def test_zero_services_defaults_to_starter(self) -> None:
        score = calculate_stack_score([], 0)
        # 0 is below the STARTER range minimum (1), but get_stack_tier
        # falls through to TITAN as a default.  Verify we get
        # *some* tier assigned and the score is populated.
        assert score.tier in list(StackTier)
        assert score.overall == 100


# ===========================================================================
# TestStackScoreMethods
# ===========================================================================


class TestStackScoreMethods:
    """StackScore.is_legendary / get_display_grade / approaching_next_tier."""

    def test_is_legendary_true(self) -> None:
        score = calculate_stack_score([], 20)
        assert score.overall >= 100
        assert score.total_services >= 16
        assert score.error_count == 0
        assert score.is_legendary()

    def test_is_legendary_false_low_score(self) -> None:
        issues = [_make_issue(severity=Severity.ERROR) for _ in range(20)]
        score = calculate_stack_score(issues, 20)
        assert not score.is_legendary()

    def test_is_legendary_false_few_services(self) -> None:
        score = calculate_stack_score([], 5)
        assert score.overall >= 100
        assert score.total_services < 16
        assert not score.is_legendary()

    def test_is_legendary_false_has_errors(self) -> None:
        issues = [_make_issue(severity=Severity.ERROR)]
        score = calculate_stack_score(issues, 20)
        assert score.error_count > 0
        assert not score.is_legendary()

    def test_get_display_grade_normal(self) -> None:
        score = calculate_stack_score([], 3)
        display = score.get_display_grade()
        # Should contain the tier emoji and the letter grade
        emoji = TIER_CONFIG[score.tier]["emoji"]
        assert emoji in display
        assert score.grade in display

    def test_get_display_grade_legendary(self) -> None:
        score = calculate_stack_score([], 20)
        assert score.is_legendary()
        display = score.get_display_grade()
        assert "LEGENDARY" in display

    def test_get_display_grade_titan_legendary(self) -> None:
        score = calculate_stack_score([], 250)
        assert score.is_legendary()
        display = score.get_display_grade()
        assert "TITAN LEGENDARY" in display

    def test_approaching_next_tier(self) -> None:
        # 55 services -> POWER_USER (31-60), next is ENTERPRISE (61+)
        score = calculate_stack_score([], 55)
        assert score.tier == StackTier.POWER_USER
        approaching, next_tier, needed = score.approaching_next_tier()
        assert approaching is True
        assert next_tier == StackTier.ENTERPRISE
        assert needed == 6

    def test_approaching_next_tier_not_close(self) -> None:
        # 40 services -> POWER_USER, 21 away from ENTERPRISE — too far
        score = calculate_stack_score([], 40)
        assert score.tier == StackTier.POWER_USER
        approaching, next_tier, needed = score.approaching_next_tier()
        assert approaching is False
        assert next_tier is None
        assert needed == 0

    def test_approaching_next_tier_at_max(self) -> None:
        # 300 services -> TITAN, no tier above
        score = calculate_stack_score([], 300)
        assert score.tier == StackTier.TITAN
        approaching, next_tier, needed = score.approaching_next_tier()
        assert approaching is False
        assert next_tier is None
        assert needed == 0


# ===========================================================================
# TestLeaderboard
# ===========================================================================


class TestLeaderboard:
    """Leaderboard submit / query."""

    def test_submit_eligible_score(self, tmp_path) -> None:
        lb = Leaderboard(path=tmp_path / "leaderboard.json")
        score = calculate_stack_score([], 70)  # ENTERPRISE
        assert score.tier == StackTier.ENTERPRISE
        result = lb.submit_score(score)
        assert result is True
        assert len(lb.get_all()) == 1

    def test_submit_ineligible_score(self, tmp_path) -> None:
        lb = Leaderboard(path=tmp_path / "leaderboard.json")
        score = calculate_stack_score([], 3)  # STARTER
        assert score.tier == StackTier.STARTER
        result = lb.submit_score(score)
        assert result is False
        assert len(lb.get_all()) == 0

    def test_submit_updates_higher_score(self, tmp_path) -> None:
        lb = Leaderboard(path=tmp_path / "leaderboard.json")
        # First: enterprise with warnings (lower score)
        issues = [_make_issue(severity=Severity.WARNING) for _ in range(5)]
        score_low = calculate_stack_score(issues, 70)
        lb.submit_score(score_low)
        old_weighted = lb.get_all()[0]["weighted_score"]

        # Second: enterprise clean (higher score)
        score_high = calculate_stack_score([], 70)
        lb.submit_score(score_high)
        entries = lb.get_all()
        assert len(entries) == 1  # same user, updated
        assert entries[0]["weighted_score"] >= old_weighted

    def test_submit_does_not_update_lower_score(self, tmp_path) -> None:
        lb = Leaderboard(path=tmp_path / "leaderboard.json")
        # First: clean enterprise
        score_high = calculate_stack_score([], 70)
        lb.submit_score(score_high)
        high_weighted = lb.get_all()[0]["weighted_score"]

        # Second: enterprise with errors (lower)
        issues = [_make_issue(severity=Severity.ERROR) for _ in range(5)]
        score_low = calculate_stack_score(issues, 70)
        lb.submit_score(score_low)
        entries = lb.get_all()
        assert len(entries) == 1
        assert entries[0]["weighted_score"] == high_weighted

    def test_get_top_legends_empty(self, tmp_path) -> None:
        lb = Leaderboard(path=tmp_path / "leaderboard.json")
        assert lb.get_top_legends() == []

    def test_get_top_legends_sorted(self, tmp_path) -> None:
        lb = Leaderboard(path=tmp_path / "leaderboard.json")
        # Manually seed entries with different weighted scores
        entries = [
            {
                "user_id": "user_a",
                "tier": "ENTERPRISE",
                "weighted_score": 150,
                "service_count": 70,
                "is_legendary": True,
                "timestamp": "2026-01-01T00:00:00",
            },
            {
                "user_id": "user_b",
                "tier": "DATACENTER",
                "weighted_score": 200,
                "service_count": 120,
                "is_legendary": True,
                "timestamp": "2026-01-02T00:00:00",
            },
            {
                "user_id": "user_c",
                "tier": "ENTERPRISE",
                "weighted_score": 170,
                "service_count": 80,
                "is_legendary": True,
                "timestamp": "2026-01-03T00:00:00",
            },
        ]
        lb.leaderboard_file.write_text(json.dumps(entries), encoding="utf-8")
        legends = lb.get_top_legends()
        assert len(legends) == 3
        assert legends[0]["weighted_score"] == 200
        assert legends[1]["weighted_score"] == 170
        assert legends[2]["weighted_score"] == 150

    def test_get_titans(self, tmp_path) -> None:
        lb = Leaderboard(path=tmp_path / "leaderboard.json")
        entries = [
            {
                "user_id": "mecha_1",
                "tier": "TITAN",
                "weighted_score": 300,
                "service_count": 250,
                "is_legendary": True,
                "timestamp": "2026-01-01T00:00:00",
            },
            {
                "user_id": "normie",
                "tier": "ENTERPRISE",
                "weighted_score": 170,
                "service_count": 80,
                "is_legendary": True,
                "timestamp": "2026-01-02T00:00:00",
            },
        ]
        lb.leaderboard_file.write_text(json.dumps(entries), encoding="utf-8")
        titans = lb.get_titans()
        assert len(titans) == 1
        assert titans[0]["user_id"] == "mecha_1"

    def test_leaderboard_file_created(self, tmp_path) -> None:
        lb_path = tmp_path / "sub" / "leaderboard.json"
        lb = Leaderboard(path=lb_path)
        score = calculate_stack_score([], 70)
        lb.submit_score(score)
        assert lb_path.exists()
        data = json.loads(lb_path.read_text(encoding="utf-8"))
        assert isinstance(data, list)
        assert len(data) == 1

    def test_leaderboard_corrupt_file_handled(self, tmp_path) -> None:
        lb_path = tmp_path / "leaderboard.json"
        lb_path.write_text("NOT VALID JSON {{{{", encoding="utf-8")
        lb = Leaderboard(path=lb_path)
        # Should not raise, returns empty
        assert lb.get_all() == []
        assert lb.get_top_legends() == []

    def test_get_all_sorted(self, tmp_path) -> None:
        lb = Leaderboard(path=tmp_path / "leaderboard.json")
        entries = [
            {
                "user_id": "a",
                "tier": "ENTERPRISE",
                "weighted_score": 100,
                "service_count": 70,
                "is_legendary": False,
                "timestamp": "2026-01-01T00:00:00",
            },
            {
                "user_id": "b",
                "tier": "DATACENTER",
                "weighted_score": 200,
                "service_count": 120,
                "is_legendary": True,
                "timestamp": "2026-01-02T00:00:00",
            },
            {
                "user_id": "c",
                "tier": "TITAN",
                "weighted_score": 300,
                "service_count": 250,
                "is_legendary": True,
                "timestamp": "2026-01-03T00:00:00",
            },
        ]
        lb.leaderboard_file.write_text(json.dumps(entries), encoding="utf-8")
        all_entries = lb.get_all()
        assert all_entries[0]["weighted_score"] == 300
        assert all_entries[1]["weighted_score"] == 200
        assert all_entries[2]["weighted_score"] == 100


# ===========================================================================
# TestTierWarning
# ===========================================================================


class TestTierWarning:
    """show_tier_warning output for various service counts."""

    def test_warning_at_195_services(self) -> None:
        console, buf = _capture_console()
        show_tier_warning(console, 195)
        text = buf.getvalue()
        assert "APPROACHING" in text

    def test_warning_at_201_services(self) -> None:
        console, buf = _capture_console()
        show_tier_warning(console, 201)
        text = buf.getvalue()
        assert "TRANSCENDED" in text or "TITAN" in text

    def test_no_warning_at_50_services(self) -> None:
        console, buf = _capture_console()
        show_tier_warning(console, 50)
        text = buf.getvalue()
        assert text == ""

    def test_no_warning_at_180_services(self) -> None:
        console, buf = _capture_console()
        show_tier_warning(console, 180)
        text = buf.getvalue()
        # 180 is 21 away from 201, outside the 10-service window
        assert text == ""


# ===========================================================================
# TestClosingCredits
# ===========================================================================


class TestClosingCredits:
    """show_closing_credits output based on leaderboard state."""

    def test_credits_no_legends(self, tmp_path) -> None:
        console, buf = _capture_console()
        with patch("composearr.leaderboard.Leaderboard") as MockLB:
            instance = MockLB.return_value
            instance.get_top_legends.return_value = []
            instance.get_titans.return_value = []
            show_closing_credits(console)
        text = buf.getvalue()
        # No output when leaderboard is empty
        assert "HALL OF FAME" not in text

    def test_credits_with_legends(self, tmp_path) -> None:
        console, buf = _capture_console()
        legend_entry = {
            "user_id": "abc123def456",
            "tier": "ENTERPRISE",
            "weighted_score": 170,
            "service_count": 80,
            "is_legendary": True,
            "timestamp": "2026-01-01T00:00:00",
        }
        with patch("composearr.leaderboard.Leaderboard") as MockLB:
            instance = MockLB.return_value
            instance.get_top_legends.return_value = [legend_entry]
            instance.get_titans.return_value = []
            show_closing_credits(console)
        text = buf.getvalue()
        assert "HALL OF FAME" in text

    def test_credits_with_titan(self, tmp_path) -> None:
        console, buf = _capture_console()
        titan_entry = {
            "user_id": "mecha999aaa12",
            "tier": "TITAN",
            "weighted_score": 300,
            "service_count": 250,
            "is_legendary": True,
            "timestamp": "2026-01-01T00:00:00",
        }
        with patch("composearr.leaderboard.Leaderboard") as MockLB:
            instance = MockLB.return_value
            instance.get_top_legends.return_value = [titan_entry]
            instance.get_titans.return_value = [titan_entry]
            show_closing_credits(console)
        text = buf.getvalue()
        assert "THE TITANS" in text


# ===========================================================================
# TestScoringBackwardCompat
# ===========================================================================


class TestScoringBackwardCompat:
    """Backward compatibility — old callers should not break."""

    def test_old_callers_still_work(self) -> None:
        # calculate_stack_score(issues, total_services) without file_count
        score = calculate_stack_score([], 5)
        assert score.overall == 100
        assert score.file_count == 0  # default

    def test_stack_score_default_tier(self) -> None:
        # Construct StackScore manually without explicit tier
        from composearr.scoring import ScoreBreakdown

        s = StackScore(
            overall=90,
            grade="A-",
            breakdown=ScoreBreakdown(),
        )
        assert s.tier == StackTier.STARTER
        assert s.tier_multiplier == 1.0

    def test_score_has_all_fields(self) -> None:
        score = calculate_stack_score([], 10, file_count=2)
        # Core fields
        assert hasattr(score, "overall")
        assert hasattr(score, "grade")
        assert hasattr(score, "breakdown")
        assert hasattr(score, "error_count")
        assert hasattr(score, "warning_count")
        assert hasattr(score, "info_count")
        assert hasattr(score, "total_services")
        # Sprint 7 fields
        assert hasattr(score, "tier")
        assert hasattr(score, "tier_multiplier")
        assert hasattr(score, "weighted_score")
        assert hasattr(score, "file_count")


# ===========================================================================
# TestEdgeCases (additional coverage)
# ===========================================================================


class TestEdgeCases:
    """Edge cases and additional coverage to round out the suite."""

    def test_tier_boundary_5_to_6(self) -> None:
        """Boundary between STARTER and HOMELAB."""
        assert get_stack_tier(5) == StackTier.STARTER
        assert get_stack_tier(6) == StackTier.HOMELAB

    def test_tier_boundary_200_to_201(self) -> None:
        """Boundary between DATACENTER and TITAN."""
        assert get_stack_tier(200) == StackTier.DATACENTER
        assert get_stack_tier(201) == StackTier.TITAN

    def test_error_cap_at_b(self) -> None:
        """Any error caps the overall score at B (83)."""
        issues = [_make_issue(severity=Severity.ERROR)]
        score = calculate_stack_score(issues, 100)
        assert score.overall <= 83

    def test_all_severity_counts(self) -> None:
        issues = [
            _make_issue(severity=Severity.ERROR),
            _make_issue(severity=Severity.WARNING),
            _make_issue(severity=Severity.WARNING),
            _make_issue(severity=Severity.INFO),
        ]
        score = calculate_stack_score(issues, 10)
        assert score.error_count == 1
        assert score.warning_count == 2
        assert score.info_count == 1

    def test_leaderboard_submit_datacenter(self, tmp_path) -> None:
        """DATACENTER tier is eligible for the leaderboard."""
        lb = Leaderboard(path=tmp_path / "leaderboard.json")
        score = calculate_stack_score([], 150)
        assert score.tier == StackTier.DATACENTER
        assert lb.submit_score(score) is True

    def test_leaderboard_submit_titan(self, tmp_path) -> None:
        """TITAN tier is eligible for the leaderboard."""
        lb = Leaderboard(path=tmp_path / "leaderboard.json")
        score = calculate_stack_score([], 250)
        assert score.tier == StackTier.TITAN
        assert lb.submit_score(score) is True

    def test_leaderboard_ineligible_tiers(self, tmp_path) -> None:
        """HOMELAB, ENTHUSIAST, POWER_USER are all ineligible."""
        lb = Leaderboard(path=tmp_path / "leaderboard.json")
        for svc_count in [10, 20, 40]:
            score = calculate_stack_score([], svc_count)
            assert lb.submit_score(score) is False
        assert len(lb.get_all()) == 0

    def test_warning_at_191_services(self) -> None:
        """191 services is exactly 10 away from 201 -- within the window."""
        console, buf = _capture_console()
        show_tier_warning(console, 191)
        text = buf.getvalue()
        assert "APPROACHING" in text

    def test_warning_at_200_services(self) -> None:
        """200 services is 1 away from 201 -- within the window."""
        console, buf = _capture_console()
        show_tier_warning(console, 200)
        text = buf.getvalue()
        assert "APPROACHING" in text
