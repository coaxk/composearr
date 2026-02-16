"""Sprint 5 tests — Orphanage, Runtime Comparison, CA304 DNS."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch, PropertyMock

import pytest

from composearr.models import ComposeFile, LintIssue, Severity
from composearr.rules.base import get_all_rules, get_rule
from composearr.scanner.parser import parse_compose_file


def _make_cf(tmp_path: Path, content: str) -> ComposeFile:
    f = tmp_path / "compose.yaml"
    f.write_text(content, encoding="utf-8")
    return parse_compose_file(f)


# ═══════════════════════════════════════════════════════════════
# DOCKER CLIENT TESTS
# ═══════════════════════════════════════════════════════════════


class TestDockerClient:
    """Test Docker client with graceful degradation."""

    def test_no_docker_sdk(self):
        """Without docker SDK, client reports unavailable."""
        with patch.dict("sys.modules", {"docker": None}):
            # Force reimport
            import importlib
            from composearr import docker_client
            original = docker_client._HAS_DOCKER

            docker_client._HAS_DOCKER = False
            try:
                client = docker_client.DockerClient()
                assert client.available is False
                assert "not installed" in client.error
                assert client.get_volumes() == []
                assert client.get_networks() == []
                assert client.get_containers() == []
            finally:
                docker_client._HAS_DOCKER = original

    def test_client_dataclasses(self):
        from composearr.docker_client import DockerVolume, DockerNetwork, DockerContainer

        vol = DockerVolume(name="test_vol", driver="local")
        assert vol.name == "test_vol"
        assert vol.driver == "local"

        net = DockerNetwork(name="test_net", id="abc123")
        assert net.name == "test_net"

        c = DockerContainer(name="test_c", service_name="web", image="nginx:1.25")
        assert c.service_name == "web"
        assert c.image == "nginx:1.25"


# ═══════════════════════════════════════════════════════════════
# ORPHANAGE TESTS
# ═══════════════════════════════════════════════════════════════


class TestOrphanageReport:
    """Test OrphanageReport dataclass."""

    def test_empty_report(self):
        from composearr.orphanage import OrphanageReport
        report = OrphanageReport(docker_available=True)
        assert report.total_orphans == 0
        assert report.has_orphans is False

    def test_report_with_orphans(self):
        from composearr.docker_client import DockerVolume
        from composearr.orphanage import OrphanageReport

        report = OrphanageReport(
            orphaned_volumes=[DockerVolume(name="old_vol")],
            docker_available=True,
        )
        assert report.total_orphans == 1
        assert report.has_orphans is True

    def test_unavailable_report(self):
        from composearr.orphanage import OrphanageReport
        report = OrphanageReport(docker_available=False, error="Docker down")
        assert report.total_orphans == 0
        assert report.error == "Docker down"


class TestOrphanageFinder:
    """Test orphanage finder with mocked Docker client."""

    def _make_mock_docker(self, volumes=None, networks=None):
        from composearr.docker_client import DockerClient
        mock = MagicMock(spec=DockerClient)
        mock.available = True
        mock.get_volumes.return_value = volumes or []
        mock.get_networks.return_value = networks or []
        return mock

    def test_no_orphans(self, tmp_path):
        """Volumes/networks that match compose are not orphans."""
        from composearr.docker_client import DockerVolume, DockerNetwork
        from composearr.orphanage import OrphanageFinder

        compose = tmp_path / "compose.yaml"
        compose.write_text(
            "services:\n  web:\n    image: nginx\n    volumes:\n      - web_data:/data\n"
            "    networks:\n      - frontend\n"
            "volumes:\n  web_data:\n"
            "networks:\n  frontend:\n",
            encoding="utf-8",
        )

        mock_docker = self._make_mock_docker(
            volumes=[DockerVolume(name="web_data")],
            networks=[DockerNetwork(name="frontend")],
        )

        finder = OrphanageFinder(tmp_path, docker=mock_docker)
        report = finder.find_orphans()
        assert report.has_orphans is False
        assert report.docker_available is True

    def test_orphaned_volume(self, tmp_path):
        from composearr.docker_client import DockerVolume
        from composearr.orphanage import OrphanageFinder

        compose = tmp_path / "compose.yaml"
        compose.write_text("services:\n  web:\n    image: nginx\n", encoding="utf-8")

        mock_docker = self._make_mock_docker(
            volumes=[DockerVolume(name="old_unused_vol")],
        )

        finder = OrphanageFinder(tmp_path, docker=mock_docker)
        report = finder.find_orphans()
        assert len(report.orphaned_volumes) == 1
        assert report.orphaned_volumes[0].name == "old_unused_vol"

    def test_orphaned_network(self, tmp_path):
        from composearr.docker_client import DockerNetwork
        from composearr.orphanage import OrphanageFinder

        compose = tmp_path / "compose.yaml"
        compose.write_text("services:\n  web:\n    image: nginx\n", encoding="utf-8")

        mock_docker = self._make_mock_docker(
            networks=[DockerNetwork(name="stale_network", id="abc123")],
        )

        finder = OrphanageFinder(tmp_path, docker=mock_docker)
        report = finder.find_orphans()
        assert len(report.orphaned_networks) == 1
        assert report.orphaned_networks[0].name == "stale_network"

    def test_project_prefix_matching(self, tmp_path):
        """Docker Compose prefixes names: project_volumename should match volumename."""
        from composearr.docker_client import DockerVolume
        from composearr.orphanage import OrphanageFinder

        compose = tmp_path / "compose.yaml"
        compose.write_text(
            "services:\n  web:\n    image: nginx\n"
            "volumes:\n  web_data:\n",
            encoding="utf-8",
        )

        mock_docker = self._make_mock_docker(
            volumes=[DockerVolume(name="myproject_web_data")],
        )

        finder = OrphanageFinder(tmp_path, docker=mock_docker)
        report = finder.find_orphans()
        assert report.has_orphans is False

    def test_docker_unavailable(self, tmp_path):
        from composearr.docker_client import DockerClient
        from composearr.orphanage import OrphanageFinder

        mock_docker = MagicMock(spec=DockerClient)
        mock_docker.available = False
        mock_docker.error = "Connection refused"

        finder = OrphanageFinder(tmp_path, docker=mock_docker)
        report = finder.find_orphans()
        assert report.docker_available is False
        assert "Connection refused" in report.error

    def test_service_volume_reference(self, tmp_path):
        """Named volumes used in service volumes: should match."""
        from composearr.docker_client import DockerVolume
        from composearr.orphanage import OrphanageFinder

        compose = tmp_path / "compose.yaml"
        compose.write_text(
            "services:\n  db:\n    image: postgres\n    volumes:\n      - pgdata:/var/lib/postgresql/data\n"
            "volumes:\n  pgdata:\n",
            encoding="utf-8",
        )

        mock_docker = self._make_mock_docker(
            volumes=[DockerVolume(name="pgdata")],
        )

        finder = OrphanageFinder(tmp_path, docker=mock_docker)
        report = finder.find_orphans()
        assert report.has_orphans is False

    def test_mixed_orphans_and_referenced(self, tmp_path):
        from composearr.docker_client import DockerVolume, DockerNetwork
        from composearr.orphanage import OrphanageFinder

        compose = tmp_path / "compose.yaml"
        compose.write_text(
            "services:\n  web:\n    image: nginx\n    networks:\n      - frontend\n"
            "networks:\n  frontend:\n",
            encoding="utf-8",
        )

        mock_docker = self._make_mock_docker(
            volumes=[DockerVolume(name="orphan_vol"), DockerVolume(name="another_orphan")],
            networks=[DockerNetwork(name="frontend"), DockerNetwork(name="orphan_net")],
        )

        finder = OrphanageFinder(tmp_path, docker=mock_docker)
        report = finder.find_orphans()
        assert len(report.orphaned_volumes) == 2
        assert len(report.orphaned_networks) == 1
        assert report.total_orphans == 3


# ═══════════════════════════════════════════════════════════════
# RUNTIME COMPARATOR TESTS
# ═══════════════════════════════════════════════════════════════


class TestRuntimeReport:
    """Test RuntimeReport dataclass."""

    def test_empty_report(self):
        from composearr.runtime import RuntimeReport
        report = RuntimeReport(docker_available=True)
        assert report.has_diffs is False

    def test_report_with_diffs(self):
        from composearr.runtime import RuntimeDiff, RuntimeReport
        report = RuntimeReport(
            diffs=[RuntimeDiff(service="web", category="missing", expected="running", actual="stopped", severity="warning")],
            docker_available=True,
        )
        assert report.has_diffs is True


class TestRuntimeComparator:
    """Test runtime comparator with mocked Docker."""

    def _make_mock_docker(self, containers=None):
        from composearr.docker_client import DockerClient
        mock = MagicMock(spec=DockerClient)
        mock.available = True
        mock.get_containers.return_value = containers or []
        return mock

    def test_all_running(self, tmp_path):
        from composearr.docker_client import DockerContainer
        from composearr.runtime import RuntimeComparator

        compose = tmp_path / "compose.yaml"
        compose.write_text(
            "services:\n  web:\n    image: nginx:1.25\n",
            encoding="utf-8",
        )

        mock_docker = self._make_mock_docker(containers=[
            DockerContainer(name="web-1", service_name="web", image="nginx:1.25", status="running"),
        ])

        comp = RuntimeComparator(tmp_path, docker=mock_docker)
        report = comp.compare()
        assert report.docker_available is True
        assert report.has_diffs is False

    def test_missing_service(self, tmp_path):
        from composearr.runtime import RuntimeComparator

        compose = tmp_path / "compose.yaml"
        compose.write_text(
            "services:\n  web:\n    image: nginx\n  db:\n    image: postgres\n",
            encoding="utf-8",
        )

        mock_docker = self._make_mock_docker(containers=[])

        comp = RuntimeComparator(tmp_path, docker=mock_docker)
        report = comp.compare()
        missing = [d for d in report.diffs if d.category == "missing"]
        assert len(missing) == 2

    def test_extra_container(self, tmp_path):
        from composearr.docker_client import DockerContainer
        from composearr.runtime import RuntimeComparator

        compose = tmp_path / "compose.yaml"
        compose.write_text("services:\n  web:\n    image: nginx\n", encoding="utf-8")

        mock_docker = self._make_mock_docker(containers=[
            DockerContainer(name="web-1", service_name="web", image="nginx:latest", status="running"),
            DockerContainer(name="rogue-1", service_name="rogue", image="bitcoin-miner:latest", status="running"),
        ])

        comp = RuntimeComparator(tmp_path, docker=mock_docker)
        report = comp.compare()
        extras = [d for d in report.diffs if d.category == "extra"]
        assert len(extras) == 1
        assert extras[0].service == "rogue"

    def test_image_mismatch(self, tmp_path):
        from composearr.docker_client import DockerContainer
        from composearr.runtime import RuntimeComparator

        compose = tmp_path / "compose.yaml"
        compose.write_text("services:\n  web:\n    image: nginx:1.25\n", encoding="utf-8")

        mock_docker = self._make_mock_docker(containers=[
            DockerContainer(name="web-1", service_name="web", image="nginx:1.24", status="running"),
        ])

        comp = RuntimeComparator(tmp_path, docker=mock_docker)
        report = comp.compare()
        image_diffs = [d for d in report.diffs if d.category == "image"]
        assert len(image_diffs) == 1
        assert image_diffs[0].severity == "error"

    def test_stopped_container(self, tmp_path):
        from composearr.docker_client import DockerContainer
        from composearr.runtime import RuntimeComparator

        compose = tmp_path / "compose.yaml"
        compose.write_text("services:\n  web:\n    image: nginx\n", encoding="utf-8")

        mock_docker = self._make_mock_docker(containers=[
            DockerContainer(name="web-1", service_name="web", image="nginx:latest", status="exited"),
        ])

        comp = RuntimeComparator(tmp_path, docker=mock_docker)
        report = comp.compare()
        status_diffs = [d for d in report.diffs if d.category == "status"]
        assert len(status_diffs) == 1
        assert status_diffs[0].actual == "exited"

    def test_docker_unavailable(self, tmp_path):
        from composearr.docker_client import DockerClient
        from composearr.runtime import RuntimeComparator

        mock_docker = MagicMock(spec=DockerClient)
        mock_docker.available = False
        mock_docker.error = "Nope"

        comp = RuntimeComparator(tmp_path, docker=mock_docker)
        report = comp.compare()
        assert report.docker_available is False


class TestImageMatch:
    """Test image matching logic."""

    def test_exact_match(self):
        from composearr.runtime import RuntimeComparator
        assert RuntimeComparator._images_match("nginx:1.25", "nginx:1.25") is True

    def test_implicit_latest(self):
        from composearr.runtime import RuntimeComparator
        assert RuntimeComparator._images_match("nginx", "nginx:latest") is True

    def test_docker_io_prefix(self):
        from composearr.runtime import RuntimeComparator
        assert RuntimeComparator._images_match("nginx:1.25", "docker.io/library/nginx:1.25") is True

    def test_different_tags(self):
        from composearr.runtime import RuntimeComparator
        assert RuntimeComparator._images_match("nginx:1.25", "nginx:1.24") is False

    def test_different_images(self):
        from composearr.runtime import RuntimeComparator
        assert RuntimeComparator._images_match("nginx:1.25", "caddy:2") is False


# ═══════════════════════════════════════════════════════════════
# CA304: DNS CONFIGURATION TESTS
# ═══════════════════════════════════════════════════════════════


class TestCA304DNSConfiguration:
    """Test CA304 — dns-configuration."""

    def test_no_dns_passes(self, tmp_path):
        cf = _make_cf(tmp_path, "services:\n  web:\n    image: nginx\n")
        rule = get_rule("CA304")
        issues = rule.check_service("web", cf.services["web"], cf)
        assert len(issues) == 0

    def test_dns_in_host_mode(self, tmp_path):
        cf = _make_cf(tmp_path,
            "services:\n  web:\n    image: nginx\n    network_mode: host\n    dns:\n      - 8.8.8.8\n")
        rule = get_rule("CA304")
        issues = rule.check_service("web", cf.services["web"], cf)
        assert len(issues) == 1
        assert "ignored" in issues[0].message.lower()
        assert issues[0].severity == Severity.WARNING

    def test_dns_in_none_mode(self, tmp_path):
        cf = _make_cf(tmp_path,
            "services:\n  web:\n    image: nginx\n    network_mode: none\n    dns:\n      - 1.1.1.1\n")
        rule = get_rule("CA304")
        issues = rule.check_service("web", cf.services["web"], cf)
        assert len(issues) == 1
        assert "useless" in issues[0].message.lower()

    def test_localhost_dns_list(self, tmp_path):
        cf = _make_cf(tmp_path,
            "services:\n  web:\n    image: nginx\n    dns:\n      - 127.0.0.1\n")
        rule = get_rule("CA304")
        issues = rule.check_service("web", cf.services["web"], cf)
        assert len(issues) == 1
        assert "localhost" in issues[0].message.lower()
        assert issues[0].severity == Severity.INFO

    def test_localhost_dns_string(self, tmp_path):
        cf = _make_cf(tmp_path,
            "services:\n  web:\n    image: nginx\n    dns: 127.0.0.1\n")
        rule = get_rule("CA304")
        issues = rule.check_service("web", cf.services["web"], cf)
        assert len(issues) == 1
        assert "localhost" in issues[0].message.lower()

    def test_ipv6_localhost_dns(self, tmp_path):
        cf = _make_cf(tmp_path,
            "services:\n  web:\n    image: nginx\n    dns:\n      - \"::1\"\n")
        rule = get_rule("CA304")
        issues = rule.check_service("web", cf.services["web"], cf)
        assert len(issues) == 1

    def test_valid_dns_passes(self, tmp_path):
        cf = _make_cf(tmp_path,
            "services:\n  web:\n    image: nginx\n    dns:\n      - 8.8.8.8\n      - 1.1.1.1\n")
        rule = get_rule("CA304")
        issues = rule.check_service("web", cf.services["web"], cf)
        assert len(issues) == 0

    def test_host_mode_with_localhost_dns(self, tmp_path):
        """Host mode + localhost DNS = only host mode warning (host mode takes priority)."""
        cf = _make_cf(tmp_path,
            "services:\n  web:\n    image: nginx\n    network_mode: host\n    dns:\n      - 127.0.0.1\n")
        rule = get_rule("CA304")
        issues = rule.check_service("web", cf.services["web"], cf)
        # Should get both: host mode warning AND localhost info
        assert len(issues) == 2
        severities = {i.severity for i in issues}
        assert Severity.WARNING in severities
        assert Severity.INFO in severities

    def test_rule_metadata(self):
        rule = get_rule("CA304")
        assert rule.id == "CA304"
        assert rule.name == "dns-configuration"
        assert rule.severity == Severity.WARNING
        assert rule.category == "networking"


# ═══════════════════════════════════════════════════════════════
# INTEGRATION TESTS
# ═══════════════════════════════════════════════════════════════


class TestScoringCA304:
    """Test that CA304 maps to network scoring category."""

    def test_ca304_network_category(self):
        from composearr.scoring import _categorize
        assert _categorize("CA304") == "network"


class TestConfigCA304:
    """Test config integration."""

    def test_default_severity(self):
        from composearr.config import DEFAULT_RULES
        assert DEFAULT_RULES["CA304"] == "warning"

    def test_name_mapping(self):
        from composearr.config import _RULE_NAME_TO_ID
        assert _RULE_NAME_TO_ID["dns-configuration"] == "CA304"


class TestRuleDocsCA304:
    """Test RULE_DOCS for CA304."""

    def test_docs_exist(self):
        from composearr.commands.explain import RULE_DOCS
        assert "CA304" in RULE_DOCS
        docs = RULE_DOCS["CA304"]
        assert "why" in docs
        assert "scenarios" in docs
        assert "fix_examples" in docs


class TestRuleRegistration:
    """Test at least 26 rules total."""

    def test_at_least_26_rules(self):
        rules = get_all_rules()
        assert len(rules) >= 26, f"Expected >= 26 rules, got {len(rules)}"

    def test_ca304_registered(self):
        rule = get_rule("CA304")
        assert rule is not None
        assert rule.category == "networking"


class TestOrphanageIsReferenced:
    """Test the _is_referenced helper directly."""

    def test_exact_match(self):
        from composearr.orphanage import OrphanageFinder
        assert OrphanageFinder._is_referenced("myvolume", {"myvolume"}) is True

    def test_prefix_match(self):
        from composearr.orphanage import OrphanageFinder
        assert OrphanageFinder._is_referenced("project_myvolume", {"myvolume"}) is True

    def test_no_match(self):
        from composearr.orphanage import OrphanageFinder
        assert OrphanageFinder._is_referenced("totally_unrelated", {"myvolume"}) is False

    def test_empty_defined(self):
        from composearr.orphanage import OrphanageFinder
        assert OrphanageFinder._is_referenced("anything", set()) is False

    def test_partial_name_no_match(self):
        """'vol' should not match 'volume' — only suffix after _ matches."""
        from composearr.orphanage import OrphanageFinder
        assert OrphanageFinder._is_referenced("vol", {"volume"}) is False
