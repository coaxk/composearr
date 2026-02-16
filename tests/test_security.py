"""Tests for security hardening utilities."""

from __future__ import annotations

from pathlib import Path

import pytest

from composearr.security.input_validator import (
    validate_file_size,
    validate_scan_path,
    validate_yaml_content,
)
from composearr.security.secret_masking import mask_secret


class TestInputValidator:
    def test_valid_path(self, tmp_path: Path):
        ok, err = validate_scan_path(tmp_path)
        assert ok
        assert err == ""

    def test_nonexistent_path(self):
        ok, err = validate_scan_path(Path("/nonexistent/path/xyz"))
        assert not ok
        assert "does not exist" in err

    def test_file_not_directory(self, tmp_path: Path):
        f = tmp_path / "test.yaml"
        f.write_text("test", encoding="utf-8")
        ok, err = validate_scan_path(f)
        assert not ok
        assert "not a directory" in err

    def test_file_size_ok(self, tmp_path: Path):
        f = tmp_path / "test.yaml"
        f.write_text("services: {}", encoding="utf-8")
        ok, err = validate_file_size(f)
        assert ok

    def test_yaml_content_ok(self):
        ok, err = validate_yaml_content("services:\n  web:\n    image: nginx\n")
        assert ok

    def test_yaml_content_binary(self):
        ok, err = validate_yaml_content("services\x00binary")
        assert not ok
        assert "binary" in err

    def test_yaml_content_excessive_lines(self):
        content = "key: value\n" * 15_000
        ok, err = validate_yaml_content(content)
        assert not ok
        assert "lines" in err

    def test_yaml_content_alias_bomb(self):
        # Simulate YAML alias bomb
        content = "a: &a\n" + "".join(f"b{i}: *a\n" for i in range(150))
        ok, err = validate_yaml_content(content)
        assert not ok
        assert "alias" in err.lower()

    def test_yaml_content_normal_aliases_ok(self):
        # A few aliases are fine
        content = "defaults: &defaults\n  restart: unless-stopped\nservices:\n  web:\n    <<: *defaults\n    image: nginx\n"
        ok, err = validate_yaml_content(content)
        assert ok


class TestDiscoverySecurity:
    """Security limits in file discovery."""

    def test_max_depth_enforced(self, tmp_path: Path):
        """Files nested beyond MAX_SCAN_DEPTH should be skipped."""
        from composearr.scanner.discovery import discover_compose_files

        # Create deeply nested compose file (depth 12)
        deep = tmp_path
        for i in range(12):
            deep = deep / f"level{i}"
        deep.mkdir(parents=True)
        (deep / "compose.yaml").write_text("services: {}", encoding="utf-8")

        # Also create a shallow one
        shallow = tmp_path / "app"
        shallow.mkdir()
        (shallow / "compose.yaml").write_text("services: {}", encoding="utf-8")

        paths, _ = discover_compose_files(tmp_path)
        # Should find the shallow one but not the deep one (>10 levels)
        assert len(paths) == 1
        assert "app" in str(paths[0])


class TestSecretMasking:
    def test_empty_value(self):
        assert mask_secret("") == "****"

    def test_short_value(self):
        result = mask_secret("abc123")
        assert "*" in result
        assert "a" not in result  # Fully masked

    def test_long_value(self):
        result = mask_secret("SuperSecretPassword123")
        assert result.startswith("Supe")
        assert result.endswith("d123")
        assert "*" in result

    def test_custom_show_chars(self):
        result = mask_secret("abcdefghijklmnop", show_chars=2)
        assert result.startswith("ab")
        assert result.endswith("op")
