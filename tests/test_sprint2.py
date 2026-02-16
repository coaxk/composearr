"""Sprint 2 tests — Audit History + Image Freshness Advisor."""

from __future__ import annotations

import json
import time
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest


# ═══════════════════════════════════════════════════════════════
# AUDIT HISTORY TESTS
# ═══════════════════════════════════════════════════════════════


class TestAuditHistoryEntry:
    """Test AuditHistoryEntry dataclass."""

    def test_create_entry(self):
        from composearr.history import AuditHistoryEntry

        entry = AuditHistoryEntry(
            timestamp="2026-02-17T12:00:00",
            stack_path="/test",
            files_scanned=5,
            services_scanned=12,
            errors=2,
            warnings=5,
            infos=3,
            total_issues=10,
            fixable_issues=4,
            score=75,
            grade="C+",
            security_score=80,
            reliability_score=70,
            consistency_score=90,
            network_score=60,
            top_rules=[["CA001", 3], ["CA201", 2]],
            duration_seconds=1.5,
        )
        assert entry.grade == "C+"
        assert entry.total_issues == 10
        assert entry.fixable_issues == 4

    def test_entry_defaults(self):
        from composearr.history import AuditHistoryEntry

        entry = AuditHistoryEntry(
            timestamp="2026-02-17T12:00:00",
            stack_path="/test",
            files_scanned=0,
            services_scanned=0,
            errors=0,
            warnings=0,
            infos=0,
            total_issues=0,
            fixable_issues=0,
            score=100,
            grade="A+",
            security_score=100,
            reliability_score=100,
            consistency_score=100,
            network_score=100,
        )
        assert entry.top_rules == []
        assert entry.duration_seconds == 0.0


class TestAuditTrend:
    """Test AuditTrend dataclass and summary."""

    def test_improved_trend(self):
        from composearr.history import AuditTrend

        trend = AuditTrend(
            previous_score=70,
            current_score=85,
            score_delta=15,
            previous_issues=10,
            current_issues=5,
            issues_delta=-5,
            previous_grade="C-",
            current_grade="B",
            improved=True,
        )
        assert trend.improved is True
        assert "Improved" in trend.summary()
        assert "C-" in trend.summary()
        assert "B" in trend.summary()

    def test_declined_trend(self):
        from composearr.history import AuditTrend

        trend = AuditTrend(
            previous_score=90,
            current_score=75,
            score_delta=-15,
            previous_issues=3,
            current_issues=8,
            issues_delta=5,
            previous_grade="A-",
            current_grade="C+",
            improved=False,
        )
        assert trend.improved is False
        assert "Declined" in trend.summary()

    def test_stable_trend(self):
        from composearr.history import AuditTrend

        trend = AuditTrend(
            previous_score=85,
            current_score=85,
            score_delta=0,
            previous_issues=5,
            current_issues=5,
            issues_delta=0,
            previous_grade="B",
            current_grade="B",
            improved=False,
        )
        assert "Stable" in trend.summary()

    def test_stable_fewer_issues(self):
        """Same score but fewer issues = improved."""
        from composearr.history import AuditTrend

        trend = AuditTrend(
            previous_score=85,
            current_score=85,
            score_delta=0,
            previous_issues=5,
            current_issues=3,
            issues_delta=-2,
            previous_grade="B",
            current_grade="B",
            improved=True,
        )
        assert trend.improved is True
        assert "Improved" in trend.summary()


