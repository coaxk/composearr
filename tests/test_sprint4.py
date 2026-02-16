"""Sprint 4 tests — Security Hardening Rules (CA801-CA804)."""

from __future__ import annotations

from pathlib import Path

import pytest

from composearr.models import ComposeFile, LintIssue, Severity
from composearr.rules.base import get_all_rules, get_rule
from composearr.scanner.parser import parse_compose_file


def _make_cf(tmp_path: Path, content: str) -> ComposeFile:
    """Helper: write content to a temp file and parse it."""
    f = tmp_path / "compose.yaml"
    f.write_text(content, encoding="utf-8")
    return parse_compose_file(f)


# ═══════════════════════════════════════════════════════════════
# CA801: NO CAPABILITY RESTRICTIONS
# ═══════════════════════════════════════════════════════════════


class TestCA801NoCapabilityRestrictions:
    """Test CA801 — no-capability-restrictions."""

    def test_no_cap_drop_triggers(self, tmp_path):
        cf = _make_cf(tmp_path, "services:\n  web:\n    image: nginx\n")
        rule = get_rule("CA801")
        issues = rule.check_service("web", cf.services["web"], cf)
        assert len(issues) == 1
        assert issues[0].rule_id == "CA801"
        assert issues[0].severity == Severity.INFO

    def test_with_cap_drop_passes(self, tmp_path):
        cf = _make_cf(tmp_path, "services:\n  web:\n    image: nginx\n    cap_drop:\n      - ALL\n")
        rule = get_rule("CA801")
        issues = rule.check_service("web", cf.services["web"], cf)
        assert len(issues) == 0

    def test_with_partial_cap_drop_passes(self, tmp_path):
        cf = _make_cf(tmp_path, "services:\n  web:\n    image: nginx\n    cap_drop:\n      - NET_RAW\n")
        rule = get_rule("CA801")
        issues = rule.check_service("web", cf.services["web"], cf)
        assert len(issues) == 0

    def test_skipped_when_privileged(self, tmp_path):
        cf = _make_cf(tmp_path, "services:\n  app:\n    image: myapp\n    privileged: true\n")
        rule = get_rule("CA801")
        issues = rule.check_service("app", cf.services["app"], cf)
        assert len(issues) == 0

    def test_known_vpn_gluetun(self, tmp_path):
        cf = _make_cf(tmp_path, "services:\n  vpn:\n    image: qmcgaw/gluetun\n")
        rule = get_rule("CA801")
        issues = rule.check_service("vpn", cf.services["vpn"], cf)
        assert len(issues) == 1
        assert "NET_ADMIN" in issues[0].suggested_fix

    def test_known_vpn_wireguard(self, tmp_path):
        cf = _make_cf(tmp_path, "services:\n  wg:\n    image: linuxserver/wireguard\n")
        rule = get_rule("CA801")
        issues = rule.check_service("wg", cf.services["wg"], cf)
        assert len(issues) == 1
        assert "NET_ADMIN" in issues[0].suggested_fix
        assert "SYS_MODULE" in issues[0].suggested_fix

    def test_known_tailscale(self, tmp_path):
        cf = _make_cf(tmp_path, "services:\n  ts:\n    image: tailscale/tailscale\n")
        rule = get_rule("CA801")
        issues = rule.check_service("ts", cf.services["ts"], cf)
        assert len(issues) == 1
        assert "NET_ADMIN" in issues[0].suggested_fix

    def test_known_dind(self, tmp_path):
        cf = _make_cf(tmp_path, "services:\n  dind:\n    image: docker:dind\n")
        rule = get_rule("CA801")
        issues = rule.check_service("dind", cf.services["dind"], cf)
        assert len(issues) == 1
        assert "SYS_ADMIN" in issues[0].suggested_fix

    def test_generic_service_suggestion(self, tmp_path):
        cf = _make_cf(tmp_path, "services:\n  app:\n    image: myapp:latest\n")
        rule = get_rule("CA801")
        issues = rule.check_service("app", cf.services["app"], cf)
        assert len(issues) == 1
        assert "cap_drop" in issues[0].suggested_fix.lower()
        assert "ALL" in issues[0].suggested_fix

    def test_no_image_still_triggers(self, tmp_path):
        cf = _make_cf(tmp_path, "services:\n  app:\n    build: .\n")
        rule = get_rule("CA801")
        issues = rule.check_service("app", cf.services["app"], cf)
        assert len(issues) == 1

    def test_rule_metadata(self):
        rule = get_rule("CA801")
        assert rule.id == "CA801"
        assert rule.name == "no-capability-restrictions"
        assert rule.severity == Severity.INFO
        assert rule.category == "security"


