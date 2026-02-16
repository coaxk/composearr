"""Tests for CLI commands."""

from __future__ import annotations

from pathlib import Path

import pytest
from typer.testing import CliRunner

from composearr.cli import app

runner = CliRunner()


class TestAuditCommand:
    def test_clean_file_exits_0(self, tmp_path: Path):
        (tmp_path / "compose.yaml").write_text(
            "services:\n  web:\n    image: nginx:1.21\n    restart: unless-stopped\n"
            "    environment:\n      TZ: UTC\n"
            "    healthcheck:\n      test: curl -f http://localhost\n      interval: 30s\n",
            encoding="utf-8",
        )
        result = runner.invoke(app, ["audit", str(tmp_path)])
        assert result.exit_code == 0

    def test_errors_exit_1(self, tmp_path: Path):
        (tmp_path / "compose.yaml").write_text(
            "services:\n  app:\n    image: nginx:1.21\n"
            "    environment:\n      DB_PASSWORD: SuperSecretP@ssw0rd123!\n",
            encoding="utf-8",
        )
        result = runner.invoke(app, ["audit", str(tmp_path)])
        assert result.exit_code == 1

    def test_nonexistent_path_exits_2(self):
        result = runner.invoke(app, ["audit", "/nonexistent/path/xyz"])
        assert result.exit_code == 2

    def test_severity_filter(self, tmp_path: Path):
        (tmp_path / "compose.yaml").write_text(
            "services:\n  web:\n    image: nginx:latest\n",
            encoding="utf-8",
        )
        result = runner.invoke(app, ["audit", str(tmp_path), "--severity", "error"])
        assert result.exit_code == 0  # No errors (CA001 is warning)

    def test_rule_filter(self, tmp_path: Path):
        (tmp_path / "compose.yaml").write_text(
            "services:\n  web:\n    image: nginx:latest\n",
            encoding="utf-8",
        )
        result = runner.invoke(app, ["audit", str(tmp_path), "--rule", "CA001", "--severity", "warning"])
        assert "CA001" in result.output

    def test_ignore_rule(self, tmp_path: Path):
        (tmp_path / "compose.yaml").write_text(
            "services:\n  web:\n    image: nginx:latest\n",
            encoding="utf-8",
        )
        result = runner.invoke(app, ["audit", str(tmp_path), "--ignore", "CA001,CA201,CA203,CA403", "--severity", "warning"])
        assert "CA001" not in result.output

    def test_group_by_file(self, tmp_path: Path):
        (tmp_path / "compose.yaml").write_text(
            "services:\n  web:\n    image: nginx:latest\n",
            encoding="utf-8",
        )
        result = runner.invoke(app, ["audit", str(tmp_path), "--group-by", "file", "--severity", "warning"])
        assert result.exit_code == 0

    def test_group_by_rule(self, tmp_path: Path):
        (tmp_path / "compose.yaml").write_text(
            "services:\n  web:\n    image: nginx:latest\n",
            encoding="utf-8",
        )
        result = runner.invoke(app, ["audit", str(tmp_path), "--group-by", "rule", "--severity", "warning"])
        assert result.exit_code == 0

    def test_empty_directory(self, tmp_path: Path):
        result = runner.invoke(app, ["audit", str(tmp_path)])
        assert result.exit_code == 0


class TestRulesCommand:
    def test_lists_rules(self):
        result = runner.invoke(app, ["rules"])
        assert result.exit_code == 0
        assert "CA001" in result.output
        assert "no-latest-tag" in result.output

    def test_lists_all_rules(self):
        result = runner.invoke(app, ["rules"])
        for rule_id in ["CA001", "CA003", "CA101", "CA201", "CA202", "CA203", "CA301", "CA302", "CA303", "CA401", "CA402", "CA403", "CA601"]:
            assert rule_id in result.output


class TestVersionFlag:
    def test_version(self):
        result = runner.invoke(app, ["--version"])
        assert result.exit_code == 0
        assert "composearr" in result.output
