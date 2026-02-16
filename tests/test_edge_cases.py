"""Edge case tests — malformed YAML, empty dirs, large stacks, single files."""

from __future__ import annotations

import time
from pathlib import Path

import pytest

from composearr.engine import run_audit
from composearr.scanner.parser import parse_compose_file


class TestMalformedYaml:
    """Graceful handling of broken YAML files."""

    def test_invalid_yaml_syntax(self, tmp_path: Path):
        """Should capture parse error, not crash."""
        compose = tmp_path / "compose.yaml"
        compose.write_text(
            "services:\n  test:\n    image: nginx\n    invalid - syntax here\n",
            encoding="utf-8",
        )
        cf = parse_compose_file(compose)
        assert cf.parse_error is not None

    def test_completely_invalid_yaml(self, tmp_path: Path):
        """Totally broken content should not crash."""
        compose = tmp_path / "compose.yaml"
        compose.write_text("{{{{not yaml at all!!!!}}}}", encoding="utf-8")
        cf = parse_compose_file(compose)
        # May parse as a valid YAML mapping or trigger error — either way, no crash
        assert cf is not None

    def test_empty_file(self, tmp_path: Path):
        """Empty compose file should not crash."""
        compose = tmp_path / "compose.yaml"
        compose.write_text("", encoding="utf-8")
        cf = parse_compose_file(compose)
        # Empty YAML is valid but has no services
        assert cf.services == {}

    def test_yaml_with_only_comments(self, tmp_path: Path):
        """File with only comments should not crash."""
        compose = tmp_path / "compose.yaml"
        compose.write_text("# This is a comment\n# Another comment\n", encoding="utf-8")
        cf = parse_compose_file(compose)
        assert cf.services == {}

    def test_yaml_without_services_key(self, tmp_path: Path):
        """YAML without services key should not crash."""
        compose = tmp_path / "compose.yaml"
        compose.write_text("version: '3'\nnetworks:\n  default:\n", encoding="utf-8")
        cf = parse_compose_file(compose)
        assert cf.services == {}

    def test_services_is_null(self, tmp_path: Path):
        """services: null should not crash."""
        compose = tmp_path / "compose.yaml"
        compose.write_text("services:\n", encoding="utf-8")
        cf = parse_compose_file(compose)
        # services key exists but is None — services property should handle gracefully
        assert cf.parse_error is None or cf.services == {}

    def test_tabs_in_yaml(self, tmp_path: Path):
        """Tabs cause YAML errors — should capture, not crash."""
        compose = tmp_path / "compose.yaml"
        compose.write_text("services:\n\ttest:\n\t\timage: nginx\n", encoding="utf-8")
        cf = parse_compose_file(compose)
        assert cf.parse_error is not None

    def test_duplicate_keys(self, tmp_path: Path):
        """Duplicate keys should not crash (ruamel treats as error by default)."""
        compose = tmp_path / "compose.yaml"
        compose.write_text(
            "services:\n  app:\n    image: nginx\n  app:\n    image: redis\n",
            encoding="utf-8",
        )
        cf = parse_compose_file(compose)
        # ruamel.yaml flags duplicate keys — either error or parsed, but no crash
        assert cf is not None

    def test_binary_content(self, tmp_path: Path):
        """Binary content should not crash parser."""
        compose = tmp_path / "compose.yaml"
        compose.write_bytes(b"\x00\x01\x02\x03\xff\xfe")
        cf = parse_compose_file(compose)
        assert cf.parse_error is not None


class TestEmptyAndMissing:
    """Handle empty directories and missing paths gracefully."""

    def test_empty_directory(self, tmp_path: Path):
        """Empty directory should return zero issues."""
        result = run_audit(tmp_path)
        assert len(result.all_issues) == 0
        assert len(result.compose_files) == 0

    def test_directory_with_no_compose_files(self, tmp_path: Path):
        """Directory with non-compose files should scan cleanly."""
        (tmp_path / "random.txt").write_text("hello", encoding="utf-8")
        (tmp_path / "config.json").write_text("{}", encoding="utf-8")
        result = run_audit(tmp_path)
        assert len(result.all_issues) == 0

    def test_nested_empty_dirs(self, tmp_path: Path):
        """Nested empty directories should not crash."""
        for name in ["app1", "app2", "app3"]:
            (tmp_path / name).mkdir()
        result = run_audit(tmp_path)
        assert len(result.all_issues) == 0