class TestAuditHistory:
    """Test AuditHistory storage, retrieval, and cleanup."""

    def _make_mock_score(self, overall=85, grade="B"):
        """Create a mock StackScore-like object."""
        breakdown = MagicMock()
        breakdown.security = 90
        breakdown.reliability = 80
        breakdown.consistency = 85
        breakdown.network = 75

        score = MagicMock()
        score.overall = overall
        score.grade = grade
        score.breakdown = breakdown
        score.error_count = 1
        score.warning_count = 3
        score.info_count = 2
        return score

    def _make_mock_issues(self, count=5):
        """Create mock issues."""
        issues = []
        for i in range(count):
            issue = MagicMock()
            issue.rule_id = f"CA{i:03d}" if i < 3 else "CA001"
            issue.fix_available = i % 2 == 0
            issues.append(issue)
        return issues

    def test_save_and_load(self, tmp_path):
        from composearr.history import AuditHistory

        hist = AuditHistory(tmp_path)
        score = self._make_mock_score()
        issues = self._make_mock_issues(5)

        filepath = hist.save_audit(
            issues=issues,
            score=score,
            files_scanned=3,
            services_scanned=8,
            duration_seconds=1.2,
        )

        assert filepath.exists()
        assert filepath.suffix == ".json"

        entries = hist.get_recent()
        assert len(entries) == 1
        assert entries[0].files_scanned == 3
        assert entries[0].services_scanned == 8
        assert entries[0].score == 85
        assert entries[0].grade == "B"
        assert entries[0].fixable_issues == 3  # 0, 2, 4 are fixable

    def test_multiple_saves_ordered(self, tmp_path):
        from composearr.history import AuditHistory

        hist = AuditHistory(tmp_path)

        for i in range(5):
            score = self._make_mock_score(overall=70 + i * 5, grade=f"C{i}")
            hist.save_audit(
                issues=self._make_mock_issues(3),
                score=score,
                files_scanned=3,
                services_scanned=8,
            )
            time.sleep(0.1)  # Ensure different timestamps

        entries = hist.get_recent(limit=3)
        assert len(entries) == 3
        # Most recent first
        assert entries[0].score >= entries[-1].score

    def test_get_recent_empty(self, tmp_path):
        from composearr.history import AuditHistory

        hist = AuditHistory(tmp_path)
        entries = hist.get_recent()
        assert entries == []

    def test_get_trend_no_history(self, tmp_path):
        from composearr.history import AuditHistory

        hist = AuditHistory(tmp_path)
        assert hist.get_trend() is None

    def test_get_trend_single_audit(self, tmp_path):
        from composearr.history import AuditHistory

        hist = AuditHistory(tmp_path)
        hist.save_audit(
            issues=self._make_mock_issues(),
            score=self._make_mock_score(),
            files_scanned=3,
            services_scanned=8,
        )
        assert hist.get_trend() is None

    def test_get_trend_two_audits(self, tmp_path):
        from composearr.history import AuditHistory

        hist = AuditHistory(tmp_path)

        # First audit (worse)
        hist.save_audit(
            issues=self._make_mock_issues(10),
            score=self._make_mock_score(overall=65, grade="D+"),
            files_scanned=3,
            services_scanned=8,
        )
        time.sleep(0.1)

        # Second audit (better)
        hist.save_audit(
            issues=self._make_mock_issues(3),
            score=self._make_mock_score(overall=90, grade="A-"),
            files_scanned=3,
            services_scanned=8,
        )

        trend = hist.get_trend()
        assert trend is not None
        assert trend.improved is True
        assert trend.score_delta == 25
        assert trend.current_grade == "A-"
        assert trend.previous_grade == "D+"

    def test_get_score_history(self, tmp_path):
        from composearr.history import AuditHistory

        hist = AuditHistory(tmp_path)

        for i in range(5):
            hist.save_audit(
                issues=self._make_mock_issues(1),
                score=self._make_mock_score(overall=60 + i * 10),
                files_scanned=1,
                services_scanned=1,
            )
            time.sleep(0.1)

        score_history = hist.get_score_history(limit=10)
        assert len(score_history) == 5
        # Oldest first
        scores = [s for _, s in score_history]
        assert scores[0] <= scores[-1]

    def test_entry_count(self, tmp_path):
        from composearr.history import AuditHistory

        hist = AuditHistory(tmp_path)
        assert hist.entry_count() == 0

        hist.save_audit(
            issues=[],
            score=self._make_mock_score(overall=100, grade="A+"),
            files_scanned=1,
            services_scanned=1,
        )
        assert hist.entry_count() == 1

    def test_cleanup(self, tmp_path):
        from composearr.history import AuditHistory

        hist = AuditHistory(tmp_path)

        for _ in range(15):
            hist.save_audit(
                issues=[],
                score=self._make_mock_score(),
                files_scanned=1,
                services_scanned=1,
            )
            time.sleep(0.05)

        assert hist.entry_count() == 15

        removed = hist.cleanup(max_entries=10)
        assert removed == 5
        assert hist.entry_count() == 10

    def test_corrupt_file_skipped(self, tmp_path):
        from composearr.history import AuditHistory

        hist = AuditHistory(tmp_path)
        hist._ensure_dir()

        # Write a corrupt JSON file
        corrupt = hist.history_dir / "audit_20260217_120000.json"
        corrupt.write_text("not valid json", encoding="utf-8")

        # Write a valid one
        hist.save_audit(
            issues=[],
            score=self._make_mock_score(),
            files_scanned=1,
            services_scanned=1,
        )

        entries = hist.get_recent()
        assert len(entries) == 1  # Corrupt file skipped

    def test_history_dir_created(self, tmp_path):
        from composearr.history import AuditHistory

        hist = AuditHistory(tmp_path)
        hist.save_audit(
            issues=[],
            score=self._make_mock_score(),
            files_scanned=1,
            services_scanned=1,
        )
        assert (tmp_path / ".composearr" / "history").is_dir()

    def test_top_rules_saved(self, tmp_path):
        from composearr.history import AuditHistory

        issues = self._make_mock_issues(5)
        # CA001 appears 3 times in the mock issues (indices 3, 4 get CA001)
        hist = AuditHistory(tmp_path)
        hist.save_audit(
            issues=issues,
            score=self._make_mock_score(),
            files_scanned=1,
            services_scanned=1,
        )
        entries = hist.get_recent()
        assert len(entries) == 1
        assert len(entries[0].top_rules) > 0