# ═══════════════════════════════════════════════════════════════
# CA802: PRIVILEGED MODE
# ═══════════════════════════════════════════════════════════════


class TestCA802PrivilegedMode:
    """Test CA802 — privileged-mode."""

    def test_privileged_unknown_service_error(self, tmp_path):
        cf = _make_cf(tmp_path, "services:\n  app:\n    image: myapp\n    privileged: true\n")
        rule = get_rule("CA802")
        issues = rule.check_service("app", cf.services["app"], cf)
        assert len(issues) == 1
        assert issues[0].severity == Severity.ERROR
        assert "security risk" in issues[0].message.lower()

    def test_privileged_dind_warning(self, tmp_path):
        cf = _make_cf(tmp_path, "services:\n  dind:\n    image: docker:dind\n    privileged: true\n")
        rule = get_rule("CA802")
        issues = rule.check_service("dind", cf.services["dind"], cf)
        assert len(issues) == 1
        assert issues[0].severity == Severity.WARNING
        assert "Docker-in-Docker" in issues[0].message

    def test_privileged_docker_image_warning(self, tmp_path):
        cf = _make_cf(tmp_path, "services:\n  ci:\n    image: docker:24.0\n    privileged: true\n")
        rule = get_rule("CA802")
        issues = rule.check_service("ci", cf.services["ci"], cf)
        assert len(issues) == 1
        assert issues[0].severity == Severity.WARNING

    def test_not_privileged_passes(self, tmp_path):
        cf = _make_cf(tmp_path, "services:\n  app:\n    image: nginx\n")
        rule = get_rule("CA802")
        issues = rule.check_service("app", cf.services["app"], cf)
        assert len(issues) == 0

    def test_privileged_false_passes(self, tmp_path):
        cf = _make_cf(tmp_path, "services:\n  app:\n    image: nginx\n    privileged: false\n")
        rule = get_rule("CA802")
        issues = rule.check_service("app", cf.services["app"], cf)
        assert len(issues) == 0

    def test_fix_available(self, tmp_path):
        cf = _make_cf(tmp_path, "services:\n  app:\n    image: myapp\n    privileged: true\n")
        rule = get_rule("CA802")
        issues = rule.check_service("app", cf.services["app"], cf)
        assert issues[0].fix_available is True

    def test_rule_metadata(self):
        rule = get_rule("CA802")
        assert rule.id == "CA802"
        assert rule.name == "privileged-mode"
        assert rule.severity == Severity.ERROR
        assert rule.category == "security"


# ═══════════════════════════════════════════════════════════════
# CA803: NO READ-ONLY ROOT
# ═══════════════════════════════════════════════════════════════


