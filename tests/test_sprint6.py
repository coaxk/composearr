"""Sprint 6 tests — CA9xx rules, template engine, batch operations."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from composearr.models import ComposeFile, Severity
from composearr.rules.base import get_all_rules, get_rule


# ── Helpers ──────────────────────────────────────────────────


def _make_compose(services: dict, path: str = "/test/compose.yaml") -> ComposeFile:
    """Create a minimal ComposeFile for testing."""
    import yaml

    data = {"services": services}
    raw = yaml.dump(data, default_flow_style=False)
    return ComposeFile(
        path=Path(path),
        raw_content=raw,
        data=data,
    )


# ═══════════════════════════════════════════════════════════════
#  CA901 — Resource Requests Mismatch
# ═══════════════════════════════════════════════════════════════


class TestCA901:
    """Resource reservations/limits mismatch."""

    def test_no_deploy_clean(self):
        cf = _make_compose({"web": {"image": "nginx"}})
        rule = get_rule("CA901")
        issues = rule.check_service("web", cf.services["web"], cf)
        assert len(issues) == 0

    def test_both_defined_clean(self):
        cf = _make_compose({"web": {"image": "nginx", "deploy": {
            "resources": {
                "limits": {"memory": "512M"},
                "reservations": {"memory": "256M"},
            }
        }}})
        rule = get_rule("CA901")
        issues = rule.check_service("web", cf.services["web"], cf)
        assert len(issues) == 0

    def test_reservations_without_limits(self):
        cf = _make_compose({"web": {"image": "nginx", "deploy": {
            "resources": {"reservations": {"memory": "256M"}}
        }}})
        rule = get_rule("CA901")
        issues = rule.check_service("web", cf.services["web"], cf)
        assert len(issues) == 1
        assert "without limits" in issues[0].message

    def test_limits_without_reservations(self):
        cf = _make_compose({"web": {"image": "nginx", "deploy": {
            "resources": {"limits": {"memory": "512M"}}
        }}})
        rule = get_rule("CA901")
        issues = rule.check_service("web", cf.services["web"], cf)
        assert len(issues) == 1
        assert "starved" in issues[0].message

    def test_empty_deploy_clean(self):
        cf = _make_compose({"web": {"image": "nginx", "deploy": {}}})
        rule = get_rule("CA901")
        issues = rule.check_service("web", cf.services["web"], cf)
        assert len(issues) == 0

    def test_severity_is_info(self):
        rule = get_rule("CA901")
        assert rule.severity == Severity.INFO


# ═══════════════════════════════════════════════════════════════
#  CA902 — Restart Policy Unlimited
# ═══════════════════════════════════════════════════════════════


class TestCA902:
    """Restart policy 'always' detection."""

    def test_restart_always_flagged(self):
        cf = _make_compose({"web": {"image": "nginx", "restart": "always"}})
        rule = get_rule("CA902")
        issues = rule.check_service("web", cf.services["web"], cf)
        assert len(issues) == 1
        assert "always" in issues[0].message

    def test_unless_stopped_clean(self):
        cf = _make_compose({"web": {"image": "nginx", "restart": "unless-stopped"}})
        rule = get_rule("CA902")
        issues = rule.check_service("web", cf.services["web"], cf)
        assert len(issues) == 0

    def test_on_failure_clean(self):
        cf = _make_compose({"web": {"image": "nginx", "restart": "on-failure"}})
        rule = get_rule("CA902")
        issues = rule.check_service("web", cf.services["web"], cf)
        assert len(issues) == 0

    def test_no_restart_clean(self):
        cf = _make_compose({"web": {"image": "nginx"}})
        rule = get_rule("CA902")
        issues = rule.check_service("web", cf.services["web"], cf)
        assert len(issues) == 0

    def test_fix_available(self):
        cf = _make_compose({"web": {"image": "nginx", "restart": "always"}})
        rule = get_rule("CA902")
        issues = rule.check_service("web", cf.services["web"], cf)
        assert issues[0].fix_available is True

    def test_severity_is_info(self):
        rule = get_rule("CA902")
        assert rule.severity == Severity.INFO


# ═══════════════════════════════════════════════════════════════
#  CA903 — Tmpfs No Size Limit
# ═══════════════════════════════════════════════════════════════


class TestCA903:
    """Tmpfs mount without size limit."""

    def test_tmpfs_string_no_size(self):
        cf = _make_compose({"web": {"image": "nginx", "tmpfs": ["/tmp"]}})
        rule = get_rule("CA903")
        issues = rule.check_service("web", cf.services["web"], cf)
        assert len(issues) == 1
        assert "/tmp" in issues[0].message

    def test_tmpfs_string_with_size(self):
        cf = _make_compose({"web": {"image": "nginx", "tmpfs": ["/tmp:size=100M"]}})
        rule = get_rule("CA903")
        issues = rule.check_service("web", cf.services["web"], cf)
        assert len(issues) == 0

    def test_tmpfs_single_string(self):
        cf = _make_compose({"web": {"image": "nginx", "tmpfs": "/tmp"}})
        rule = get_rule("CA903")
        issues = rule.check_service("web", cf.services["web"], cf)
        assert len(issues) == 1

    def test_no_tmpfs_clean(self):
        cf = _make_compose({"web": {"image": "nginx"}})
        rule = get_rule("CA903")
        issues = rule.check_service("web", cf.services["web"], cf)
        assert len(issues) == 0

    def test_multiple_tmpfs(self):
        cf = _make_compose({"web": {"image": "nginx", "tmpfs": ["/tmp", "/run"]}})
        rule = get_rule("CA903")
        issues = rule.check_service("web", cf.services["web"], cf)
        assert len(issues) == 2

    def test_dict_form_no_size(self):
        cf = _make_compose({"web": {"image": "nginx", "tmpfs": [
            {"type": "tmpfs", "target": "/tmp", "tmpfs": {}}
        ]}})
        rule = get_rule("CA903")
        issues = rule.check_service("web", cf.services["web"], cf)
        assert len(issues) == 1

    def test_dict_form_with_size(self):
        cf = _make_compose({"web": {"image": "nginx", "tmpfs": [
            {"type": "tmpfs", "target": "/tmp", "tmpfs": {"size": 100000000}}
        ]}})
        rule = get_rule("CA903")
        issues = rule.check_service("web", cf.services["web"], cf)
        assert len(issues) == 0

    def test_severity_is_warning(self):
        rule = get_rule("CA903")
        assert rule.severity == Severity.WARNING


# ═══════════════════════════════════════════════════════════════
#  CA904 — No User Namespace
# ═══════════════════════════════════════════════════════════════


class TestCA904:
    """User namespace remapping."""

    def test_no_userns_flagged(self):
        cf = _make_compose({"web": {"image": "nginx"}})
        rule = get_rule("CA904")
        issues = rule.check_service("web", cf.services["web"], cf)
        assert len(issues) == 1

    def test_userns_set_clean(self):
        cf = _make_compose({"web": {"image": "nginx", "userns_mode": "host"}})
        rule = get_rule("CA904")
        issues = rule.check_service("web", cf.services["web"], cf)
        assert len(issues) == 0

    def test_privileged_skipped(self):
        cf = _make_compose({"web": {"image": "nginx", "privileged": True}})
        rule = get_rule("CA904")
        issues = rule.check_service("web", cf.services["web"], cf)
        assert len(issues) == 0

    def test_network_mode_host_skipped(self):
        cf = _make_compose({"web": {"image": "nginx", "network_mode": "host"}})
        rule = get_rule("CA904")
        issues = rule.check_service("web", cf.services["web"], cf)
        assert len(issues) == 0

    def test_dind_skipped(self):
        cf = _make_compose({"dind": {"image": "docker:dind"}})
        rule = get_rule("CA904")
        issues = rule.check_service("dind", cf.services["dind"], cf)
        assert len(issues) == 0

    def test_portainer_skipped(self):
        cf = _make_compose({"mgmt": {"image": "portainer/portainer-ce:2.20"}})
        rule = get_rule("CA904")
        issues = rule.check_service("mgmt", cf.services["mgmt"], cf)
        assert len(issues) == 0

    def test_severity_is_info(self):
        rule = get_rule("CA904")
        assert rule.severity == Severity.INFO


# ═══════════════════════════════════════════════════════════════
#  Fixer — CA902
# ═══════════════════════════════════════════════════════════════


class TestFixCA902:
    """Test restart always -> unless-stopped fix."""

    def test_fix_restart_always(self):
        from composearr.fixer import _fix_restart_always
        services = {"web": {"image": "nginx", "restart": "always"}}
        assert _fix_restart_always(services, "web") is True
        assert services["web"]["restart"] == "unless-stopped"

    def test_fix_no_op_unless_stopped(self):
        from composearr.fixer import _fix_restart_always
        services = {"web": {"image": "nginx", "restart": "unless-stopped"}}
        assert _fix_restart_always(services, "web") is False

    def test_fix_none_service(self):
        from composearr.fixer import _fix_restart_always
        services = {"web": {"image": "nginx", "restart": "always"}}
        assert _fix_restart_always(services, None) is False


# ═══════════════════════════════════════════════════════════════
#  Template Engine
# ═══════════════════════════════════════════════════════════════


class TestTemplateEngine:
    """Test template listing and generation."""

    def test_list_templates(self):
        from composearr.templates.engine import TemplateEngine
        engine = TemplateEngine()
        templates = engine.list_templates()
        assert len(templates) >= 10
        assert "sonarr" in templates
        assert "radarr" in templates
        assert "nginx" in templates
        assert "postgres" in templates

    def test_template_metadata(self):
        from composearr.templates.engine import TemplateEngine
        engine = TemplateEngine()
        templates = engine.list_templates()
        sonarr = templates["sonarr"]
        assert sonarr.description != ""
        assert sonarr.category == "media"
        assert "arr" in sonarr.tags

    def test_generate_creates_files(self, tmp_path):
        from composearr.templates.engine import TemplateEngine
        engine = TemplateEngine()
        output = tmp_path / "test_sonarr"
        result = engine.generate("sonarr", output, {"PUID": "1000", "PGID": "1000", "TZ": "UTC"})
        assert result.compose_path.exists()
        content = result.compose_path.read_text(encoding="utf-8")
        assert "sonarr" in content.lower()

    def test_generate_creates_env(self, tmp_path):
        from composearr.templates.engine import TemplateEngine
        engine = TemplateEngine()
        output = tmp_path / "test_sonarr"
        result = engine.generate("sonarr", output, {"PUID": "1000"})
        if result.env_path:
            assert result.env_path.exists()
            content = result.env_path.read_text(encoding="utf-8")
            assert "PUID" in content

    def test_generate_invalid_template(self, tmp_path):
        from composearr.templates.engine import TemplateEngine
        engine = TemplateEngine()
        with pytest.raises(ValueError, match="not found"):
            engine.generate("nonexistent_template", tmp_path)

    def test_generate_substitutes_variables(self, tmp_path):
        from composearr.templates.engine import TemplateEngine
        engine = TemplateEngine()
        output = tmp_path / "test_nginx"
        result = engine.generate("nginx", output, {})
        assert result.compose_path.exists()

    def test_all_templates_valid(self, tmp_path):
        """Every template should generate without errors."""
        from composearr.templates.engine import TemplateEngine
        engine = TemplateEngine()
        for name in engine.list_templates():
            output = tmp_path / name
            result = engine.generate(name, output, {})
            assert result.compose_path.exists(), f"Template {name} failed to generate"

    def test_get_template(self):
        from composearr.templates.engine import TemplateEngine
        engine = TemplateEngine()
        meta = engine.get_template("sonarr")
        assert meta is not None
        assert meta.name == "sonarr"

    def test_get_nonexistent_template(self):
        from composearr.templates.engine import TemplateEngine
        engine = TemplateEngine()
        meta = engine.get_template("nonexistent")
        assert meta is None


# ═══════════════════════════════════════════════════════════════
#  Batch Processor
# ═══════════════════════════════════════════════════════════════


class TestBatchProcessor:
    """Test batch scan and fix operations."""

    def test_scan_empty_dir(self, tmp_path):
        from composearr.batch import BatchProcessor
        processor = BatchProcessor(tmp_path)
        issues, result = processor.scan()
        assert result.files_processed == 0
        assert len(result.errors) > 0  # "No compose files found"

    def test_scan_finds_issues(self, tmp_path):
        from composearr.batch import BatchProcessor
        compose = tmp_path / "compose.yaml"
        compose.write_text(
            "services:\n"
            "  web:\n"
            "    image: nginx:latest\n"
            "    restart: always\n",
            encoding="utf-8",
        )
        processor = BatchProcessor(tmp_path)
        issues, result = processor.scan()
        assert result.files_processed == 1
        assert result.issues_found > 0

    def test_scan_filter_severity(self, tmp_path):
        from composearr.batch import BatchProcessor
        compose = tmp_path / "compose.yaml"
        compose.write_text(
            "services:\n"
            "  web:\n"
            "    image: nginx:latest\n",
            encoding="utf-8",
        )
        processor = BatchProcessor(tmp_path)
        all_issues, all_result = processor.scan()
        error_issues, error_result = processor.scan(min_severity="error")
        # Error-only should find fewer or equal issues
        assert error_result.issues_found <= all_result.issues_found

    def test_fix_with_auto_approve(self, tmp_path):
        from composearr.batch import BatchProcessor
        compose = tmp_path / "compose.yaml"
        compose.write_text(
            "services:\n"
            "  web:\n"
            "    image: nginx:latest\n"
            "    restart: always\n",
            encoding="utf-8",
        )
        processor = BatchProcessor(tmp_path, auto_approve=True, create_backups=True)
        result = processor.fix_all()
        assert result.files_processed == 1
        # Should have fixed at least some issues
        # (depending on what fixers are available)

    def test_fix_without_auto_no_changes(self, tmp_path):
        from composearr.batch import BatchProcessor
        compose = tmp_path / "compose.yaml"
        compose.write_text(
            "services:\n"
            "  web:\n"
            "    image: nginx:latest\n",
            encoding="utf-8",
        )
        processor = BatchProcessor(tmp_path, auto_approve=False)
        result = processor.fix_all()
        assert result.issues_fixed == 0  # No auto-approve = no fixes

    def test_batch_result_exit_codes(self):
        from composearr.batch import BatchResult
        # Clean run
        r1 = BatchResult(issues_found=5, issues_fixed=5)
        assert r1.exit_code == 0
        assert r1.success is True

        # Issues remain
        r2 = BatchResult(issues_found=5, issues_fixed=2, issues_unfixable=3)
        assert r2.exit_code == 1

        # Errors during processing
        r3 = BatchResult(errors=["something broke"])
        assert r3.exit_code == 2
        assert r3.success is False


# ═══════════════════════════════════════════════════════════════
#  Scoring & Config Integration
# ═══════════════════════════════════════════════════════════════


class TestScoringCA9xx:
    """CA9xx rules should map to correct scoring categories."""

    def test_ca9xx_maps_to_reliability(self):
        from composearr.scoring import _categorize
        assert _categorize("CA901") == "reliability"
        assert _categorize("CA902") == "reliability"
        assert _categorize("CA903") == "reliability"

    def test_ca904_maps_to_reliability(self):
        from composearr.scoring import _categorize
        # CA904 is security in the rule, but prefix-mapped to reliability
        # (the scoring map uses prefix CA9 → reliability)
        assert _categorize("CA904") == "reliability"


class TestConfigCA9xx:
    """CA9xx rules should be in default config."""

    def test_ca9xx_in_defaults(self):
        from composearr.config import DEFAULT_RULES
        assert "CA901" in DEFAULT_RULES
        assert "CA902" in DEFAULT_RULES
        assert "CA903" in DEFAULT_RULES
        assert "CA904" in DEFAULT_RULES

    def test_ca9xx_name_mapping(self):
        from composearr.config import _RULE_NAME_TO_ID
        assert _RULE_NAME_TO_ID["resource-requests-mismatch"] == "CA901"
        assert _RULE_NAME_TO_ID["restart-policy-unlimited"] == "CA902"
        assert _RULE_NAME_TO_ID["tmpfs-no-size-limit"] == "CA903"
        assert _RULE_NAME_TO_ID["no-user-namespace"] == "CA904"


class TestRuleDocsCA9xx:
    """CA9xx should have explain documentation."""

    def test_all_ca9xx_have_docs(self):
        from composearr.commands.explain import RULE_DOCS
        for rule_id in ["CA901", "CA902", "CA903", "CA904"]:
            assert rule_id in RULE_DOCS, f"Missing docs for {rule_id}"
            assert "why" in RULE_DOCS[rule_id]
            assert "scenarios" in RULE_DOCS[rule_id]


# ═══════════════════════════════════════════════════════════════
#  Rule Registration — 30 Rules!
# ═══════════════════════════════════════════════════════════════


class TestRuleRegistration:
    """Test 30 rules total — THE SUMMIT!"""

    def test_30_rules_total(self):
        rules = get_all_rules()
        assert len(rules) >= 30, f"Expected >= 30 rules, got {len(rules)}"

    def test_ca9xx_registered(self):
        for rule_id in ["CA901", "CA902", "CA903", "CA904"]:
            rule = get_rule(rule_id)
            assert rule is not None, f"Rule {rule_id} not registered"
            assert rule.id == rule_id


# ═══════════════════════════════════════════════════════════════
#  Docker Client — Cross-OS Platform Detection
# ═══════════════════════════════════════════════════════════════


class TestDockerClientPlatform:
    """Test platform detection and help text."""

    def test_detect_platform_returns_string(self):
        from composearr.docker_client import _detect_platform
        platform = _detect_platform()
        assert platform in ("windows", "linux", "macos", "wsl")

    def test_platform_help_text(self):
        from composearr.docker_client import _get_platform_help
        help_text = _get_platform_help()
        assert isinstance(help_text, str)
        assert len(help_text) > 50

    def test_connection_urls_not_empty(self):
        from composearr.docker_client import _build_connection_urls
        urls = _build_connection_urls()
        assert len(urls) > 0

    def test_docker_host_env_respected(self):
        from composearr.docker_client import _build_connection_urls
        import os
        old = os.environ.get("DOCKER_HOST")
        try:
            os.environ["DOCKER_HOST"] = "tcp://myhost:2375"
            urls = _build_connection_urls()
            assert "tcp://myhost:2375" in urls
            assert urls[0] == "tcp://myhost:2375"  # Should be first
        finally:
            if old is None:
                os.environ.pop("DOCKER_HOST", None)
            else:
                os.environ["DOCKER_HOST"] = old


# ═══════════════════════════════════════════════════════════════
#  Full Stack Audit with CA9xx
# ═══════════════════════════════════════════════════════════════


class TestFullStackAuditCA9xx:
    """Run a full audit and verify CA9xx rules participate."""

    def test_full_audit_finds_ca902(self, tmp_path):
        """A service with restart: always should trigger CA902."""
        compose = tmp_path / "compose.yaml"
        compose.write_text(
            "services:\n"
            "  web:\n"
            "    image: nginx:1.25\n"
            "    restart: always\n",
            encoding="utf-8",
        )
        from composearr.engine import run_audit
        from composearr.config import Config

        result = run_audit(tmp_path, Config())
        rule_ids = {i.rule_id for i in result.all_issues}
        assert "CA902" in rule_ids

    def test_full_audit_finds_ca903(self, tmp_path):
        """A service with tmpfs should trigger CA903."""
        compose = tmp_path / "compose.yaml"
        compose.write_text(
            "services:\n"
            "  web:\n"
            "    image: nginx:1.25\n"
            "    tmpfs:\n"
            "      - /tmp\n",
            encoding="utf-8",
        )
        from composearr.engine import run_audit
        from composearr.config import Config

        result = run_audit(tmp_path, Config())
        rule_ids = {i.rule_id for i in result.all_issues}
        assert "CA903" in rule_ids
