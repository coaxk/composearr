"""Comprehensive tests for ComposeArr Sprint 1 features.

Covers:
  CA501 (missing-memory-limit)
  CA502 (missing-cpu-limit)
  CA503 (resource-limits-unusual)
  CA504 (no-logging-config)
  CA505 (no-log-rotation)
  CA404 (duplicate-env-vars)
  Stack Health Score (scoring.py)
  Fixer functions
"""

from __future__ import annotations

from pathlib import Path

import pytest

from composearr.models import ComposeFile, LintIssue, Severity
from composearr.rules.base import get_rule
from composearr.rules.CA5xx_resources import (
    MissingMemoryLimit,
    MissingCpuLimit,
    NoLoggingConfig,
    NoLogRotation,
    ResourceLimitsUnusual,
    _parse_memory,
    _parse_cpus,
)
from composearr.rules.CA4xx_consistency import DuplicateEnvVars
from composearr.scoring import (
    ScoreBreakdown,
    StackScore,
    calculate_stack_score,
    score_to_grade,
    _categorize,
)
from composearr.fixer import (
    _fix_memory_limit,
    _fix_cpu_limit,
    _fix_logging_config,
    _fix_log_rotation,
    _fix_duplicate_env,
)


# ── Helpers ──────────────────────────────────────────────────


def _cf(tmp_path: Path, yaml_content: str, data: dict) -> ComposeFile:
    """Create a ComposeFile from raw YAML text and a pre-parsed data dict."""
    p = tmp_path / "compose.yaml"
    p.write_text(yaml_content, encoding="utf-8")
    return ComposeFile(path=p, raw_content=yaml_content, data=data)


def _make_issue(
    rule_id: str,
    severity: Severity = Severity.WARNING,
    service: str = "app",
) -> LintIssue:
    return LintIssue(
        rule_id=rule_id,
        rule_name=f"test-{rule_id}",
        severity=severity,
        message=f"Test issue {rule_id}",
        file_path="test.yaml",
        service=service,
    )


# ══════════════════════════════════════════════════════════════
# CA501: Missing Memory Limit
# ══════════════════════════════════════════════════════════════


class TestCA501:
    def test_flags_missing_memory_limit(self, tmp_path: Path):
        yaml_content = "services:\n  app:\n    image: nginx\n"
        cf = _cf(tmp_path, yaml_content, {"services": {"app": {"image": "nginx"}}})
        rule = MissingMemoryLimit()
        issues = rule.check_service("app", {"image": "nginx"}, cf)
        assert len(issues) == 1
        assert issues[0].rule_id == "CA501"
        assert issues[0].severity == Severity.WARNING

    def test_passes_with_memory_limit(self, tmp_path: Path):
        svc = {
            "image": "nginx",
            "deploy": {"resources": {"limits": {"memory": "512M"}}},
        }
        yaml_content = "services:\n  app:\n    image: nginx\n    deploy:\n      resources:\n        limits:\n          memory: 512M\n"
        cf = _cf(tmp_path, yaml_content, {"services": {"app": svc}})
        rule = MissingMemoryLimit()
        issues = rule.check_service("app", svc, cf)
        assert len(issues) == 0

    def test_suggested_fix_references_known_app(self, tmp_path: Path):
        yaml_content = "services:\n  sonarr:\n    image: linuxserver/sonarr:latest\n"
        svc = {"image": "linuxserver/sonarr:latest"}
        cf = _cf(tmp_path, yaml_content, {"services": {"sonarr": svc}})
        rule = MissingMemoryLimit()
        issues = rule.check_service("sonarr", svc, cf)
        assert len(issues) == 1
        assert "512M" in issues[0].suggested_fix
        assert "Sonarr" in issues[0].suggested_fix

    def test_suggested_fix_defaults_for_unknown_app(self, tmp_path: Path):
        yaml_content = "services:\n  custom:\n    image: mycustom/thing:v1\n"
        svc = {"image": "mycustom/thing:v1"}
        cf = _cf(tmp_path, yaml_content, {"services": {"custom": svc}})
        rule = MissingMemoryLimit()
        issues = rule.check_service("custom", svc, cf)
        assert len(issues) == 1
        assert "256M" in issues[0].suggested_fix

    def test_fix_available_flag_set(self, tmp_path: Path):
        yaml_content = "services:\n  app:\n    image: nginx\n"
        cf = _cf(tmp_path, yaml_content, {"services": {"app": {"image": "nginx"}}})
        rule = MissingMemoryLimit()
        issues = rule.check_service("app", {"image": "nginx"}, cf)
        assert issues[0].fix_available is True

    def test_empty_deploy_still_flagged(self, tmp_path: Path):
        svc = {"image": "nginx", "deploy": {}}
        yaml_content = "services:\n  app:\n    image: nginx\n    deploy: {}\n"
        cf = _cf(tmp_path, yaml_content, {"services": {"app": svc}})
        rule = MissingMemoryLimit()
        issues = rule.check_service("app", svc, cf)
        assert len(issues) == 1