class TestSparkline:
    """Test sparkline generation."""

    def test_empty_scores(self):
        from composearr.history import make_sparkline
        assert make_sparkline([]) == ""

    def test_single_score(self):
        from composearr.history import make_sparkline
        result = make_sparkline([50])
        assert len(result) == 1

    def test_ascending_scores(self):
        from composearr.history import make_sparkline
        result = make_sparkline([10, 30, 50, 70, 90])
        assert len(result) == 5
        # First char should be lowest block, last should be highest
        assert result[0] < result[-1]

    def test_flat_scores(self):
        from composearr.history import make_sparkline
        result = make_sparkline([80, 80, 80])
        assert len(result) == 3
        # All chars should be the same
        assert len(set(result)) == 1

    def test_descending_scores(self):
        from composearr.history import make_sparkline
        result = make_sparkline([100, 80, 60, 40, 20])
        assert len(result) == 5
        assert result[0] > result[-1]


# ═══════════════════════════════════════════════════════════════
# REGISTRY CLIENT TESTS
# ═══════════════════════════════════════════════════════════════


class TestParseImage:
    """Test Docker image reference parsing."""

    def test_simple_image(self):
        from composearr.registry_client import parse_image

        info = parse_image("nginx:latest")
        assert info.registry == "docker.io"
        assert info.repo == "library/nginx"
        assert info.tag == "latest"

    def test_simple_no_tag(self):
        from composearr.registry_client import parse_image

        info = parse_image("nginx")
        assert info.registry == "docker.io"
        assert info.repo == "library/nginx"
        assert info.tag == "latest"

    def test_user_repo(self):
        from composearr.registry_client import parse_image

        info = parse_image("linuxserver/sonarr:4.0")
        assert info.registry == "docker.io"
        assert info.repo == "linuxserver/sonarr"
        assert info.tag == "4.0"

    def test_ghcr_image(self):
        from composearr.registry_client import parse_image

        info = parse_image("ghcr.io/linuxserver/sonarr:latest")
        assert info.registry == "ghcr.io"
        assert info.repo == "linuxserver/sonarr"
        assert info.tag == "latest"

    def test_lscr_image(self):
        from composearr.registry_client import parse_image

        info = parse_image("lscr.io/linuxserver/sonarr:4.0.14")
        assert info.registry == "lscr.io"
        assert info.repo == "linuxserver/sonarr"
        assert info.tag == "4.0.14"

    def test_user_repo_no_tag(self):
        from composearr.registry_client import parse_image

        info = parse_image("linuxserver/sonarr")
        assert info.tag == "latest"
        assert info.repo == "linuxserver/sonarr"

    def test_three_part_image(self):
        from composearr.registry_client import parse_image

        info = parse_image("quay.io/prometheus/node-exporter:v1.7.0")
        assert info.registry == "quay.io"
        assert info.repo == "prometheus/node-exporter"
        assert info.tag == "v1.7.0"

    def test_localhost_registry(self):
        from composearr.registry_client import parse_image

        info = parse_image("localhost:5000/myapp:v1")
        assert info.registry == "localhost:5000"
        assert info.repo == "myapp"
        assert info.tag == "v1"