class TestCA803NoReadOnlyRoot:
    """Test CA803 — no-read-only-root."""

    def test_nginx_no_readonly_triggers(self, tmp_path):
        cf = _make_cf(tmp_path, "services:\n  web:\n    image: nginx\n")
        rule = get_rule("CA803")
        issues = rule.check_service("web", cf.services["web"], cf)
        assert len(issues) == 1
        assert issues[0].rule_id == "CA803"
        assert "nginx" in issues[0].message

    def test_nginx_with_readonly_passes(self, tmp_path):
        cf = _make_cf(tmp_path, "services:\n  web:\n    image: nginx\n    read_only: true\n")
        rule = get_rule("CA803")
        issues = rule.check_service("web", cf.services["web"], cf)
        assert len(issues) == 0

    def test_caddy_triggers(self, tmp_path):
        cf = _make_cf(tmp_path, "services:\n  proxy:\n    image: caddy:2\n")
        rule = get_rule("CA803")
        issues = rule.check_service("proxy", cf.services["proxy"], cf)
        assert len(issues) == 1
        assert "caddy" in issues[0].message

    def test_traefik_triggers(self, tmp_path):
        cf = _make_cf(tmp_path, "services:\n  proxy:\n    image: traefik:v2.10\n")
        rule = get_rule("CA803")
        issues = rule.check_service("proxy", cf.services["proxy"], cf)
        assert len(issues) == 1
        assert "traefik" in issues[0].message

    def test_redis_triggers(self, tmp_path):
        cf = _make_cf(tmp_path, "services:\n  cache:\n    image: redis:7\n")
        rule = get_rule("CA803")
        issues = rule.check_service("cache", cf.services["cache"], cf)
        assert len(issues) == 1
        assert "redis" in issues[0].message

    def test_sonarr_skipped(self, tmp_path):
        cf = _make_cf(tmp_path, "services:\n  sonarr:\n    image: lscr.io/linuxserver/sonarr\n")
        rule = get_rule("CA803")
        issues = rule.check_service("sonarr", cf.services["sonarr"], cf)
        assert len(issues) == 0

    def test_radarr_skipped(self, tmp_path):
        cf = _make_cf(tmp_path, "services:\n  radarr:\n    image: lscr.io/linuxserver/radarr\n")
        rule = get_rule("CA803")
        issues = rule.check_service("radarr", cf.services["radarr"], cf)
        assert len(issues) == 0

    def test_plex_skipped(self, tmp_path):
        cf = _make_cf(tmp_path, "services:\n  plex:\n    image: lscr.io/linuxserver/plex\n")
        rule = get_rule("CA803")
        issues = rule.check_service("plex", cf.services["plex"], cf)
        assert len(issues) == 0

    def test_postgres_skipped(self, tmp_path):
        cf = _make_cf(tmp_path, "services:\n  db:\n    image: postgres:16\n")
        rule = get_rule("CA803")
        issues = rule.check_service("db", cf.services["db"], cf)
        assert len(issues) == 0

    def test_unknown_service_skipped(self, tmp_path):
        """Unknown services are NOT flagged (only known-safe ones trigger)."""
        cf = _make_cf(tmp_path, "services:\n  app:\n    image: myapp:latest\n")
        rule = get_rule("CA803")
        issues = rule.check_service("app", cf.services["app"], cf)
        assert len(issues) == 0

    def test_tmpfs_in_suggestion(self, tmp_path):
        cf = _make_cf(tmp_path, "services:\n  web:\n    image: nginx\n")
        rule = get_rule("CA803")
        issues = rule.check_service("web", cf.services["web"], cf)
        assert "tmpfs" in issues[0].suggested_fix
        assert "/var/cache/nginx" in issues[0].suggested_fix

    def test_bazarr_skipped(self, tmp_path):
        cf = _make_cf(tmp_path, "services:\n  bazarr:\n    image: lscr.io/linuxserver/bazarr\n")
        rule = get_rule("CA803")
        issues = rule.check_service("bazarr", cf.services["bazarr"], cf)
        assert len(issues) == 0

    def test_qbittorrent_skipped(self, tmp_path):
        cf = _make_cf(tmp_path, "services:\n  qbt:\n    image: lscr.io/linuxserver/qbittorrent\n")
        rule = get_rule("CA803")
        issues = rule.check_service("qbt", cf.services["qbt"], cf)
        assert len(issues) == 0

    def test_rule_metadata(self):
        rule = get_rule("CA803")
        assert rule.id == "CA803"
        assert rule.name == "no-read-only-root"
        assert rule.severity == Severity.INFO
        assert rule.category == "security"


