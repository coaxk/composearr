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
        f.write_text("test")
        ok, err = validate_scan_path(f)
        assert not ok
        assert "not a directory" in err

    def test_file_size_ok(self, tmp_path: Path):
        f = tmp_path / "test.yaml"
        f.write_text("services: {}")
        ok, err = validate_file_size(f)
        assert ok

    def test_yaml_content_ok(self):
        ok, err = validate_yaml_content("services:\n  web:\n    image: nginx\n")
        assert ok

    def test_yaml_content_binary(self):
        ok, err = validate_yaml_content("services\x00binary")
        assert not ok
        assert "binary" in err


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