class TestSemverParsing:
    """Test semver tag parsing."""

    def test_full_semver(self):
        from composearr.registry_client import _parse_semver

        assert _parse_semver("1.2.3") == (1, 2, 3)

    def test_v_prefix(self):
        from composearr.registry_client import _parse_semver

        assert _parse_semver("v4.0.14") == (4, 0, 14)

    def test_major_minor(self):
        from composearr.registry_client import _parse_semver

        assert _parse_semver("4.0") == (4, 0, 0)

    def test_major_only(self):
        from composearr.registry_client import _parse_semver

        assert _parse_semver("4") == (4, 0, 0)

    def test_not_semver(self):
        from composearr.registry_client import _parse_semver

        assert _parse_semver("latest") is None
        assert _parse_semver("develop") is None
        assert _parse_semver("abc123") is None


class TestUnstableDetection:
    """Test unstable tag detection."""

    def test_latest_is_unstable(self):
        from composearr.registry_client import _is_unstable

        assert _is_unstable("latest") is True

    def test_dev_is_unstable(self):
        from composearr.registry_client import _is_unstable

        assert _is_unstable("dev") is True
        assert _is_unstable("develop") is True
        assert _is_unstable("nightly") is True

    def test_beta_alpha_rc(self):
        from composearr.registry_client import _is_unstable

        assert _is_unstable("1.0-beta") is True
        assert _is_unstable("1.0-alpha") is True
        assert _is_unstable("1.0-rc1") is True

    def test_stable_tags(self):
        from composearr.registry_client import _is_unstable

        assert _is_unstable("4.0.14") is False
        assert _is_unstable("v1.2.3") is False
        assert _is_unstable("1.25-bookworm") is False

    def test_commit_hash(self):
        from composearr.registry_client import _is_unstable

        assert _is_unstable("a1b2c3d") is True
        assert _is_unstable("abc123def456") is True


class TestLatestStable:
    """Test latest stable tag detection."""

    def test_semver_sorted(self):
        from composearr.registry_client import ImageTag, RegistryClient

        client = RegistryClient()
        tags = [
            ImageTag(name="1.0.0"),
            ImageTag(name="2.0.0"),
            ImageTag(name="1.5.0"),
            ImageTag(name="latest"),
        ]
        result = client.get_latest_stable(tags)
        assert result is not None
        assert result.name == "2.0.0"

    def test_with_v_prefix(self):
        from composearr.registry_client import ImageTag, RegistryClient

        client = RegistryClient()
        tags = [
            ImageTag(name="v1.0.0"),
            ImageTag(name="v2.1.0"),
            ImageTag(name="v1.5.0"),
        ]
        result = client.get_latest_stable(tags)
        assert result is not None
        assert result.name == "v2.1.0"

    def test_all_unstable_returns_none(self):
        from composearr.registry_client import ImageTag, RegistryClient

        client = RegistryClient()
        tags = [
            ImageTag(name="latest"),
            ImageTag(name="dev"),
            ImageTag(name="nightly"),
        ]
        result = client.get_latest_stable(tags)
        assert result is None

    def test_empty_tags(self):
        from composearr.registry_client import ImageTag, RegistryClient

        client = RegistryClient()
        result = client.get_latest_stable([])
        assert result is None

    def test_fallback_to_created_date(self):
        from composearr.registry_client import ImageTag, RegistryClient

        client = RegistryClient()
        tags = [
            ImageTag(name="bookworm", created=datetime(2025, 1, 1, tzinfo=timezone.utc)),
            ImageTag(name="bullseye", created=datetime(2025, 6, 1, tzinfo=timezone.utc)),
            ImageTag(name="latest"),
        ]
        result = client.get_latest_stable(tags)
        assert result is not None
        assert result.name == "bullseye"  # Most recent


class TestFreshnessResult:
    """Test FreshnessResult dataclass."""

    def test_create_result(self):
        from composearr.registry_client import FreshnessResult

        fr = FreshnessResult(
            service="sonarr",
            image="lscr.io/linuxserver/sonarr:4.0",
            current_tag="4.0",
            latest_stable="4.0.14",
            available_tags=25,
            up_to_date=False,
        )
        assert fr.service == "sonarr"
        assert fr.up_to_date is False
        assert fr.error is None


