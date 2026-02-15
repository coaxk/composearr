"""Tests for all 10 lint rules."""

from __future__ import annotations

from pathlib import Path

import pytest

from composearr.models import ComposeFile, Severity
from composearr.rules.base import get_all_rules, get_rule
from composearr.scanner.parser import parse_compose_file


def _make_cf(tmp_path: Path, content: str) -> ComposeFile:
    """Helper: write content to a temp file and parse it."""
    f = tmp_path / "compose.yaml"
    f.write_text(content, encoding="utf-8")
    return parse_compose_file(f)


def _run_service_rule(rule_id: str, service_name: str, service_config: dict, cf: ComposeFile):
    """Run a service-scope rule and return issues."""
    rule = get_rule(rule_id)
    assert rule is not None
    return rule.check_service(service_name, service_config, cf)


# ── CA001: No Latest Tag ─────────────────────────────────────


class TestCA001:
    def test_detects_latest(self, tmp_path: Path):
        cf = _make_cf(tmp_path, "services:\n  web:\n    image: nginx:latest\n")
        issues = _run_service_rule("CA001", "web", {"image": "nginx:latest"}, cf)
        assert len(issues) == 1
        assert issues[0].rule_id == "CA001"

    def test_detects_no_tag(self, tmp_path: Path):
        cf = _make_cf(tmp_path, "services:\n  web:\n    image: nginx\n")
        issues = _run_service_rule("CA001", "web", {"image": "nginx"}, cf)
        assert len(issues) == 1

    def test_detects_nightly(self, tmp_path: Path):
        cf = _make_cf(tmp_path, "services:\n  web:\n    image: app:nightly\n")
        issues = _run_service_rule("CA001", "web", {"image": "app:nightly"}, cf)
        assert len(issues) == 1

    def test_allows_pinned_version(self, tmp_path: Path):
        cf = _make_cf(tmp_path, "services:\n  web:\n    image: nginx:1.21.6\n")
        issues = _run_service_rule("CA001", "web", {"image": "nginx:1.21.6"}, cf)
        assert len(issues) == 0

    def test_allows_sha_digest(self, tmp_path: Path):
        cf = _make_cf(tmp_path, "services:\n  web:\n    image: nginx@sha256:abc123\n")
        issues = _run_service_rule("CA001", "web", {"image": "nginx@sha256:abc123"}, cf)
        assert len(issues) == 0

    def test_no_image_key(self, tmp_path: Path):
        cf = _make_cf(tmp_path, "services:\n  web:\n    build: .\n")
        issues = _run_service_rule("CA001", "web", {"build": "."}, cf)
        assert len(issues) == 0

    def test_registry_prefix(self, tmp_path: Path):
        cf = _make_cf(tmp_path, "services:\n  web:\n    image: ghcr.io/org/app:latest\n")
        issues = _run_service_rule("CA001", "web", {"image": "ghcr.io/org/app:latest"}, cf)
        assert len(issues) == 1


# ── CA101: No Inline Secrets ─────────────────────────────────