# ══════════════════════════════════════════════════════════════
# CA502: Missing CPU Limit
# ══════════════════════════════════════════════════════════════


class TestCA502:
    def test_flags_missing_cpu_limit(self, tmp_path: Path):
        yaml_content = "services:\n  app:\n    image: nginx\n"
        cf = _cf(tmp_path, yaml_content, {"services": {"app": {"image": "nginx"}}})
        rule = MissingCpuLimit()
        issues = rule.check_service("app", {"image": "nginx"}, cf)
        assert len(issues) == 1
        assert issues[0].rule_id == "CA502"

    def test_passes_with_cpu_limit(self, tmp_path: Path):
        svc = {
            "image": "nginx",
            "deploy": {"resources": {"limits": {"cpus": "0.5"}}},
        }
        yaml_content = "services:\n  app:\n    image: nginx\n    deploy:\n      resources:\n        limits:\n          cpus: '0.5'\n"
        cf = _cf(tmp_path, yaml_content, {"services": {"app": svc}})
        rule = MissingCpuLimit()
        issues = rule.check_service("app", svc, cf)
        assert len(issues) == 0

    def test_suggested_fix_references_known_app(self, tmp_path: Path):
        yaml_content = "services:\n  plex:\n    image: plexinc/pms-docker:latest\n"
        svc = {"image": "plexinc/pms-docker:latest"}
        cf = _cf(tmp_path, yaml_content, {"services": {"plex": svc}})
        rule = MissingCpuLimit()
        issues = rule.check_service("plex", svc, cf)
        assert len(issues) == 1
        assert "2.0" in issues[0].suggested_fix
        assert "Plex" in issues[0].suggested_fix

    def test_suggested_fix_defaults_for_unknown_app(self, tmp_path: Path):
        yaml_content = "services:\n  custom:\n    image: unknown/app:v1\n"
        svc = {"image": "unknown/app:v1"}
        cf = _cf(tmp_path, yaml_content, {"services": {"custom": svc}})
        rule = MissingCpuLimit()
        issues = rule.check_service("custom", svc, cf)
        assert len(issues) == 1
        assert "0.5" in issues[0].suggested_fix

    def test_fix_available_flag_set(self, tmp_path: Path):
        yaml_content = "services:\n  app:\n    image: nginx\n"
        cf = _cf(tmp_path, yaml_content, {"services": {"app": {"image": "nginx"}}})
        rule = MissingCpuLimit()
        issues = rule.check_service("app", {"image": "nginx"}, cf)
        assert issues[0].fix_available is True

    def test_empty_limits_still_flagged(self, tmp_path: Path):
        svc = {"image": "nginx", "deploy": {"resources": {"limits": {}}}}
        yaml_content = "services:\n  app:\n    image: nginx\n"
        cf = _cf(tmp_path, yaml_content, {"services": {"app": svc}})
        rule = MissingCpuLimit()
        issues = rule.check_service("app", svc, cf)
        assert len(issues) == 1


# ══════════════════════════════════════════════════════════════
# CA503: Resource Limits Unusual
# ══════════════════════════════════════════════════════════════