class TestSingleFile:
    """Audit behavior with single compose files."""

    def test_single_valid_file(self, tmp_path: Path):
        """Single compose file with issues should report them."""
        compose = tmp_path / "compose.yaml"
        compose.write_text(
            "services:\n  app:\n    image: nginx:latest\n",
            encoding="utf-8",
        )
        result = run_audit(tmp_path)
        rule_ids = {i.rule_id for i in result.all_issues}
        assert "CA001" in rule_ids  # latest tag

    def test_single_perfect_file(self, tmp_path: Path):
        """Perfectly configured file should have minimal issues."""
        compose = tmp_path / "compose.yaml"
        compose.write_text(
            "services:\n"
            "  app:\n"
            "    image: nginx:1.25.3\n"
            "    restart: unless-stopped\n"
            "    environment:\n"
            "      TZ: Etc/UTC\n"
            "    healthcheck:\n"
            "      test: ['CMD', 'curl', '-f', 'http://localhost']\n"
            "      interval: 30s\n"
            "      timeout: 10s\n"
            "      retries: 3\n",
            encoding="utf-8",
        )
        result = run_audit(tmp_path)
        # Should have very few or no issues
        errors = [i for i in result.all_issues if i.severity.value == "error"]
        assert len(errors) == 0


class TestAuditContinuesOnErrors:
    """Audit should continue when individual files fail."""

    def test_audit_continues_past_broken_file(self, tmp_path: Path):
        """One broken file should not stop the audit."""
        # Good file
        good_dir = tmp_path / "good"
        good_dir.mkdir()
        (good_dir / "compose.yaml").write_text(
            "services:\n  app:\n    image: nginx:latest\n",
            encoding="utf-8",
        )

        # Broken file (tabs cause YAML parse error)
        bad_dir = tmp_path / "bad"
        bad_dir.mkdir()
        (bad_dir / "compose.yaml").write_text(
            "services:\n\tbroken:\n\t\timage: nginx\n",
            encoding="utf-8",
        )

        result = run_audit(tmp_path)
        # Should still find issues in the good file
        assert len(result.compose_files) == 2
        assert any(cf.parse_error is not None for cf in result.compose_files)
        assert any(cf.parse_error is None for cf in result.compose_files)
        assert len(result.all_issues) > 0

    def test_multiple_broken_files(self, tmp_path: Path):
        """Multiple broken files should not crash."""
        for i in range(5):
            d = tmp_path / f"broken{i}"
            d.mkdir()
            (d / "compose.yaml").write_text(f"not valid yaml {{{i}}}", encoding="utf-8")

        result = run_audit(tmp_path)
        assert len(result.compose_files) == 5
        assert all(cf.parse_error is not None for cf in result.compose_files)


class TestLargeStack:
    """Performance with many compose files."""

    def test_100_service_stack(self, tmp_path: Path):
        """100 compose files should complete in reasonable time."""
        from composearr.rules.CA0xx_images import set_network_enabled

        for i in range(100):
            svc_dir = tmp_path / f"service{i:03d}"
            svc_dir.mkdir()
            (svc_dir / "compose.yaml").write_text(
                f"services:\n"
                f"  svc{i}:\n"
                f"    image: nginx:latest\n"
                f"    restart: unless-stopped\n"
                f"    ports:\n"
                f"      - \"{8000 + i}:80\"\n",
                encoding="utf-8",
            )

        # Disable network lookups — this tests audit speed, not network
        set_network_enabled(False)
        try:
            start = time.perf_counter()
            result = run_audit(tmp_path)
            elapsed = time.perf_counter() - start
        finally:
            set_network_enabled(True)

        assert len(result.compose_files) == 100
        assert elapsed < 30.0  # Must complete in under 30 seconds
        assert len(result.all_issues) > 0  # Should find CA001 issues

    def test_services_per_file(self, tmp_path: Path):
        """Single file with many services should work."""
        from composearr.rules.CA0xx_images import set_network_enabled

        lines = ["services:"]
        for i in range(50):
            lines.extend([
                f"  service{i}:",
                f"    image: nginx:latest",
                f"    restart: unless-stopped",
            ])
        compose = tmp_path / "compose.yaml"
        compose.write_text("\n".join(lines) + "\n", encoding="utf-8")

        set_network_enabled(False)
        try:
            result = run_audit(tmp_path)
        finally:
            set_network_enabled(True)
        assert len(result.compose_files) == 1
        assert len(result.all_issues) > 0