class TestCA101:
    def test_detects_password(self, tmp_path: Path):
        cf = _make_cf(tmp_path, "services:\n  app:\n    environment:\n      DB_PASSWORD: SuperSecretP@ss123!\n")
        issues = _run_service_rule("CA101", "app", {
            "environment": {"DB_PASSWORD": "SuperSecretP@ss123!"}
        }, cf)
        assert len(issues) == 1
        assert "DB_PASSWORD" in issues[0].message

    def test_ignores_variable_reference(self, tmp_path: Path):
        cf = _make_cf(tmp_path, "services:\n  app:\n    environment:\n      API_KEY: ${API_KEY}\n")
        issues = _run_service_rule("CA101", "app", {
            "environment": {"API_KEY": "${API_KEY}"}
        }, cf)
        assert len(issues) == 0

    def test_ignores_placeholder(self, tmp_path: Path):
        cf = _make_cf(tmp_path, "services:\n  app:\n    environment:\n      PASSWORD: changeme\n")
        issues = _run_service_rule("CA101", "app", {
            "environment": {"PASSWORD": "changeme"}
        }, cf)
        assert len(issues) == 0

    def test_ignores_boolean(self, tmp_path: Path):
        cf = _make_cf(tmp_path, "services:\n  app:\n    environment:\n      AUTH_ENABLED: true\n")
        issues = _run_service_rule("CA101", "app", {
            "environment": {"AUTH_ENABLED": "true"}
        }, cf)
        assert len(issues) == 0

    def test_ignores_short_value(self, tmp_path: Path):
        cf = _make_cf(tmp_path, "services:\n  app:\n    environment:\n      TOKEN: abc\n")
        issues = _run_service_rule("CA101", "app", {
            "environment": {"TOKEN": "abc"}
        }, cf)
        assert len(issues) == 0

    def test_detects_wireguard_key(self, tmp_path: Path):
        key = "bijL6fcCeVv25izRy3JseahatW9rsd0eCpo5aLricRI="
        cf = _make_cf(tmp_path, f"services:\n  vpn:\n    environment:\n      WIREGUARD_PRIVATE_KEY: {key}\n")
        issues = _run_service_rule("CA101", "vpn", {
            "environment": {"WIREGUARD_PRIVATE_KEY": key}
        }, cf)
        assert len(issues) == 1

    def test_list_format_env(self, tmp_path: Path):
        cf = _make_cf(tmp_path, "services:\n  app:\n    environment:\n      - DB_PASSWORD=SuperSecretP@ss123!\n")
        issues = _run_service_rule("CA101", "app", {
            "environment": ["DB_PASSWORD=SuperSecretP@ss123!"]
        }, cf)
        assert len(issues) == 1

    def test_no_environment(self, tmp_path: Path):
        cf = _make_cf(tmp_path, "services:\n  app:\n    image: nginx:1.0\n")
        issues = _run_service_rule("CA101", "app", {"image": "nginx:1.0"}, cf)
        assert len(issues) == 0


# ── CA201: Require Healthcheck ────────────────────────────────


class TestCA201:
    def test_flags_missing_healthcheck(self, tmp_path: Path):
        cf = _make_cf(tmp_path, "services:\n  web:\n    image: nginx:1.0\n")
        issues = _run_service_rule("CA201", "web", {"image": "nginx:1.0"}, cf)
        assert len(issues) == 1
        assert "healthcheck" in issues[0].message.lower()

    def test_passes_with_healthcheck(self, tmp_path: Path):
        cf = _make_cf(tmp_path, "services:\n  web:\n    image: nginx:1.0\n    healthcheck:\n      test: curl -f http://localhost\n")
        issues = _run_service_rule("CA201", "web", {
            "image": "nginx:1.0",
            "healthcheck": {"test": "curl -f http://localhost"},
        }, cf)
        assert len(issues) == 0


# ── CA202: No Fake Healthcheck ────────────────────────────────


class TestCA202:
    def test_detects_exit_0(self, tmp_path: Path):
        cf = _make_cf(tmp_path, "services:\n  web:\n    healthcheck:\n      test: exit 0\n")
        issues = _run_service_rule("CA202", "web", {
            "healthcheck": {"test": ["CMD-SHELL", "exit 0"]},
        }, cf)
        assert len(issues) == 1

    def test_detects_true(self, tmp_path: Path):
        cf = _make_cf(tmp_path, "services:\n  web:\n    healthcheck:\n      test: true\n")
        issues = _run_service_rule("CA202", "web", {
            "healthcheck": {"test": ["CMD-SHELL", "true"]},
        }, cf)
        assert len(issues) == 1

    def test_allows_real_check(self, tmp_path: Path):
        cf = _make_cf(tmp_path, "services:\n  web:\n    healthcheck:\n      test: curl -f http://localhost\n")
        issues = _run_service_rule("CA202", "web", {
            "healthcheck": {"test": ["CMD-SHELL", "curl -f http://localhost || exit 1"]},
        }, cf)
        assert len(issues) == 0

    def test_no_healthcheck(self, tmp_path: Path):
        cf = _make_cf(tmp_path, "services:\n  web:\n    image: nginx:1.0\n")
        issues = _run_service_rule("CA202", "web", {"image": "nginx:1.0"}, cf)
        assert len(issues) == 0


# ── CA203: Require Restart Policy ─────────────────────────────