class TestCA503:
    def test_flags_memory_too_high(self, tmp_path: Path):
        """Memory >4x typical should be flagged."""
        svc = {
            "image": "linuxserver/sonarr:latest",
            "deploy": {"resources": {"limits": {"memory": "4G"}}},
        }
        yaml_content = "services:\n  sonarr:\n    image: linuxserver/sonarr:latest\n"
        cf = _cf(tmp_path, yaml_content, {"services": {"sonarr": svc}})
        rule = ResourceLimitsUnusual()
        issues = rule.check_service("sonarr", svc, cf)
        assert len(issues) == 1
        assert "higher than typical" in issues[0].message
        assert issues[0].severity == Severity.INFO

    def test_flags_memory_too_low(self, tmp_path: Path):
        """Memory <0.25x typical should be flagged."""
        svc = {
            "image": "linuxserver/sonarr:latest",
            "deploy": {"resources": {"limits": {"memory": "64M"}}},
        }
        yaml_content = "services:\n  sonarr:\n    image: linuxserver/sonarr:latest\n"
        cf = _cf(tmp_path, yaml_content, {"services": {"sonarr": svc}})
        rule = ResourceLimitsUnusual()
        issues = rule.check_service("sonarr", svc, cf)
        assert len(issues) == 1
        assert "very low" in issues[0].message

    def test_passes_memory_in_range(self, tmp_path: Path):
        """Memory within 0.25x-4x typical should pass."""
        svc = {
            "image": "linuxserver/sonarr:latest",
            "deploy": {"resources": {"limits": {"memory": "512M"}}},
        }
        yaml_content = "services:\n  sonarr:\n    image: linuxserver/sonarr:latest\n"
        cf = _cf(tmp_path, yaml_content, {"services": {"sonarr": svc}})
        rule = ResourceLimitsUnusual()
        issues = rule.check_service("sonarr", svc, cf)
        assert len(issues) == 0

    def test_passes_for_unknown_app(self, tmp_path: Path):
        """Unknown images should not be flagged (no profile to compare)."""
        svc = {
            "image": "mycustom/thing:v1",
            "deploy": {"resources": {"limits": {"memory": "8G"}}},
        }
        yaml_content = "services:\n  custom:\n    image: mycustom/thing:v1\n"
        cf = _cf(tmp_path, yaml_content, {"services": {"custom": svc}})
        rule = ResourceLimitsUnusual()
        issues = rule.check_service("custom", svc, cf)
        assert len(issues) == 0

    def test_flags_cpu_too_high(self, tmp_path: Path):
        """CPU >4x typical should be flagged."""
        svc = {
            "image": "linuxserver/sonarr:latest",
            "deploy": {"resources": {"limits": {"cpus": "4.0"}}},
        }
        yaml_content = "services:\n  sonarr:\n    image: linuxserver/sonarr:latest\n"
        cf = _cf(tmp_path, yaml_content, {"services": {"sonarr": svc}})
        rule = ResourceLimitsUnusual()
        issues = rule.check_service("sonarr", svc, cf)
        # Sonarr typical_cpu is 0.5; 4.0/0.5 = 8x > 4x
        assert len(issues) == 1
        assert "CPU" in issues[0].message

    def test_passes_no_limits(self, tmp_path: Path):
        """Services without limits should not be flagged (CA501/CA502 handle that)."""
        svc = {"image": "linuxserver/sonarr:latest"}
        yaml_content = "services:\n  sonarr:\n    image: linuxserver/sonarr:latest\n"
        cf = _cf(tmp_path, yaml_content, {"services": {"sonarr": svc}})
        rule = ResourceLimitsUnusual()
        issues = rule.check_service("sonarr", svc, cf)
        assert len(issues) == 0

    def test_both_memory_and_cpu_flagged(self, tmp_path: Path):
        """Both memory and CPU unusual should produce two issues."""
        svc = {
            "image": "linuxserver/sonarr:latest",
            "deploy": {"resources": {"limits": {"memory": "4G", "cpus": "4.0"}}},
        }
        yaml_content = "services:\n  sonarr:\n    image: linuxserver/sonarr:latest\n"
        cf = _cf(tmp_path, yaml_content, {"services": {"sonarr": svc}})
        rule = ResourceLimitsUnusual()
        issues = rule.check_service("sonarr", svc, cf)
        assert len(issues) == 2


# ══════════════════════════════════════════════════════════════
# CA504: No Logging Config
# ══════════════════════════════════════════════════════════════