# ═══════════════════════════════════════════════════════════════
# CA804: NO NEW PRIVILEGES
# ═══════════════════════════════════════════════════════════════


class TestCA804NoNewPrivileges:
    """Test CA804 — no-new-privileges."""

    def test_missing_nnp_triggers(self, tmp_path):
        cf = _make_cf(tmp_path, "services:\n  app:\n    image: nginx\n")
        rule = get_rule("CA804")
        issues = rule.check_service("app", cf.services["app"], cf)
        assert len(issues) == 1
        assert issues[0].rule_id == "CA804"
        assert "no-new-privileges" in issues[0].message

    def test_with_nnp_passes(self, tmp_path):
        cf = _make_cf(tmp_path, 'services:\n  app:\n    image: nginx\n    security_opt:\n      - "no-new-privileges:true"\n')
        rule = get_rule("CA804")
        issues = rule.check_service("app", cf.services["app"], cf)
        assert len(issues) == 0

    def test_with_other_security_opts_triggers(self, tmp_path):
        cf = _make_cf(tmp_path, 'services:\n  app:\n    image: nginx\n    security_opt:\n      - "seccomp:default"\n')
        rule = get_rule("CA804")
        issues = rule.check_service("app", cf.services["app"], cf)
        assert len(issues) == 1

    def test_empty_security_opt_triggers(self, tmp_path):
        cf = _make_cf(tmp_path, "services:\n  app:\n    image: nginx\n    security_opt: []\n")
        rule = get_rule("CA804")
        issues = rule.check_service("app", cf.services["app"], cf)
        assert len(issues) == 1

    def test_fix_available(self, tmp_path):
        cf = _make_cf(tmp_path, "services:\n  app:\n    image: nginx\n")
        rule = get_rule("CA804")
        issues = rule.check_service("app", cf.services["app"], cf)
        assert issues[0].fix_available is True

    def test_multiple_services(self, tmp_path):
        content = (
            "services:\n"
            "  web:\n    image: nginx\n"
            "  api:\n    image: node:20\n"
            '  safe:\n    image: redis\n    security_opt:\n      - "no-new-privileges:true"\n'
        )
        cf = _make_cf(tmp_path, content)
        rule = get_rule("CA804")
        all_issues = []
        for svc_name, svc_config in cf.services.items():
            all_issues.extend(rule.check_service(svc_name, svc_config, cf))
        # web and api trigger, safe does not
        triggered = {i.service for i in all_issues}
        assert "web" in triggered
        assert "api" in triggered
        assert "safe" not in triggered

    def test_rule_metadata(self):
        rule = get_rule("CA804")
        assert rule.id == "CA804"
        assert rule.name == "no-new-privileges"
        assert rule.severity == Severity.INFO
        assert rule.category == "security"


# ═══════════════════════════════════════════════════════════════
# HELPER FUNCTION TESTS
# ═══════════════════════════════════════════════════════════════