class TestCA203:
    def test_flags_missing_restart(self, tmp_path: Path):
        cf = _make_cf(tmp_path, "services:\n  web:\n    image: nginx:1.0\n")
        issues = _run_service_rule("CA203", "web", {"image": "nginx:1.0"}, cf)
        assert len(issues) == 1

    def test_passes_with_restart(self, tmp_path: Path):
        cf = _make_cf(tmp_path, "services:\n  web:\n    image: nginx:1.0\n    restart: unless-stopped\n")
        issues = _run_service_rule("CA203", "web", {
            "image": "nginx:1.0", "restart": "unless-stopped"
        }, cf)
        assert len(issues) == 0


# ── CA301: Port Conflict (cross-file) ────────────────────────


class TestCA301:
    def test_detects_port_conflict(self, tmp_path: Path):
        f1 = tmp_path / "svc1" / "compose.yaml"
        f1.parent.mkdir()
        f1.write_text("services:\n  sonarr:\n    ports:\n      - '8080:8989'\n")

        f2 = tmp_path / "svc2" / "compose.yaml"
        f2.parent.mkdir()
        f2.write_text("services:\n  radarr:\n    ports:\n      - '8080:7878'\n")

        cf1 = parse_compose_file(f1)
        cf2 = parse_compose_file(f2)

        rule = get_rule("CA301")
        issues = rule.check_project([cf1, cf2])
        assert len(issues) == 1
        assert "8080" in issues[0].message

    def test_no_conflict_different_ports(self, tmp_path: Path):
        f1 = tmp_path / "svc1" / "compose.yaml"
        f1.parent.mkdir()
        f1.write_text("services:\n  sonarr:\n    ports:\n      - '8989:8989'\n")

        f2 = tmp_path / "svc2" / "compose.yaml"
        f2.parent.mkdir()
        f2.write_text("services:\n  radarr:\n    ports:\n      - '7878:7878'\n")

        cf1 = parse_compose_file(f1)
        cf2 = parse_compose_file(f2)

        rule = get_rule("CA301")
        issues = rule.check_project([cf1, cf2])
        assert len(issues) == 0

    def test_no_ports(self, tmp_path: Path):
        f1 = tmp_path / "compose.yaml"
        f1.write_text("services:\n  web:\n    image: nginx:1.0\n")
        cf1 = parse_compose_file(f1)
        rule = get_rule("CA301")
        issues = rule.check_project([cf1])
        assert len(issues) == 0


# ── CA401: PUID/PGID Mismatch (cross-file) ──────────────────


class TestCA401:
    def test_detects_mismatch(self, tmp_path: Path):
        f1 = tmp_path / "svc1" / "compose.yaml"
        f1.parent.mkdir()
        f1.write_text("services:\n  sonarr:\n    environment:\n      PUID: '1000'\n")

        f2 = tmp_path / "svc2" / "compose.yaml"
        f2.parent.mkdir()
        f2.write_text("services:\n  qbit:\n    environment:\n      PUID: '568'\n")

        cf1 = parse_compose_file(f1)
        cf2 = parse_compose_file(f2)

        rule = get_rule("CA401")
        issues = rule.check_project([cf1, cf2])
        assert len(issues) == 1
        assert "1000" in issues[0].message
        assert "568" in issues[0].message

    def test_no_mismatch(self, tmp_path: Path):
        f1 = tmp_path / "svc1" / "compose.yaml"
        f1.parent.mkdir()
        f1.write_text("services:\n  sonarr:\n    environment:\n      PUID: '1000'\n")

        f2 = tmp_path / "svc2" / "compose.yaml"
        f2.parent.mkdir()
        f2.write_text("services:\n  radarr:\n    environment:\n      PUID: '1000'\n")

        cf1 = parse_compose_file(f1)
        cf2 = parse_compose_file(f2)

        rule = get_rule("CA401")
        issues = rule.check_project([cf1, cf2])
        assert len(issues) == 0


# ── CA402: UMASK Inconsistent (cross-file) ───────────────────