class TestCA504:
    def test_flags_missing_logging(self, tmp_path: Path):
        yaml_content = "services:\n  app:\n    image: nginx\n"
        cf = _cf(tmp_path, yaml_content, {"services": {"app": {"image": "nginx"}}})
        rule = NoLoggingConfig()
        issues = rule.check_service("app", {"image": "nginx"}, cf)
        assert len(issues) == 1
        assert issues[0].rule_id == "CA504"
        assert issues[0].severity == Severity.WARNING

    def test_passes_with_logging(self, tmp_path: Path):
        svc = {
            "image": "nginx",
            "logging": {"driver": "json-file", "options": {"max-size": "10m"}},
        }
        yaml_content = "services:\n  app:\n    image: nginx\n    logging:\n      driver: json-file\n"
        cf = _cf(tmp_path, yaml_content, {"services": {"app": svc}})
        rule = NoLoggingConfig()
        issues = rule.check_service("app", svc, cf)
        assert len(issues) == 0

    def test_fix_available_flag_set(self, tmp_path: Path):
        yaml_content = "services:\n  app:\n    image: nginx\n"
        cf = _cf(tmp_path, yaml_content, {"services": {"app": {"image": "nginx"}}})
        rule = NoLoggingConfig()
        issues = rule.check_service("app", {"image": "nginx"}, cf)
        assert issues[0].fix_available is True
        assert "max-size" in issues[0].suggested_fix

    def test_passes_with_syslog_driver(self, tmp_path: Path):
        svc = {"image": "nginx", "logging": {"driver": "syslog"}}
        yaml_content = "services:\n  app:\n    image: nginx\n    logging:\n      driver: syslog\n"
        cf = _cf(tmp_path, yaml_content, {"services": {"app": svc}})
        rule = NoLoggingConfig()
        issues = rule.check_service("app", svc, cf)
        assert len(issues) == 0


# ══════════════════════════════════════════════════════════════
# CA505: No Log Rotation
# ══════════════════════════════════════════════════════════════


class TestCA505:
    def test_flags_json_file_without_rotation(self, tmp_path: Path):
        svc = {"image": "nginx", "logging": {"driver": "json-file"}}
        yaml_content = "services:\n  app:\n    image: nginx\n    logging:\n      driver: json-file\n"
        cf = _cf(tmp_path, yaml_content, {"services": {"app": svc}})
        rule = NoLogRotation()
        issues = rule.check_service("app", svc, cf)
        assert len(issues) == 1
        assert issues[0].rule_id == "CA505"
        assert "max-size" in issues[0].message
        assert "max-file" in issues[0].message

    def test_flags_missing_max_file_only(self, tmp_path: Path):
        svc = {
            "image": "nginx",
            "logging": {"driver": "json-file", "options": {"max-size": "10m"}},
        }
        yaml_content = "services:\n  app:\n    image: nginx\n"
        cf = _cf(tmp_path, yaml_content, {"services": {"app": svc}})
        rule = NoLogRotation()
        issues = rule.check_service("app", svc, cf)
        assert len(issues) == 1
        assert "max-file" in issues[0].message
        assert "max-size" not in issues[0].message

    def test_flags_missing_max_size_only(self, tmp_path: Path):
        svc = {
            "image": "nginx",
            "logging": {"driver": "json-file", "options": {"max-file": "3"}},
        }
        yaml_content = "services:\n  app:\n    image: nginx\n"
        cf = _cf(tmp_path, yaml_content, {"services": {"app": svc}})
        rule = NoLogRotation()
        issues = rule.check_service("app", svc, cf)
        assert len(issues) == 1
        assert "max-size" in issues[0].message
        assert "max-file" not in issues[0].message

    def test_syslog_not_flagged(self, tmp_path: Path):
        svc = {"image": "nginx", "logging": {"driver": "syslog"}}
        yaml_content = "services:\n  app:\n    image: nginx\n    logging:\n      driver: syslog\n"
        cf = _cf(tmp_path, yaml_content, {"services": {"app": svc}})
        rule = NoLogRotation()
        issues = rule.check_service("app", svc, cf)
        assert len(issues) == 0

    def test_fluentd_not_flagged(self, tmp_path: Path):
        svc = {"image": "nginx", "logging": {"driver": "fluentd"}}
        yaml_content = "services:\n  app:\n    image: nginx\n"
        cf = _cf(tmp_path, yaml_content, {"services": {"app": svc}})
        rule = NoLogRotation()
        issues = rule.check_service("app", svc, cf)
        assert len(issues) == 0

    def test_fully_configured_logging_passes(self, tmp_path: Path):
        svc = {
            "image": "nginx",
            "logging": {
                "driver": "json-file",
                "options": {"max-size": "10m", "max-file": "3"},
            },
        }
        yaml_content = "services:\n  app:\n    image: nginx\n"
        cf = _cf(tmp_path, yaml_content, {"services": {"app": svc}})
        rule = NoLogRotation()
        issues = rule.check_service("app", svc, cf)
        assert len(issues) == 0

    def test_no_logging_at_all_not_flagged(self, tmp_path: Path):
        """CA504 handles missing logging; CA505 should not fire."""
        svc = {"image": "nginx"}
        yaml_content = "services:\n  app:\n    image: nginx\n"
        cf = _cf(tmp_path, yaml_content, {"services": {"app": svc}})
        rule = NoLogRotation()
        issues = rule.check_service("app", svc, cf)
        assert len(issues) == 0

    def test_local_driver_without_rotation_flagged(self, tmp_path: Path):
        svc = {"image": "nginx", "logging": {"driver": "local"}}
        yaml_content = "services:\n  app:\n    image: nginx\n"
        cf = _cf(tmp_path, yaml_content, {"services": {"app": svc}})
        rule = NoLogRotation()
        issues = rule.check_service("app", svc, cf)
        assert len(issues) == 1

    def test_fix_available_flag_set(self, tmp_path: Path):
        svc = {"image": "nginx", "logging": {"driver": "json-file"}}
        yaml_content = "services:\n  app:\n    image: nginx\n"
        cf = _cf(tmp_path, yaml_content, {"services": {"app": svc}})
        rule = NoLogRotation()
        issues = rule.check_service("app", svc, cf)
        assert issues[0].fix_available is True