class TestDetectApp:
    """Test the _detect_app helper."""

    def test_simple_image(self):
        from composearr.rules.CA8xx_security import _detect_app, _KNOWN_NEEDS_CAPS
        assert _detect_app("nginx", _KNOWN_NEEDS_CAPS) == ""
        assert _detect_app("qmcgaw/gluetun", _KNOWN_NEEDS_CAPS) == "gluetun"
        assert _detect_app("docker:dind", _KNOWN_NEEDS_CAPS) == "docker"

    def test_registry_prefix(self):
        from composearr.rules.CA8xx_security import _detect_app, _KNOWN_NEEDS_CAPS
        assert _detect_app("ghcr.io/qdm12/gluetun", _KNOWN_NEEDS_CAPS) == "gluetun"
        assert _detect_app("lscr.io/linuxserver/wireguard", _KNOWN_NEEDS_CAPS) == "wireguard"

    def test_empty_image(self):
        from composearr.rules.CA8xx_security import _detect_app, _KNOWN_NEEDS_CAPS
        assert _detect_app("", _KNOWN_NEEDS_CAPS) == ""

    def test_writable_detection(self):
        from composearr.rules.CA8xx_security import _detect_app, _NEEDS_WRITABLE
        assert _detect_app("lscr.io/linuxserver/sonarr", _NEEDS_WRITABLE) == "sonarr"
        assert _detect_app("postgres:16", _NEEDS_WRITABLE) == "postgres"
        assert _detect_app("nginx:latest", _NEEDS_WRITABLE) == ""

    def test_readonly_safe_detection(self):
        from composearr.rules.CA8xx_security import _detect_app, _READONLY_SAFE
        assert _detect_app("nginx:1.25", _READONLY_SAFE) == "nginx"
        assert _detect_app("caddy:2", _READONLY_SAFE) == "caddy"
        assert _detect_app("traefik:v2.10", _READONLY_SAFE) == "traefik"
        assert _detect_app("redis:7", _READONLY_SAFE) == "redis"


# ═══════════════════════════════════════════════════════════════
# AUTO-FIX TESTS
# ═══════════════════════════════════════════════════════════════


class TestFixPrivilegedMode:
    """Test CA802 auto-fix — remove privileged mode."""

    def test_fix_removes_privileged(self, tmp_path):
        from composearr.fixer import apply_fixes

        compose = tmp_path / "compose.yaml"
        compose.write_text(
            "services:\n  app:\n    image: myapp\n    privileged: true\n",
            encoding="utf-8",
        )

        issue = LintIssue(
            rule_id="CA802",
            rule_name="privileged-mode",
            severity=Severity.ERROR,
            message="Running in privileged mode",
            file_path=str(compose),
            service="app",
            fix_available=True,
            suggested_fix="Remove privileged: true",
        )

        result = apply_fixes([issue], tmp_path, backup=False)
        assert result.applied == 1

        from ruamel.yaml import YAML
        yaml = YAML()
        data = yaml.load(compose)
        assert "privileged" not in data["services"]["app"]

    def test_fix_preserves_other_keys(self, tmp_path):
        from composearr.fixer import apply_fixes

        compose = tmp_path / "compose.yaml"
        compose.write_text(
            "services:\n  app:\n    image: myapp\n    privileged: true\n    restart: unless-stopped\n",
            encoding="utf-8",
        )

        issue = LintIssue(
            rule_id="CA802",
            rule_name="privileged-mode",
            severity=Severity.ERROR,
            message="Running in privileged mode",
            file_path=str(compose),
            service="app",
            fix_available=True,
            suggested_fix="Remove privileged: true",
        )

        result = apply_fixes([issue], tmp_path, backup=False)
        assert result.applied == 1

        from ruamel.yaml import YAML
        yaml = YAML()
        data = yaml.load(compose)
        assert data["services"]["app"]["restart"] == "unless-stopped"
        assert data["services"]["app"]["image"] == "myapp"

    def test_fix_no_service(self, tmp_path):
        from composearr.fixer import apply_fixes

        compose = tmp_path / "compose.yaml"
        compose.write_text("services:\n  app:\n    image: myapp\n", encoding="utf-8")

        issue = LintIssue(
            rule_id="CA802",
            rule_name="privileged-mode",
            severity=Severity.ERROR,
            message="test",
            file_path=str(compose),
            service=None,
            fix_available=True,
            suggested_fix="test",
        )

        result = apply_fixes([issue], tmp_path, backup=False)
        assert result.skipped == 1


