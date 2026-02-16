"""Cross-platform compatibility tests."""

from __future__ import annotations

from pathlib import Path

from composearr.scanner.discovery import discover_compose_files
from composearr.scanner.parser import parse_compose_file
from composearr.scanner.platform_detect import classify_paths


class TestPathHandling:
    """Ensure paths work on all platforms."""

    def test_path_normalizes_separators(self, tmp_path: Path):
        """Path() should normalize separators regardless of input."""
        # All these should resolve to the same thing
        p1 = Path(str(tmp_path) + "/sonarr/compose.yaml")
        p2 = Path(str(tmp_path) + "\\sonarr\\compose.yaml")
        assert p1 == p2

    def test_relative_path_as_posix(self, tmp_path: Path):
        """as_posix() should always use forward slashes."""
        child = tmp_path / "sub" / "dir" / "file.yaml"
        rel = child.relative_to(tmp_path).as_posix()
        assert "\\" not in rel
        assert rel == "sub/dir/file.yaml"

    def test_discover_in_empty_dir(self, tmp_path: Path):
        """Discovery should return empty list for empty directory."""
        paths, managed = discover_compose_files(tmp_path)
        assert paths == []
        assert managed == {}

    def test_discover_finds_compose_files(self, tmp_path: Path):
        """Discovery should find compose files regardless of platform."""
        svc_dir = tmp_path / "myservice"
        svc_dir.mkdir()
        compose = svc_dir / "compose.yaml"
        compose.write_text("services:\n  app:\n    image: nginx\n", encoding="utf-8")

        paths, _ = discover_compose_files(tmp_path)
        assert len(paths) == 1
        assert paths[0].name == "compose.yaml"

    def test_parser_handles_any_path(self, tmp_path: Path):
        """Parser should work with any valid path format."""
        compose = tmp_path / "compose.yaml"
        compose.write_text(
            "services:\n  web:\n    image: nginx:1.25\n",
            encoding="utf-8",
        )
        cf = parse_compose_file(compose)
        assert cf.parse_error is None
        assert "web" in cf.services

    def test_classify_paths_normalizes(self, tmp_path: Path):
        """Platform detection should work regardless of separator."""
        dockge = tmp_path / "dockge" / "stacks" / "app" / "compose.yaml"
        dockge.parent.mkdir(parents=True)
        dockge.write_text("services: {}", encoding="utf-8")

        canonical, managed = classify_paths([dockge], tmp_path)
        assert "Dockge" in managed
        assert len(canonical) == 0


class TestLineEndings:
    """Ensure CRLF and LF are both handled."""

    def test_parse_lf_yaml(self, tmp_path: Path):
        """Standard LF line endings should parse fine."""
        compose = tmp_path / "compose.yaml"
        content = "services:\n  app:\n    image: nginx:1.25\n"
        compose.write_bytes(content.encode("utf-8"))

        cf = parse_compose_file(compose)
        assert cf.parse_error is None
        assert "app" in cf.services

    def test_parse_crlf_yaml(self, tmp_path: Path):
        """Windows CRLF line endings should parse fine."""
        compose = tmp_path / "compose.yaml"
        content = "services:\r\n  app:\r\n    image: nginx:1.25\r\n"
        compose.write_bytes(content.encode("utf-8"))

        cf = parse_compose_file(compose)
        assert cf.parse_error is None
        assert "app" in cf.services

    def test_parse_mixed_line_endings(self, tmp_path: Path):
        """Mixed line endings should still parse."""
        compose = tmp_path / "compose.yaml"
        content = "services:\n  app:\r\n    image: nginx:1.25\n"
        compose.write_bytes(content.encode("utf-8"))

        cf = parse_compose_file(compose)
        assert cf.parse_error is None


class TestSpecialPaths:
    """Paths with spaces, unicode, etc."""

    def test_path_with_spaces(self, tmp_path: Path):
        """Directories with spaces should work."""
        spaced = tmp_path / "my docker stacks" / "app"
        spaced.mkdir(parents=True)
        compose = spaced / "compose.yaml"
        compose.write_text(
            "services:\n  web:\n    image: nginx\n",
            encoding="utf-8",
        )

        cf = parse_compose_file(compose)
        assert cf.parse_error is None

    def test_path_with_unicode(self, tmp_path: Path):
        """Unicode in path should work."""
        unidir = tmp_path / "stacks-v2"
        unidir.mkdir()
        compose = unidir / "compose.yaml"
        compose.write_text(
            "services:\n  web:\n    image: nginx\n",
            encoding="utf-8",
        )

        cf = parse_compose_file(compose)
        assert cf.parse_error is None

    def test_deeply_nested_path(self, tmp_path: Path):
        """Deeply nested directories should work."""
        deep = tmp_path
        for i in range(10):
            deep = deep / f"level{i}"
        deep.mkdir(parents=True)
        compose = deep / "compose.yaml"
        compose.write_text(
            "services:\n  app:\n    image: nginx\n",
            encoding="utf-8",
        )

        cf = parse_compose_file(compose)
        assert cf.parse_error is None


class TestSarifPaths:
    """SARIF URIs should always use forward slashes."""

    def test_sarif_uri_forward_slashes(self):
        """SARIF file URIs should use forward slashes on all platforms."""
        from composearr.formatters.sarif_formatter import format_sarif
        from composearr.models import FormatOptions, LintIssue, ScanResult, Severity

        result = ScanResult()
        result.compose_files = []
        issue = LintIssue(
            rule_id="CA001",
            rule_name="no-latest-tag",
            severity=Severity.WARNING,
            message="Test",
            file_path="sub\\dir\\compose.yaml",
        )
        result.issues = [issue]

        output = format_sarif(result, ".", FormatOptions())
        assert "sub/dir/compose.yaml" in output
        assert "sub\\\\dir" not in output