# ══════════════════════════════════════════════════════════════
# CA404: Duplicate Env Vars
# ══════════════════════════════════════════════════════════════


class TestCA404:
    def test_flags_duplicate_in_list_format(self, tmp_path: Path):
        svc = {
            "image": "nginx",
            "environment": ["FOO=bar", "FOO=baz"],
        }
        yaml_content = "services:\n  app:\n    image: nginx\n    environment:\n      - FOO=bar\n      - FOO=baz\n"
        cf = _cf(tmp_path, yaml_content, {"services": {"app": svc}})
        rule = DuplicateEnvVars()
        issues = rule.check_service("app", svc, cf)
        assert len(issues) == 1
        assert issues[0].rule_id == "CA404"
        assert issues[0].severity == Severity.ERROR
        assert "FOO" in issues[0].message
        assert "baz" in issues[0].message  # last value wins

    def test_dict_format_never_triggers(self, tmp_path: Path):
        svc = {
            "image": "nginx",
            "environment": {"FOO": "bar"},
        }
        yaml_content = "services:\n  app:\n    image: nginx\n    environment:\n      FOO: bar\n"
        cf = _cf(tmp_path, yaml_content, {"services": {"app": svc}})
        rule = DuplicateEnvVars()
        issues = rule.check_service("app", svc, cf)
        assert len(issues) == 0

    def test_single_occurrence_no_issue(self, tmp_path: Path):
        svc = {
            "image": "nginx",
            "environment": ["FOO=bar", "BAZ=qux"],
        }
        yaml_content = "services:\n  app:\n    image: nginx\n    environment:\n      - FOO=bar\n      - BAZ=qux\n"
        cf = _cf(tmp_path, yaml_content, {"services": {"app": svc}})
        rule = DuplicateEnvVars()
        issues = rule.check_service("app", svc, cf)
        assert len(issues) == 0

    def test_multiple_duplicates_multiple_issues(self, tmp_path: Path):
        svc = {
            "image": "nginx",
            "environment": ["A=1", "A=2", "B=x", "B=y"],
        }
        yaml_content = "services:\n  app:\n    image: nginx\n"
        cf = _cf(tmp_path, yaml_content, {"services": {"app": svc}})
        rule = DuplicateEnvVars()
        issues = rule.check_service("app", svc, cf)
        assert len(issues) == 2

    def test_no_environment_no_issue(self, tmp_path: Path):
        svc = {"image": "nginx"}
        yaml_content = "services:\n  app:\n    image: nginx\n"
        cf = _cf(tmp_path, yaml_content, {"services": {"app": svc}})
        rule = DuplicateEnvVars()
        issues = rule.check_service("app", svc, cf)
        assert len(issues) == 0

    def test_fix_available_flag_set(self, tmp_path: Path):
        svc = {"image": "nginx", "environment": ["TZ=UTC", "TZ=US/Eastern"]}
        yaml_content = "services:\n  app:\n    image: nginx\n"
        cf = _cf(tmp_path, yaml_content, {"services": {"app": svc}})
        rule = DuplicateEnvVars()
        issues = rule.check_service("app", svc, cf)
        assert len(issues) == 1
        assert issues[0].fix_available is True
        assert "TZ" in issues[0].suggested_fix


