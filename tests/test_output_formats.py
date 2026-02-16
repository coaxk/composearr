"""Tests for production output formats."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from composearr.cli import app
from composearr.formatters.json_formatter import format_json
from composearr.formatters.github_formatter import format_github
from composearr.formatters.sarif_formatter import format_sarif
from composearr.models import FormatOptions, LintIssue, ScanResult, Severity

runner = CliRunner()


def _make_result() -> ScanResult:
    result = ScanResult()
    result.issues = [
        LintIssue(
            rule_id="CA001",
            rule_name="no-latest-tag",
            severity=Severity.WARNING,
            message="Image uses :latest tag",
            file_path="sonarr/compose.yaml",
            line=3,
            service="sonarr",
            suggested_fix="Pin to a specific version",
        ),
        LintIssue(
            rule_id="CA101",
            rule_name="no-inline-secrets",
            severity=Severity.ERROR,
            message="DB_PASSWORD contains secret value inline",
            file_path="myapp/compose.yaml",
            line=5,
            service="myapp",
            fix_available=True,
            suggested_fix="Move to .env and reference as ${DB_PASSWORD}",
        ),
    ]
    return result


class TestJsonFormat:
    def test_valid_json(self):
        result = _make_result()
        output = format_json(result, "/test")
        parsed = json.loads(output)
        assert parsed["version"] == "1.0"

    def test_has_summary(self):
        result = _make_result()
        output = format_json(result, "/test")
        parsed = json.loads(output)
        assert parsed["summary"]["errors"] == 1
        assert parsed["summary"]["warnings"] == 1

    def test_has_issues(self):
        result = _make_result()
        output = format_json(result, "/test")
        parsed = json.loads(output)
        assert len(parsed["issues"]) == 2
        assert parsed["issues"][0]["rule_id"] == "CA001"

    def test_includes_line_and_service(self):
        result = _make_result()
        output = format_json(result, "/test")
        parsed = json.loads(output)
        assert parsed["issues"][0]["line"] == 3
        assert parsed["issues"][0]["service"] == "sonarr"

    def test_empty_result(self):
        result = ScanResult()
        output = format_json(result, "/test")
        parsed = json.loads(output)
        assert parsed["issues"] == []
        assert parsed["summary"]["errors"] == 0

    def test_skipped_managed_included(self):
        result = ScanResult()
        result.skipped_managed = {"Komodo": 35}
        output = format_json(result, "/test")
        parsed = json.loads(output)
        assert parsed["skipped_managed"]["Komodo"] == 35


class TestGithubFormat:
    def test_annotation_format(self):
        result = _make_result()
        output = format_github(result, "/test")
        assert "::warning file=sonarr/compose.yaml,line=3::" in output
        assert "::error file=myapp/compose.yaml,line=5::" in output

    def test_includes_rule_id(self):
        result = _make_result()
        output = format_github(result, "/test")
        assert "CA001:" in output
        assert "CA101:" in output

    def test_empty_result(self):
        result = ScanResult()
        output = format_github(result, "/test")
        assert output == ""

    def test_escapes_double_colon(self):
        result = ScanResult()
        result.issues = [
            LintIssue(
                rule_id="CA302",
                rule_name="unreachable-dependency",
                severity=Severity.ERROR,
                message="'app' declares depends_on::db but cannot reach it",
                file_path="app/compose.yaml",
                line=5,
            ),
        ]
        output = format_github(result, "/test")
        # :: in message must be escaped to prevent annotation injection
        assert "depends_on: :db" in output
        assert "depends_on::db" not in output

    def test_escapes_newlines(self):
        result = ScanResult()
        result.issues = [
            LintIssue(
                rule_id="CA401",
                rule_name="puid-pgid-mismatch",
                severity=Severity.ERROR,
                message="PUID mismatch:\n  line1\n  line2",
                file_path="app/compose.yaml",
            ),
        ]
        output = format_github(result, "/test")
        assert "\n  line1" not in output
        assert "%0A" in output


class TestSarifFormat:
    def test_valid_sarif(self):
        result = _make_result()
        output = format_sarif(result, "/test")
        parsed = json.loads(output)
        assert parsed["version"] == "2.1.0"
        assert "$schema" in parsed

    def test_has_tool_info(self):
        result = _make_result()
        output = format_sarif(result, "/test")
        parsed = json.loads(output)
        driver = parsed["runs"][0]["tool"]["driver"]
        assert driver["name"] == "composearr"
        assert "rules" in driver

    def test_has_results(self):
        result = _make_result()
        output = format_sarif(result, "/test")
        parsed = json.loads(output)
        results = parsed["runs"][0]["results"]
        assert len(results) == 2

    def test_result_has_location(self):
        result = _make_result()
        output = format_sarif(result, "/test")
        parsed = json.loads(output)
        loc = parsed["runs"][0]["results"][0]["locations"][0]["physicalLocation"]
        assert "artifactLocation" in loc
        assert "region" in loc

    def test_result_has_fix(self):
        result = _make_result()
        output = format_sarif(result, "/test")
        parsed = json.loads(output)
        # Second issue (CA101) has a suggested fix
        fixes = parsed["runs"][0]["results"][1].get("fixes", [])
        assert len(fixes) == 1

    def test_rules_include_all_10(self):
        result = ScanResult()
        output = format_sarif(result, "/test")
        parsed = json.loads(output)
        rule_ids = [r["id"] for r in parsed["runs"][0]["tool"]["driver"]["rules"]]
        for expected in ["CA001", "CA101", "CA201", "CA202", "CA203", "CA301", "CA401", "CA402", "CA403", "CA601"]:
            assert expected in rule_ids


class TestCLIFormatFlag:
    def test_json_flag(self, tmp_path: Path):
        (tmp_path / "compose.yaml").write_text(
            "services:\n  web:\n    image: nginx:latest\n",
            encoding="utf-8",
        )
        result = runner.invoke(app, ["audit", str(tmp_path), "--format", "json"])
        parsed = json.loads(result.output)
        assert "issues" in parsed

    def test_github_flag(self, tmp_path: Path):
        (tmp_path / "compose.yaml").write_text(
            "services:\n  web:\n    image: nginx:latest\n",
            encoding="utf-8",
        )
        result = runner.invoke(app, ["audit", str(tmp_path), "--format", "github"])
        assert "::" in result.output or result.output.strip() == ""

    def test_sarif_flag(self, tmp_path: Path):
        (tmp_path / "compose.yaml").write_text(
            "services:\n  web:\n    image: nginx:latest\n",
            encoding="utf-8",
        )
        result = runner.invoke(app, ["audit", str(tmp_path), "--format", "sarif"])
        parsed = json.loads(result.output)
        assert parsed["version"] == "2.1.0"