class TestCA402:
    def test_detects_inconsistency(self, tmp_path: Path):
        f1 = tmp_path / "svc1" / "compose.yaml"
        f1.parent.mkdir()
        f1.write_text("services:\n  sonarr:\n    environment:\n      UMASK: '022'\n")

        f2 = tmp_path / "svc2" / "compose.yaml"
        f2.parent.mkdir()
        f2.write_text("services:\n  qbit:\n    environment:\n      UMASK: '002'\n")

        cf1 = parse_compose_file(f1)
        cf2 = parse_compose_file(f2)

        rule = get_rule("CA402")
        issues = rule.check_project([cf1, cf2])
        assert len(issues) == 1

    def test_consistent_umask(self, tmp_path: Path):
        f1 = tmp_path / "svc1" / "compose.yaml"
        f1.parent.mkdir()
        f1.write_text("services:\n  sonarr:\n    environment:\n      UMASK: '002'\n")

        f2 = tmp_path / "svc2" / "compose.yaml"
        f2.parent.mkdir()
        f2.write_text("services:\n  radarr:\n    environment:\n      UMASK: '002'\n")

        cf1 = parse_compose_file(f1)
        cf2 = parse_compose_file(f2)

        rule = get_rule("CA402")
        issues = rule.check_project([cf1, cf2])
        assert len(issues) == 0


# ── CA403: Missing Timezone ──────────────────────────────────


class TestCA403:
    def test_flags_missing_tz(self, tmp_path: Path):
        cf = _make_cf(tmp_path, "services:\n  web:\n    image: nginx:1.0\n")
        issues = _run_service_rule("CA403", "web", {"image": "nginx:1.0"}, cf)
        assert len(issues) == 1

    def test_passes_with_tz(self, tmp_path: Path):
        cf = _make_cf(tmp_path, "services:\n  web:\n    environment:\n      TZ: UTC\n")
        issues = _run_service_rule("CA403", "web", {
            "environment": {"TZ": "UTC"}
        }, cf)
        assert len(issues) == 0

    def test_passes_with_list_env(self, tmp_path: Path):
        cf = _make_cf(tmp_path, "services:\n  web:\n    environment:\n      - TZ=UTC\n")
        issues = _run_service_rule("CA403", "web", {
            "environment": ["TZ=UTC"]
        }, cf)
        assert len(issues) == 0


# ── CA601: Hardlink Path Mismatch ────────────────────────────


class TestCA601:
    def test_detects_split_mounts(self, tmp_path: Path):
        f = tmp_path / "compose.yaml"
        f.write_text(
            "services:\n  sonarr:\n    image: lscr.io/linuxserver/sonarr:latest\n"
            "    volumes:\n      - /mnt/media:/media\n      - /mnt/dl:/downloads\n"
        )
        cf = parse_compose_file(f)
        rule = get_rule("CA601")
        issues = rule.check_project([cf])
        assert len(issues) == 1

    def test_passes_unified_data(self, tmp_path: Path):
        f = tmp_path / "compose.yaml"
        f.write_text(
            "services:\n  sonarr:\n    image: lscr.io/linuxserver/sonarr:latest\n"
            "    volumes:\n      - /mnt/data:/data\n"
        )
        cf = parse_compose_file(f)
        rule = get_rule("CA601")
        issues = rule.check_project([cf])
        assert len(issues) == 0

    def test_ignores_non_arr_services(self, tmp_path: Path):
        f = tmp_path / "compose.yaml"
        f.write_text(
            "services:\n  nginx:\n    image: nginx:1.21\n"
            "    volumes:\n      - /mnt/media:/media\n"
        )
        cf = parse_compose_file(f)
        rule = get_rule("CA601")
        issues = rule.check_project([cf])
        assert len(issues) == 0


# ── Rule Registry ────────────────────────────────────────────


class TestRuleRegistry:
    def test_all_10_rules_registered(self):
        rules = get_all_rules()
        rule_ids = {r.id for r in rules}
        expected = {"CA001", "CA101", "CA201", "CA202", "CA203", "CA301", "CA401", "CA402", "CA403", "CA601"}
        assert rule_ids == expected

    def test_get_rule_by_id(self):
        rule = get_rule("CA001")
        assert rule is not None
        assert rule.id == "CA001"
        assert rule.name == "no-latest-tag"

    def test_get_nonexistent_rule(self):
        rule = get_rule("CA999")
        assert rule is None

    def test_rules_have_required_attrs(self):
        for rule in get_all_rules():
            assert rule.id
            assert rule.name
            assert rule.severity
            assert rule.scope
            assert rule.description
            assert rule.category