# ══════════════════════════════════════════════════════════════
# Stack Health Score
# ══════════════════════════════════════════════════════════════


class TestScoreToGrade:
    def test_a_plus(self):
        assert score_to_grade(100) == "A+"
        assert score_to_grade(97) == "A+"

    def test_a(self):
        assert score_to_grade(96) == "A"
        assert score_to_grade(93) == "A"

    def test_a_minus(self):
        assert score_to_grade(92) == "A-"
        assert score_to_grade(90) == "A-"

    def test_b_plus(self):
        assert score_to_grade(89) == "B+"
        assert score_to_grade(87) == "B+"

    def test_b(self):
        assert score_to_grade(86) == "B"
        assert score_to_grade(83) == "B"

    def test_b_minus(self):
        assert score_to_grade(82) == "B-"
        assert score_to_grade(80) == "B-"

    def test_c_plus(self):
        assert score_to_grade(79) == "C+"
        assert score_to_grade(77) == "C+"

    def test_c(self):
        assert score_to_grade(76) == "C"
        assert score_to_grade(73) == "C"

    def test_c_minus(self):
        assert score_to_grade(72) == "C-"
        assert score_to_grade(70) == "C-"

    def test_d_plus(self):
        assert score_to_grade(69) == "D+"
        assert score_to_grade(67) == "D+"

    def test_d(self):
        assert score_to_grade(66) == "D"
        assert score_to_grade(63) == "D"

    def test_d_minus(self):
        assert score_to_grade(62) == "D-"
        assert score_to_grade(60) == "D-"

    def test_f(self):
        assert score_to_grade(59) == "F"
        assert score_to_grade(0) == "F"


class TestCalculateStackScore:
    def test_no_issues_perfect_score(self):
        result = calculate_stack_score([], total_services=5)
        assert result.overall == 100
        assert result.grade == "A+"
        assert result.error_count == 0
        assert result.warning_count == 0
        assert result.info_count == 0

    def test_errors_capped_at_b(self):
        """Any unresolved errors should cap the score at B (83)."""
        issues = [_make_issue("CA101", Severity.ERROR)]
        result = calculate_stack_score(issues, total_services=5)
        assert result.overall <= 83
        assert result.grade in ("B", "B-", "C+", "C", "C-", "D+", "D", "D-", "F")

    def test_error_count_tracked(self):
        issues = [
            _make_issue("CA101", Severity.ERROR),
            _make_issue("CA101", Severity.ERROR),
        ]
        result = calculate_stack_score(issues, total_services=5)
        assert result.error_count == 2

    def test_warning_count_tracked(self):
        issues = [
            _make_issue("CA501", Severity.WARNING),
            _make_issue("CA502", Severity.WARNING),
            _make_issue("CA504", Severity.WARNING),
        ]
        result = calculate_stack_score(issues, total_services=5)
        assert result.warning_count == 3

    def test_info_count_tracked(self):
        issues = [_make_issue("CA503", Severity.INFO)]
        result = calculate_stack_score(issues, total_services=5)
        assert result.info_count == 1

    def test_category_breakdown_populated(self):
        # CA1xx -> security, CA5xx -> reliability
        issues = [
            _make_issue("CA101", Severity.ERROR),
            _make_issue("CA501", Severity.WARNING),
        ]
        result = calculate_stack_score(issues, total_services=5)
        assert result.breakdown.security < 100
        assert result.breakdown.reliability < 100
        # Network and consistency should be untouched
        assert result.breakdown.network == 100
        assert result.breakdown.consistency == 100

    def test_many_warnings_lower_score(self):
        issues = [_make_issue("CA501", Severity.WARNING) for _ in range(10)]
        result = calculate_stack_score(issues, total_services=5)
        assert result.overall < 100

    def test_zero_services_returns_100(self):
        result = calculate_stack_score([], total_services=0)
        assert result.overall == 100

    def test_total_services_stored(self):
        result = calculate_stack_score([], total_services=12)
        assert result.total_services == 12

    def test_error_hard_cap_boundary(self):
        """With one error, if raw score would be >83, it gets capped to 83."""
        # Single error with many services (diluted effect)
        issues = [_make_issue("CA101", Severity.ERROR)]
        result = calculate_stack_score(issues, total_services=50)
        assert result.overall <= 83

    def test_score_breakdown_overall_weighted(self):
        breakdown = ScoreBreakdown(
            security=100, reliability=100, consistency=100, network=100
        )
        assert breakdown.overall == 100

        breakdown2 = ScoreBreakdown(
            security=80, reliability=80, consistency=80, network=80
        )
        assert breakdown2.overall == 80

    def test_categorize_function(self):
        assert _categorize("CA001") == "security"
        assert _categorize("CA101") == "security"
        assert _categorize("CA201") == "reliability"
        assert _categorize("CA301") == "network"
        assert _categorize("CA401") == "consistency"
        assert _categorize("CA501") == "reliability"
        assert _categorize("CA601") == "consistency"


