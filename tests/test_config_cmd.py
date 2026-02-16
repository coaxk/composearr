"""Tests for config validation command."""

from __future__ import annotations

from pathlib import Path

from composearr.commands.config_cmd import validate_config_data


class TestValidateConfigData:
    def test_valid_config(self):
        data = {
            "rules": {"CA001": "warning", "no-inline-secrets": "error"},
            "ignore": {"files": ["**/test/**"], "services": ["debug"]},
        }
        issues = validate_config_data(data)
        assert issues == []

    def test_unknown_top_key(self):
        data = {"rules": {}, "banana": True}
        issues = validate_config_data(data)
        assert any("Unknown top-level key" in i for i in issues)

    def test_unknown_rule(self):
        data = {"rules": {"FAKE_RULE": "warning"}}
        issues = validate_config_data(data)
        assert any("Unknown rule" in i for i in issues)

    def test_invalid_severity(self):
        data = {"rules": {"CA001": "critical"}}
        issues = validate_config_data(data)
        assert any("Invalid severity" in i for i in issues)

    def test_valid_severity_off(self):
        data = {"rules": {"CA001": "off"}}
        issues = validate_config_data(data)
        assert issues == []

    def test_ignore_list_format(self):
        data = {"ignore": ["**/test/**"]}
        issues = validate_config_data(data)
        assert issues == []

    def test_ignore_invalid_type(self):
        data = {"ignore": "not_a_list"}
        issues = validate_config_data(data)
        assert any("must be a list" in i for i in issues)

    def test_trusted_registries_valid(self):
        data = {"trusted_registries": ["myregistry.example.com"]}
        issues = validate_config_data(data)
        assert issues == []

    def test_trusted_registries_invalid_type(self):
        data = {"trusted_registries": "not_a_list"}
        issues = validate_config_data(data)
        assert any("must be a list" in i for i in issues)

    def test_defaults_valid(self):
        data = {"defaults": {"severity": "warning", "group_by": "rule", "format": "json"}}
        issues = validate_config_data(data)
        assert issues == []

    def test_defaults_invalid_severity(self):
        data = {"defaults": {"severity": "banana"}}
        issues = validate_config_data(data)
        assert any("Invalid default severity" in i for i in issues)

    def test_defaults_invalid_group_by(self):
        data = {"defaults": {"group_by": "banana"}}
        issues = validate_config_data(data)
        assert any("Invalid default group_by" in i for i in issues)

    def test_empty_config(self):
        issues = validate_config_data({})
        assert issues == []

    def test_rules_by_name(self):
        data = {"rules": {"no-latest-tag": "error"}}
        issues = validate_config_data(data)
        assert issues == []


class TestConfigCLI:
    def test_config_command_defaults(self):
        from typer.testing import CliRunner
        from composearr.cli import app

        runner = CliRunner()
        result = runner.invoke(app, ["config"])
        assert result.exit_code == 0

    def test_config_validate_with_path(self, tmp_path: Path):
        from typer.testing import CliRunner
        from composearr.cli import app

        runner = CliRunner()
        result = runner.invoke(app, ["config", str(tmp_path)])
        assert result.exit_code == 0

    def test_config_validate_bad_config(self, tmp_path: Path):
        from typer.testing import CliRunner
        from composearr.cli import app

        (tmp_path / ".composearr.yml").write_text("rules:\n  FAKE_RULE: warning\n", encoding="utf-8")
        runner = CliRunner()
        result = runner.invoke(app, ["config", str(tmp_path)])
        assert result.exit_code == 1
