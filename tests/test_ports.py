"""Tests for port allocation table command."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from composearr.commands.ports import (
    collect_ports,
    find_conflicts,
    format_ports_csv,
    format_ports_json,
    suggest_available_port,
)
from composearr.models import PortMapping


class TestCollectPorts:
    def test_collects_from_compose(self, tmp_path: Path):
        (tmp_path / "compose.yaml").write_text(
            "services:\n"
            "  web:\n"
            "    image: nginx:1.25\n"
            "    ports:\n"
            '      - "8080:80"\n'
            '      - "8443:443"\n',
            encoding="utf-8",
        )
        ports = collect_ports(tmp_path)
        assert len(ports) == 2
        assert ports[0].host_port == 8080
        assert ports[0].container_port == 80
        assert ports[0].service == "web"

    def test_collects_from_multiple_files(self, tmp_path: Path):
        (tmp_path / "web").mkdir()
        (tmp_path / "web" / "compose.yaml").write_text(
            "services:\n  web:\n    image: nginx:1.25\n    ports:\n      - '8080:80'\n",
            encoding="utf-8",
        )
        (tmp_path / "db").mkdir()
        (tmp_path / "db" / "compose.yaml").write_text(
            "services:\n  db:\n    image: postgres:16\n    ports:\n      - '5432:5432'\n",
            encoding="utf-8",
        )
        ports = collect_ports(tmp_path)
        assert len(ports) == 2

    def test_empty_directory(self, tmp_path: Path):
        ports = collect_ports(tmp_path)
        assert ports == []

    def test_no_ports(self, tmp_path: Path):
        (tmp_path / "compose.yaml").write_text(
            "services:\n  web:\n    image: nginx:1.25\n",
            encoding="utf-8",
        )
        ports = collect_ports(tmp_path)
        assert ports == []


class TestFindConflicts:
    def test_no_conflicts(self):
        ports = [
            PortMapping(8080, 80, service="web"),
            PortMapping(5432, 5432, service="db"),
        ]
        assert find_conflicts(ports) == {}

    def test_detects_conflict(self):
        ports = [
            PortMapping(8080, 80, service="web1"),
            PortMapping(8080, 80, service="web2"),
        ]
        conflicts = find_conflicts(ports)
        assert "8080/tcp" in conflicts
        assert len(conflicts["8080/tcp"]) == 2

    def test_different_protocols_no_conflict(self):
        ports = [
            PortMapping(8080, 80, protocol="tcp", service="web"),
            PortMapping(8080, 80, protocol="udp", service="dns"),
        ]
        assert find_conflicts(ports) == {}


class TestSuggestAvailablePort:
    def test_suggests_next_port(self):
        used = {8080, 8081, 8082}
        assert suggest_available_port(used, 8080) == 8083

    def test_suggests_exact_if_available(self):
        used = {8080}
        assert suggest_available_port(used, 8081) == 8081


class TestPortsJson:
    def test_valid_json(self, tmp_path: Path):
        ports = [
            PortMapping(8080, 80, service="web", file_path=str(tmp_path / "compose.yaml")),
        ]
        result = json.loads(format_ports_json(ports, tmp_path))
        assert result["total_mappings"] == 1
        assert result["conflicts"] == 0
        assert result["ports"][0]["host_port"] == 8080

    def test_marks_conflicts(self, tmp_path: Path):
        ports = [
            PortMapping(8080, 80, service="web1", file_path=str(tmp_path / "a.yaml")),
            PortMapping(8080, 80, service="web2", file_path=str(tmp_path / "b.yaml")),
        ]
        result = json.loads(format_ports_json(ports, tmp_path))
        assert result["conflicts"] == 1
        assert result["ports"][0]["conflict"] is True


class TestPortsCsv:
    def test_valid_csv(self, tmp_path: Path):
        ports = [
            PortMapping(8080, 80, service="web", file_path=str(tmp_path / "compose.yaml")),
        ]
        csv_output = format_ports_csv(ports, tmp_path)
        assert "host_port" in csv_output  # Header
        assert "8080" in csv_output
        assert "web" in csv_output


class TestPortsCLI:
    def test_ports_command(self, tmp_path: Path):
        from typer.testing import CliRunner
        from composearr.cli import app

        (tmp_path / "compose.yaml").write_text(
            "services:\n  web:\n    image: nginx:1.25\n    ports:\n      - '8080:80'\n",
            encoding="utf-8",
        )
        runner = CliRunner()
        result = runner.invoke(app, ["ports", str(tmp_path)])
        assert result.exit_code == 0
        assert "8080" in result.output

    def test_ports_json(self, tmp_path: Path):
        from typer.testing import CliRunner
        from composearr.cli import app

        (tmp_path / "compose.yaml").write_text(
            "services:\n  web:\n    image: nginx:1.25\n    ports:\n      - '8080:80'\n",
            encoding="utf-8",
        )
        runner = CliRunner()
        result = runner.invoke(app, ["ports", str(tmp_path), "--format", "json"])
        parsed = json.loads(result.output)
        assert parsed["total_mappings"] == 1