# ══════════════════════════════════════════════════════════════
# Fixer Functions
# ══════════════════════════════════════════════════════════════


class TestFixMemoryLimit:
    def test_adds_memory_limit_unknown_app(self):
        services = {"app": {"image": "myapp:v1"}}
        result = _fix_memory_limit(services, "app")
        assert result is True
        assert services["app"]["deploy"]["resources"]["limits"]["memory"] == "256M"

    def test_adds_memory_limit_known_app(self):
        services = {"sonarr": {"image": "linuxserver/sonarr:latest"}}
        result = _fix_memory_limit(services, "sonarr")
        assert result is True
        assert services["sonarr"]["deploy"]["resources"]["limits"]["memory"] == "512M"

    def test_does_not_overwrite_existing(self):
        services = {
            "app": {
                "image": "nginx",
                "deploy": {"resources": {"limits": {"memory": "1G"}}},
            }
        }
        result = _fix_memory_limit(services, "app")
        assert result is False
        assert services["app"]["deploy"]["resources"]["limits"]["memory"] == "1G"

    def test_returns_false_for_missing_service(self):
        services = {"app": {"image": "nginx"}}
        result = _fix_memory_limit(services, "nonexistent")
        assert result is False

    def test_returns_false_for_none_service(self):
        services = {"app": {"image": "nginx"}}
        result = _fix_memory_limit(services, None)
        assert result is False


class TestFixCpuLimit:
    def test_adds_cpu_limit_unknown_app(self):
        services = {"app": {"image": "myapp:v1"}}
        result = _fix_cpu_limit(services, "app")
        assert result is True
        assert services["app"]["deploy"]["resources"]["limits"]["cpus"] == "0.5"

    def test_adds_cpu_limit_known_app(self):
        services = {"plex": {"image": "plexinc/pms-docker:latest"}}
        result = _fix_cpu_limit(services, "plex")
        assert result is True
        assert services["plex"]["deploy"]["resources"]["limits"]["cpus"] == "2.0"

    def test_does_not_overwrite_existing(self):
        services = {
            "app": {
                "image": "nginx",
                "deploy": {"resources": {"limits": {"cpus": "1.0"}}},
            }
        }
        result = _fix_cpu_limit(services, "app")
        assert result is False

    def test_returns_false_for_none_service(self):
        services = {"app": {"image": "nginx"}}
        result = _fix_cpu_limit(services, None)
        assert result is False


class TestFixLoggingConfig:
    def test_adds_logging_config(self):
        services = {"app": {"image": "nginx"}}
        result = _fix_logging_config(services, "app")
        assert result is True
        logging = services["app"]["logging"]
        assert logging["driver"] == "json-file"
        assert logging["options"]["max-size"] == "10m"
        assert logging["options"]["max-file"] == "3"

    def test_does_not_overwrite_existing(self):
        services = {"app": {"image": "nginx", "logging": {"driver": "syslog"}}}
        result = _fix_logging_config(services, "app")
        assert result is False
        assert services["app"]["logging"]["driver"] == "syslog"

    def test_returns_false_for_missing_service(self):
        services = {"app": {"image": "nginx"}}
        result = _fix_logging_config(services, "nonexistent")
        assert result is False

    def test_returns_false_for_none_service(self):
        services = {"app": {"image": "nginx"}}
        result = _fix_logging_config(services, None)
        assert result is False


