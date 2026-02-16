"""Tests for the fixer module — apply_fixes with backup and rollback."""

from __future__ import annotations

from pathlib import Path

import pytest

from composearr.fixer import apply_fixes, FixResult, verify_yaml_file
from composearr.models import LintIssue, Severity


def _make_issue(file_path: str, rule_id: str = "CA203", service: str = "web") -> LintIssue:
    return LintIssue(
        rule_id=rule_id,
        rule_name="require-restart-policy",
        severity=Severity.WARNING,
        message="No restart policy",
        file_path=file_path,
        service=service,
        fix_available=True,
        suggested_fix="Add restart: unless-stopped",
    )


class TestFixResult:
    def test_fix_result_defaults(self):
        r = FixResult()
        assert r.applied == 0
        assert r.skipped == 0
        assert r.errors == 0
        assert r.backup_paths == []
        assert r.verified_files == []
        assert r.verification_errors == []


class TestApplyFixes:
    def test_creates_backup(self, tmp_path: Path):
        compose = tmp_path / "compose.yaml"
        compose.write_text("services:\n  web:\n    image: nginx\n", encoding="utf-8")

        issue = _make_issue(str(compose))
        result = apply_fixes([issue], tmp_path, backup=True)

        assert result.applied == 1
        assert len(result.backup_paths) == 1
        assert result.backup_paths[0].exists()
        assert result.backup_paths[0].name == "compose.yaml.bak"

    def test_backup_contains_original_content(self, tmp_path: Path):
        original = "services:\n  web:\n    image: nginx\n"
        compose = tmp_path / "compose.yaml"
        compose.write_text(original, encoding="utf-8")

        issue = _make_issue(str(compose))
        result = apply_fixes([issue], tmp_path, backup=True)

        bak_content = result.backup_paths[0].read_text(encoding="utf-8")
        assert bak_content == original

    def test_no_backup_when_disabled(self, tmp_path: Path):
        compose = tmp_path / "compose.yaml"
        compose.write_text("services:\n  web:\n    image: nginx\n", encoding="utf-8")

        issue = _make_issue(str(compose))
        result = apply_fixes([issue], tmp_path, backup=False)

        assert result.applied == 1
        assert result.backup_paths == []
        assert not (tmp_path / "compose.yaml.bak").exists()

    def test_fix_adds_restart_policy(self, tmp_path: Path):
        compose = tmp_path / "compose.yaml"
        compose.write_text("services:\n  web:\n    image: nginx\n", encoding="utf-8")

        issue = _make_issue(str(compose))
        apply_fixes([issue], tmp_path, backup=False)

        content = compose.read_text(encoding="utf-8")
        assert "restart" in content
        assert "unless-stopped" in content

    def test_rollback_from_backup(self, tmp_path: Path):
        """Verify backup can be used to roll back changes."""
        original = "services:\n  web:\n    image: nginx\n"
        compose = tmp_path / "compose.yaml"
        compose.write_text(original, encoding="utf-8")

        issue = _make_issue(str(compose))
        result = apply_fixes([issue], tmp_path, backup=True)

        # File was modified
        modified = compose.read_text(encoding="utf-8")
        assert "restart" in modified

        # Roll back by copying backup over original
        import shutil
        bak = result.backup_paths[0]
        shutil.copy2(bak, compose)

        restored = compose.read_text(encoding="utf-8")
        assert restored == original
        assert "restart" not in restored

    def test_missing_file_counts_as_error(self, tmp_path: Path):
        issue = _make_issue(str(tmp_path / "nonexistent.yaml"))
        result = apply_fixes([issue], tmp_path, backup=True)
        assert result.errors == 1
        assert result.applied == 0

    def test_multiple_files_multiple_backups(self, tmp_path: Path):
        f1 = tmp_path / "a" / "compose.yaml"
        f1.parent.mkdir()
        f1.write_text("services:\n  web:\n    image: nginx\n", encoding="utf-8")

        f2 = tmp_path / "b" / "compose.yaml"
        f2.parent.mkdir()
        f2.write_text("services:\n  db:\n    image: postgres\n", encoding="utf-8")

        issues = [
            _make_issue(str(f1), service="web"),
            _make_issue(str(f2), service="db"),
        ]
        result = apply_fixes(issues, tmp_path, backup=True)

        assert result.applied == 2
        assert len(result.backup_paths) == 2

    def test_fix_verifies_yaml_structure(self, tmp_path: Path):
        compose = tmp_path / "compose.yaml"
        compose.write_text("services:\n  web:\n    image: nginx\n", encoding="utf-8")

        issue = _make_issue(str(compose))
        result = apply_fixes([issue], tmp_path, backup=False)

        assert result.applied == 1
        assert len(result.verified_files) == 1
        assert result.verified_files[0] == compose
        assert result.verification_errors == []


class TestVerifyYamlFile:
    def test_valid_compose(self, tmp_path: Path):
        f = tmp_path / "compose.yaml"
        f.write_text("services:\n  web:\n    image: nginx\n", encoding="utf-8")
        ok, msg = verify_yaml_file(f)
        assert ok is True
        assert msg == ""

    def test_missing_services_key(self, tmp_path: Path):
        f = tmp_path / "compose.yaml"
        f.write_text("version: '3'\n", encoding="utf-8")
        ok, msg = verify_yaml_file(f)
        assert ok is False
        assert "services" in msg

    def test_empty_file(self, tmp_path: Path):
        f = tmp_path / "compose.yaml"
        f.write_text("", encoding="utf-8")
        ok, msg = verify_yaml_file(f)
        assert ok is False

    def test_invalid_yaml(self, tmp_path: Path):
        f = tmp_path / "compose.yaml"
        f.write_text("{{invalid yaml: [", encoding="utf-8")
        ok, msg = verify_yaml_file(f)
        assert ok is False

    def test_services_is_mapping(self, tmp_path: Path):
        f = tmp_path / "compose.yaml"
        f.write_text("services:\n  web:\n    image: nginx\n", encoding="utf-8")
        ok, _ = verify_yaml_file(f)
        assert ok is True

    def test_services_not_mapping(self, tmp_path: Path):
        f = tmp_path / "compose.yaml"
        f.write_text("services:\n  - web\n  - db\n", encoding="utf-8")
        ok, msg = verify_yaml_file(f)
        assert ok is False
        assert "mapping" in msg.lower() or "list" in msg.lower()