class TestFixNoNewPrivileges:
    """Test CA804 auto-fix — add no-new-privileges."""

    def test_fix_adds_security_opt(self, tmp_path):
        from composearr.fixer import apply_fixes

        compose = tmp_path / "compose.yaml"
        compose.write_text(
            "services:\n  app:\n    image: nginx\n",
            encoding="utf-8",
        )

        issue = LintIssue(
            rule_id="CA804",
            rule_name="no-new-privileges",
            severity=Severity.INFO,
            message="Missing no-new-privileges",
            file_path=str(compose),
            service="app",
            fix_available=True,
            suggested_fix="Add security_opt",
        )

        result = apply_fixes([issue], tmp_path, backup=False)
        assert result.applied == 1

        from ruamel.yaml import YAML
        yaml = YAML()
        data = yaml.load(compose)
        assert "no-new-privileges:true" in data["services"]["app"]["security_opt"]

    def test_fix_appends_to_existing(self, tmp_path):
        from composearr.fixer import apply_fixes

        compose = tmp_path / "compose.yaml"
        compose.write_text(
            'services:\n  app:\n    image: nginx\n    security_opt:\n      - "seccomp:default"\n',
            encoding="utf-8",
        )

        issue = LintIssue(
            rule_id="CA804",
            rule_name="no-new-privileges",
            severity=Severity.INFO,
            message="Missing no-new-privileges",
            file_path=str(compose),
            service="app",
            fix_available=True,
            suggested_fix="Add security_opt",
        )

        result = apply_fixes([issue], tmp_path, backup=False)
        assert result.applied == 1

        from ruamel.yaml import YAML
        yaml = YAML()
        data = yaml.load(compose)
        sec_opts = data["services"]["app"]["security_opt"]
        assert "seccomp:default" in sec_opts
        assert "no-new-privileges:true" in sec_opts

    def test_fix_idempotent(self, tmp_path):
        from composearr.fixer import apply_fixes

        compose = tmp_path / "compose.yaml"
        compose.write_text(
            'services:\n  app:\n    image: nginx\n    security_opt:\n      - "no-new-privileges:true"\n',
            encoding="utf-8",
        )

        issue = LintIssue(
            rule_id="CA804",
            rule_name="no-new-privileges",
            severity=Severity.INFO,
            message="Missing no-new-privileges",
            file_path=str(compose),
            service="app",
            fix_available=True,
            suggested_fix="Add security_opt",
        )

        result = apply_fixes([issue], tmp_path, backup=False)
        assert result.skipped == 1


# ═══════════════════════════════════════════════════════════════
# INTEGRATION TESTS
# ═══════════════════════════════════════════════════════════════


class TestScoringCA8xx:
    """Test that CA8xx issues map to the security scoring category."""

    def test_ca802_security_category(self):
        from composearr.scoring import _categorize
        assert _categorize("CA801") == "security"
        assert _categorize("CA802") == "security"
        assert _categorize("CA803") == "security"
        assert _categorize("CA804") == "security"

    def test_privileged_lowers_security_score(self):
        from composearr.scoring import calculate_stack_score

        issues = [
            LintIssue(
                rule_id="CA802", rule_name="privileged-mode",
                severity=Severity.ERROR, message="test",
                file_path="test.yaml", service="app",
            ),
        ]
        score = calculate_stack_score(issues, total_services=5)
        assert score.breakdown.security < 100
        assert score.error_count == 1


