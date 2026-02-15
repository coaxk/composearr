"""Tests for network topology rules (CA302, CA303) and topology helpers."""

from __future__ import annotations

from pathlib import Path

import pytest

from composearr.models import ComposeFile, Severity
from composearr.rules.base import get_rule
from composearr.rules.CA3xx_network_topology import (
    build_network_graph,
    can_communicate,
    _get_network_mode,
    _get_service_networks,
    _get_depends_on,
)
from composearr.scanner.parser import parse_compose_file


def _make_cf(tmp_path: Path, content: str, name: str = "compose.yaml") -> ComposeFile:
    f = tmp_path / name
    f.write_text(content, encoding="utf-8")
    return parse_compose_file(f)


# ── Helper unit tests ─────────────────────────────────────────


class TestHelpers:
    def test_get_network_mode_present(self):
        assert _get_network_mode({"network_mode": "host"}) == "host"

    def test_get_network_mode_absent(self):
        assert _get_network_mode({}) is None

    def test_get_service_networks_list(self):
        assert _get_service_networks({"networks": ["frontend", "backend"]}) == ["frontend", "backend"]

    def test_get_service_networks_dict(self):
        nets = _get_service_networks({"networks": {"frontend": {}, "backend": None}})
        assert sorted(nets) == ["backend", "frontend"]

    def test_get_service_networks_absent(self):
        assert _get_service_networks({}) == []

    def test_get_depends_on_list(self):
        assert _get_depends_on({"depends_on": ["db", "redis"]}) == ["db", "redis"]

    def test_get_depends_on_dict(self):
        deps = _get_depends_on({"depends_on": {"db": {"condition": "service_healthy"}}})
        assert deps == ["db"]

    def test_get_depends_on_absent(self):
        assert _get_depends_on({}) == []


# ── Network graph building ────────────────────────────────────


class TestBuildNetworkGraph:
    def test_builds_from_single_file(self, tmp_path: Path):
        cf = _make_cf(tmp_path, """
services:
  web:
    image: nginx
    networks:
      - frontend
  db:
    image: postgres
    networks:
      - backend
networks:
  frontend: {}
  backend:
    internal: true
""")
        graph = build_network_graph([cf])
        assert "web" in graph["services"]
        assert "db" in graph["services"]
        assert graph["services"]["web"]["networks"] == ["frontend"]
        assert graph["networks"]["backend"]["internal"] is True

    def test_builds_from_multiple_files(self, tmp_path: Path):
        cf1 = _make_cf(tmp_path, "services:\n  web:\n    image: nginx\n", "web.yaml")
        cf2 = _make_cf(tmp_path, "services:\n  db:\n    image: postgres\n", "db.yaml")
        graph = build_network_graph([cf1, cf2])
        assert len(graph["services"]) == 2


# ── Communication checks ─────────────────────────────────────


class TestCanCommunicate:
    def test_default_bridge_same_file(self, tmp_path: Path):
        cf = _make_cf(tmp_path, """
services:
  web:
    image: nginx
  db:
    image: postgres
""")
        graph = build_network_graph([cf])
        assert can_communicate(graph, "web", "db") is True

    def test_shared_custom_network(self, tmp_path: Path):
        cf = _make_cf(tmp_path, """
services:
  web:
    image: nginx
    networks: [app]
  db:
    image: postgres
    networks: [app]
networks:
  app: {}
""")
        graph = build_network_graph([cf])
        assert can_communicate(graph, "web", "db") is True

    def test_different_networks_cannot_communicate(self, tmp_path: Path):
        cf = _make_cf(tmp_path, """
services:
  web:
    image: nginx
    networks: [frontend]
  db:
    image: postgres
    networks: [backend]
networks:
  frontend: {}
  backend: {}
""")
        graph = build_network_graph([cf])
        assert can_communicate(graph, "web", "db") is False

    def test_host_mode_both(self, tmp_path: Path):
        cf = _make_cf(tmp_path, """
services:
  web:
    image: nginx
    network_mode: host
  db:
    image: postgres
    network_mode: host
""")
        graph = build_network_graph([cf])
        assert can_communicate(graph, "web", "db") is True

    def test_none_mode_isolated(self, tmp_path: Path):
        cf = _make_cf(tmp_path, """
services:
  web:
    image: nginx
  batch:
    image: worker
    network_mode: none
""")
        graph = build_network_graph([cf])
        assert can_communicate(graph, "web", "batch") is False

    def test_service_mode_shared(self, tmp_path: Path):
        cf = _make_cf(tmp_path, """
services:
  app:
    image: nginx
  sidecar:
    image: envoy
    network_mode: "service:app"
""")
        graph = build_network_graph([cf])
        assert can_communicate(graph, "sidecar", "app") is True

    def test_unknown_service(self, tmp_path: Path):
        cf = _make_cf(tmp_path, "services:\n  web:\n    image: nginx\n")
        graph = build_network_graph([cf])
        assert can_communicate(graph, "web", "nonexistent") is False