class TestFixLogRotation:
    def test_adds_rotation_to_bare_json_file(self):
        services = {"app": {"image": "nginx", "logging": {"driver": "json-file"}}}
        result = _fix_log_rotation(services, "app")
        assert result is True
        opts = services["app"]["logging"]["options"]
        assert opts["max-size"] == "10m"
        assert opts["max-file"] == "3"

    def test_adds_missing_max_file(self):
        services = {
            "app": {
                "image": "nginx",
                "logging": {"driver": "json-file", "options": {"max-size": "10m"}},
            }
        }
        result = _fix_log_rotation(services, "app")
        assert result is True
        assert services["app"]["logging"]["options"]["max-file"] == "3"
        assert services["app"]["logging"]["options"]["max-size"] == "10m"

    def test_adds_missing_max_size(self):
        services = {
            "app": {
                "image": "nginx",
                "logging": {"driver": "json-file", "options": {"max-file": "5"}},
            }
        }
        result = _fix_log_rotation(services, "app")
        assert result is True
        assert services["app"]["logging"]["options"]["max-size"] == "10m"
        assert services["app"]["logging"]["options"]["max-file"] == "5"

    def test_no_change_when_fully_configured(self):
        services = {
            "app": {
                "image": "nginx",
                "logging": {
                    "driver": "json-file",
                    "options": {"max-size": "10m", "max-file": "3"},
                },
            }
        }
        result = _fix_log_rotation(services, "app")
        assert result is False

    def test_returns_false_no_logging_key(self):
        services = {"app": {"image": "nginx"}}
        result = _fix_log_rotation(services, "app")
        assert result is False

    def test_returns_false_for_none_service(self):
        services = {"app": {"image": "nginx"}}
        result = _fix_log_rotation(services, None)
        assert result is False


class TestFixDuplicateEnv:
    def test_removes_duplicates_keeps_last(self):
        services = {
            "app": {
                "image": "nginx",
                "environment": ["FOO=first", "BAR=keep", "FOO=second"],
            }
        }
        result = _fix_duplicate_env(services, "app")
        assert result is True
        env = services["app"]["environment"]
        assert len(env) == 2
        # Should keep last FOO and only BAR
        env_strs = [str(e) for e in env]
        assert "FOO=second" in env_strs
        assert "BAR=keep" in env_strs
        assert "FOO=first" not in env_strs

    def test_no_duplicates_returns_false(self):
        services = {
            "app": {
                "image": "nginx",
                "environment": ["FOO=bar", "BAZ=qux"],
            }
        }
        result = _fix_duplicate_env(services, "app")
        assert result is False

    def test_dict_format_returns_false(self):
        services = {
            "app": {
                "image": "nginx",
                "environment": {"FOO": "bar"},
            }
        }
        result = _fix_duplicate_env(services, "app")
        assert result is False

    def test_returns_false_for_none_service(self):
        services = {"app": {"image": "nginx"}}
        result = _fix_duplicate_env(services, None)
        assert result is False

    def test_returns_false_for_missing_service(self):
        services = {"app": {"image": "nginx"}}
        result = _fix_duplicate_env(services, "nonexistent")
        assert result is False


# ══════════════════════════════════════════════════════════════
# Helper function unit tests
# ══════════════════════════════════════════════════════════════


class TestParseMemory:
    def test_megabytes(self):
        assert _parse_memory("512M") == 512 * 1024**2

    def test_gigabytes(self):
        assert _parse_memory("2G") == 2 * 1024**3

    def test_bare_bytes(self):
        assert _parse_memory("1024") == 1024

    def test_invalid(self):
        assert _parse_memory("notanumber") is None

    def test_empty(self):
        assert _parse_memory("") is None


class TestParseCpus:
    def test_float_string(self):
        assert _parse_cpus("0.5") == 0.5

    def test_integer(self):
        assert _parse_cpus(2) == 2.0

    def test_float(self):
        assert _parse_cpus(1.5) == 1.5

    def test_invalid(self):
        assert _parse_cpus("notanumber") is None