class TestConfigCA8xx:
    """Test config integration for CA8xx rules."""

    def test_default_severities(self):
        from composearr.config import DEFAULT_RULES
        assert DEFAULT_RULES["CA801"] == "info"
        assert DEFAULT_RULES["CA802"] == "error"
        assert DEFAULT_RULES["CA803"] == "info"
        assert DEFAULT_RULES["CA804"] == "info"

    def test_name_to_id_mapping(self):
        from composearr.config import _RULE_NAME_TO_ID
        assert _RULE_NAME_TO_ID["no-capability-restrictions"] == "CA801"
        assert _RULE_NAME_TO_ID["privileged-mode"] == "CA802"
        assert _RULE_NAME_TO_ID["no-read-only-root"] == "CA803"
        assert _RULE_NAME_TO_ID["no-new-privileges"] == "CA804"

    def test_config_disable_rule(self):
        from composearr.config import Config
        config = Config()
        assert config.is_rule_enabled("CA801") is True
        config.rules["CA801"] = "off"
        assert config.is_rule_enabled("CA801") is False


class TestRuleDocsCA8xx:
    """Test that RULE_DOCS exist for CA8xx rules."""

    def test_docs_exist(self):
        from composearr.commands.explain import RULE_DOCS
        for rule_id in ("CA801", "CA802", "CA803", "CA804"):
            assert rule_id in RULE_DOCS, f"Missing RULE_DOCS for {rule_id}"
            docs = RULE_DOCS[rule_id]
            assert "why" in docs
            assert "scenarios" in docs
            assert "fix_examples" in docs
            assert "related" in docs
            assert "learn_more" in docs

    def test_docs_have_content(self):
        from composearr.commands.explain import RULE_DOCS
        for rule_id in ("CA801", "CA802", "CA803", "CA804"):
            docs = RULE_DOCS[rule_id]
            assert len(docs["why"]) > 50
            assert len(docs["scenarios"]) >= 2
            assert len(docs["fix_examples"]) >= 1
            assert len(docs["related"]) >= 1


class TestRuleRegistration:
    """Test all 25 rules are registered."""

    def test_at_least_25_rules(self):
        rules = get_all_rules()
        assert len(rules) >= 25, f"Expected at least 25 rules, got {len(rules)}"

    def test_ca8xx_rules_present(self):
        for rule_id in ("CA801", "CA802", "CA803", "CA804"):
            rule = get_rule(rule_id)
            assert rule is not None, f"Rule {rule_id} not registered"
            assert rule.category == "security"


class TestFullStackAudit:
    """Integration test: run all rules against a realistic compose file."""

    def test_security_issues_detected(self, tmp_path):
        """A file with security issues should trigger CA801-CA804."""
        content = (
            "services:\n"
            "  web:\n"
            "    image: nginx\n"
            "  dangerous:\n"
            "    image: myapp\n"
            "    privileged: true\n"
        )
        cf = _make_cf(tmp_path, content)

        all_issues = []
        for rule in get_all_rules():
            for svc_name, svc_config in cf.services.items():
                all_issues.extend(rule.check_service(svc_name, svc_config, cf))
            all_issues.extend(rule.check_file(cf))

        ca8_ids = {i.rule_id for i in all_issues if i.rule_id.startswith("CA8")}
        assert "CA801" in ca8_ids  # web has no cap_drop
        assert "CA802" in ca8_ids  # dangerous is privileged
        assert "CA804" in ca8_ids  # both miss no-new-privileges

    def test_hardened_service_clean(self, tmp_path):
        """A properly hardened service should not trigger CA801-CA804."""
        content = (
            "services:\n"
            "  web:\n"
            "    image: nginx\n"
            "    read_only: true\n"
            "    cap_drop:\n"
            "      - ALL\n"
            '    security_opt:\n'
            '      - "no-new-privileges:true"\n'
            "    tmpfs:\n"
            "      - /var/cache/nginx\n"
            "      - /var/run\n"
        )
        cf = _make_cf(tmp_path, content)

        ca8_issues = []
        for rule in get_all_rules():
            for svc_name, svc_config in cf.services.items():
                issues = rule.check_service(svc_name, svc_config, cf)
                ca8_issues.extend(i for i in issues if i.rule_id.startswith("CA8"))

        assert len(ca8_issues) == 0, f"Hardened service triggered: {[i.rule_id for i in ca8_issues]}"