class TestCheckFreshness:
    """Test check_freshness with mocked network."""

    def test_freshness_check_no_network(self):
        """With no requests library, returns empty results."""
        from composearr.registry_client import RegistryClient

        client = RegistryClient()

        # Mock get_tags to return empty (as if no network)
        client.get_tags = MagicMock(return_value=[])

        services = {
            "sonarr": {"image": "lscr.io/linuxserver/sonarr:4.0"},
        }
        results = client.check_freshness(services)
        assert len(results) == 1
        assert results[0].service == "sonarr"
        assert results[0].error is not None  # "No tags found..."

    def test_freshness_up_to_date(self):
        from composearr.registry_client import ImageTag, RegistryClient

        client = RegistryClient()
        client.get_tags = MagicMock(return_value=[
            ImageTag(name="4.0.14"),
            ImageTag(name="4.0.13"),
            ImageTag(name="latest"),
        ])

        services = {
            "sonarr": {"image": "lscr.io/linuxserver/sonarr:4.0.14"},
        }
        results = client.check_freshness(services)
        assert len(results) == 1
        assert results[0].up_to_date is True

    def test_freshness_update_available(self):
        from composearr.registry_client import ImageTag, RegistryClient

        client = RegistryClient()
        client.get_tags = MagicMock(return_value=[
            ImageTag(name="4.0.14"),
            ImageTag(name="4.0.10"),
            ImageTag(name="latest"),
        ])

        services = {
            "sonarr": {"image": "lscr.io/linuxserver/sonarr:4.0.10"},
        }
        results = client.check_freshness(services)
        assert len(results) == 1
        assert results[0].up_to_date is False
        assert results[0].latest_stable == "4.0.14"

    def test_freshness_skips_no_image(self):
        from composearr.registry_client import RegistryClient

        client = RegistryClient()

        services = {
            "myapp": {"build": "."},  # No image
        }
        results = client.check_freshness(services)
        assert len(results) == 0

    def test_freshness_multiple_services(self):
        from composearr.registry_client import ImageTag, RegistryClient

        client = RegistryClient()

        def mock_tags(image):
            if "sonarr" in image:
                return [ImageTag(name="4.0.14"), ImageTag(name="latest")]
            elif "radarr" in image:
                return [ImageTag(name="5.0.0"), ImageTag(name="latest")]
            return []

        client.get_tags = MagicMock(side_effect=mock_tags)

        services = {
            "sonarr": {"image": "lscr.io/linuxserver/sonarr:4.0.14"},
            "radarr": {"image": "lscr.io/linuxserver/radarr:4.0.0"},
        }
        results = client.check_freshness(services)
        assert len(results) == 2

    def test_freshness_latest_tag_user(self):
        """User running :latest should show as 'up to date' (can't compare)."""
        from composearr.registry_client import ImageTag, RegistryClient

        client = RegistryClient()
        client.get_tags = MagicMock(return_value=[
            ImageTag(name="4.0.14"),
            ImageTag(name="latest"),
        ])

        services = {
            "sonarr": {"image": "lscr.io/linuxserver/sonarr:latest"},
        }
        results = client.check_freshness(services)
        assert len(results) == 1
        assert results[0].up_to_date is True  # Can't meaningfully compare :latest


# ═══════════════════════════════════════════════════════════════
# INTEGRATION TESTS
# ═══════════════════════════════════════════════════════════════