# ── CA302: Unreachable Dependency ─────────────────────────────


class TestCA302:
    def test_detects_unreachable_dependency(self, tmp_path: Path):
        cf = _make_cf(tmp_path, """
services:
  app:
    image: myapp
    depends_on: [db]
    networks: [frontend]
  db:
    image: postgres
    networks: [backend]
networks:
  frontend: {}
  backend: {}
""")
        rule = get_rule("CA302")
        issues = rule.check_project([cf])
        assert len(issues) == 1
        assert issues[0].rule_id == "CA302"
        assert "app" in issues[0].message
        assert "db" in issues[0].message

    def test_no_issue_when_reachable(self, tmp_path: Path):
        cf = _make_cf(tmp_path, """
services:
  app:
    image: myapp
    depends_on: [db]
    networks: [shared]
  db:
    image: postgres
    networks: [shared]
networks:
  shared: {}
""")
        rule = get_rule("CA302")
        issues = rule.check_project([cf])
        assert len(issues) == 0

    def test_no_issue_default_bridge(self, tmp_path: Path):
        cf = _make_cf(tmp_path, """
services:
  app:
    image: myapp
    depends_on: [db]
  db:
    image: postgres
""")
        rule = get_rule("CA302")
        issues = rule.check_project([cf])
        assert len(issues) == 0

    def test_detects_none_mode_dependency(self, tmp_path: Path):
        cf = _make_cf(tmp_path, """
services:
  app:
    image: myapp
    depends_on: [db]
    network_mode: none
  db:
    image: postgres
""")
        rule = get_rule("CA302")
        issues = rule.check_project([cf])
        assert len(issues) == 1

    def test_severity_is_error(self):
        rule = get_rule("CA302")
        assert rule.severity == Severity.ERROR


# ── CA303: Isolated Service With Ports ────────────────────────


class TestCA303:
    def test_detects_isolated_with_ports(self, tmp_path: Path):
        cf = _make_cf(tmp_path, """
services:
  batch:
    image: worker
    network_mode: none
    ports:
      - "8080:8080"
""")
        rule = get_rule("CA303")
        issues = rule.check_project([cf])
        assert len(issues) == 1
        assert issues[0].rule_id == "CA303"
        assert "batch" in issues[0].message

    def test_no_issue_isolated_without_ports(self, tmp_path: Path):
        cf = _make_cf(tmp_path, """
services:
  batch:
    image: worker
    network_mode: none
""")
        rule = get_rule("CA303")
        issues = rule.check_project([cf])
        assert len(issues) == 0

    def test_no_issue_normal_service_with_ports(self, tmp_path: Path):
        cf = _make_cf(tmp_path, """
services:
  web:
    image: nginx
    ports:
      - "80:80"
""")
        rule = get_rule("CA303")
        issues = rule.check_project([cf])
        assert len(issues) == 0

    def test_severity_is_warning(self):
        rule = get_rule("CA303")
        assert rule.severity == Severity.WARNING