class TestHistoryIntegration:
    """Test history saving integration with audit pipeline."""

    def test_save_with_real_score(self, tmp_path):
        """Test saving with actual StackScore objects."""
        from composearr.history import AuditHistory
        from composearr.models import LintIssue, Severity
        from composearr.scoring import calculate_stack_score

        issues = [
            LintIssue(
                rule_id="CA001",
                rule_name="no-latest-tag",
                severity=Severity.WARNING,
                message="Using :latest tag",
                file_path=str(tmp_path / "compose.yaml"),
                fix_available=True,
                suggested_fix="Pin to nginx:1.25",
            ),
            LintIssue(
                rule_id="CA201",
                rule_name="require-healthcheck",
                severity=Severity.WARNING,
                message="No healthcheck defined",
                file_path=str(tmp_path / "compose.yaml"),
            ),
        ]

        score = calculate_stack_score(issues, total_services=3)

        hist = AuditHistory(tmp_path)
        filepath = hist.save_audit(
            issues=issues,
            score=score,
            files_scanned=1,
            services_scanned=3,
            duration_seconds=0.5,
        )

        assert filepath.exists()

        entries = hist.get_recent()
        assert len(entries) == 1
        assert entries[0].total_issues == 2
        assert entries[0].fixable_issues == 1
        assert entries[0].errors == 0
        assert entries[0].warnings == 2

    def test_history_json_roundtrip(self, tmp_path):
        """Verify JSON serialization roundtrip preserves all fields."""
        from composearr.history import AuditHistory
        from composearr.scoring import StackScore, ScoreBreakdown

        score = StackScore(
            overall=85,
            grade="B",
            breakdown=ScoreBreakdown(security=90, reliability=80, consistency=85, network=75),
            error_count=1,
            warning_count=3,
            info_count=2,
            total_services=8,
        )

        hist = AuditHistory(tmp_path)
        filepath = hist.save_audit(
            issues=[],
            score=score,
            files_scanned=5,
            services_scanned=8,
            duration_seconds=2.1,
        )

        # Read raw JSON
        with open(filepath, encoding="utf-8") as f:
            data = json.load(f)

        assert data["score"] == 85
        assert data["grade"] == "B"
        assert data["security_score"] == 90
        assert data["reliability_score"] == 80
        assert data["files_scanned"] == 5
        assert data["duration_seconds"] == 2.1

    def test_trend_after_multiple_audits(self, tmp_path):
        """Test trend calculation with real score progression."""
        from composearr.history import AuditHistory
        from composearr.models import LintIssue, Severity
        from composearr.scoring import calculate_stack_score

        hist = AuditHistory(tmp_path)

        # First audit: many issues
        issues_1 = [
            LintIssue(
                rule_id="CA001", rule_name="no-latest-tag",
                severity=Severity.WARNING, message="bad",
                file_path="f.yaml",
            )
            for _ in range(8)
        ]
        score_1 = calculate_stack_score(issues_1, total_services=4)
        hist.save_audit(issues_1, score_1, 2, 4, 1.0)
        time.sleep(0.1)

        # Second audit: fewer issues (improvement)
        issues_2 = [
            LintIssue(
                rule_id="CA001", rule_name="no-latest-tag",
                severity=Severity.WARNING, message="bad",
                file_path="f.yaml",
            )
            for _ in range(2)
        ]
        score_2 = calculate_stack_score(issues_2, total_services=4)
        hist.save_audit(issues_2, score_2, 2, 4, 0.8)

        trend = hist.get_trend()
        assert trend is not None
        assert trend.improved is True
        assert trend.current_issues < trend.previous_issues


class TestRegistryClientMocked:
    """Test RegistryClient with mocked HTTP responses."""

    @patch("composearr.registry_client._HAS_REQUESTS", False)
    def test_no_requests_library(self):
        from composearr.registry_client import RegistryClient

        client = RegistryClient()
        result = client.get_tags("nginx:latest")
        assert result == []

    def test_dockerhub_tags_mocked(self):
        from composearr.registry_client import RegistryClient

        client = RegistryClient()

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "results": [
                {
                    "name": "1.25",
                    "digest": "sha256:abc",
                    "last_updated": "2025-06-01T12:00:00Z",
                    "full_size": 12345678,
                },
                {
                    "name": "latest",
                    "digest": "sha256:def",
                    "last_updated": "2025-06-01T12:00:00Z",
                },
            ]
        }
        mock_response.raise_for_status = MagicMock()

        mock_session = MagicMock()
        mock_session.get.return_value = mock_response
        client._session = mock_session

        tags = client._get_dockerhub_tags("library/nginx")
        assert len(tags) == 2
        assert tags[0].name == "1.25"
        assert tags[0].size_bytes == 12345678
        assert tags[1].name == "latest"

    def test_ghcr_tags_mocked(self):
        from composearr.registry_client import RegistryClient

        client = RegistryClient()

        # Two calls: token then tags
        token_response = MagicMock()
        token_response.status_code = 200
        token_response.json.return_value = {"token": "test-token"}
        token_response.raise_for_status = MagicMock()

        tags_response = MagicMock()
        tags_response.status_code = 200
        tags_response.json.return_value = {"tags": ["v1.0", "v1.1", "latest"]}
        tags_response.raise_for_status = MagicMock()

        mock_session = MagicMock()
        mock_session.get.side_effect = [token_response, tags_response]
        client._session = mock_session

        tags = client._get_ghcr_tags("linuxserver/sonarr")
        assert len(tags) == 3
        assert tags[0].name == "v1.0"

    def test_network_error_returns_empty(self):
        from composearr.registry_client import RegistryClient

        client = RegistryClient()

        mock_session = MagicMock()
        mock_session.get.side_effect = Exception("Network error")
        mock_session.headers = {}
        client._session = mock_session

        tags = client.get_tags("nginx:latest")
        assert tags == []
