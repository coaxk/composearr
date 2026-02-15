"""Tests for scanner module: discovery, parser, env_resolver."""

from __future__ import annotations

from pathlib import Path

import pytest

from composearr.scanner.discovery import discover_compose_files
from composearr.scanner.parser import parse_compose_file, find_line_number, find_service_line
from composearr.scanner.env_resolver import load_env_file, discover_env_files, resolve_variable


# ── Discovery ────────────────────────────────────────────────


class TestDiscovery:
    def test_finds_compose_yaml(self, tmp_path: Path):
        (tmp_path / "svc1").mkdir()
        (tmp_path / "svc1" / "compose.yaml").write_text("services:\n  web:\n    image: nginx:1.0\n")
        (tmp_path / "svc2").mkdir()
        (tmp_path / "svc2" / "compose.yaml").write_text("services:\n  api:\n    image: node:18\n")

        paths, managed = discover_compose_files(tmp_path)
        assert len(paths) == 2
        assert len(managed) == 0

    def test_finds_docker_compose_yml(self, tmp_path: Path):
        (tmp_path / "docker-compose.yml").write_text("services:\n  web:\n    image: nginx:1.0\n")
        paths, _ = discover_compose_files(tmp_path)
        assert len(paths) == 1

    def test_ignores_hidden_directories(self, tmp_path: Path):
        hidden = tmp_path / ".git"
        hidden.mkdir()
        (hidden / "compose.yaml").write_text("services: {}")
        paths, _ = discover_compose_files(tmp_path)
        assert len(paths) == 0

    def test_empty_directory(self, tmp_path: Path):
        paths, managed = discover_compose_files(tmp_path)
        assert paths == []
        assert managed == {}

    def test_nonexistent_directory(self):
        paths, managed = discover_compose_files(Path("/nonexistent/path/xyz"))
        assert paths == []
        assert managed == {}

    def test_recursive_discovery(self, tmp_path: Path):
        deep = tmp_path / "level1" / "level2"
        deep.mkdir(parents=True)
        (deep / "compose.yaml").write_text("services:\n  web:\n    image: nginx:1.0\n")
        paths, _ = discover_compose_files(tmp_path)
        assert len(paths) == 1


# ── Parser ───────────────────────────────────────────────────


class TestParser:
    def test_parses_valid_compose(self, tmp_path: Path):
        f = tmp_path / "compose.yaml"
        f.write_text("services:\n  web:\n    image: nginx:1.0\n")
        cf = parse_compose_file(f)
        assert cf.parse_error is None
        assert "web" in cf.services
        assert cf.services["web"]["image"] == "nginx:1.0"

    def test_preserves_raw_content(self, tmp_path: Path):
        content = "# comment\nservices:\n  web:\n    image: nginx:1.0\n"
        f = tmp_path / "compose.yaml"
        f.write_text(content)
        cf = parse_compose_file(f)
        assert "# comment" in cf.raw_content

    def test_handles_malformed_yaml(self, tmp_path: Path):
        f = tmp_path / "compose.yaml"
        f.write_text("services:\n  web:\n    image: nginx:latest\n  invalid syntax here\n")
        cf = parse_compose_file(f)
        # Should either parse with error or handle gracefully
        # The parser wraps errors in parse_error field
        assert cf is not None

    def test_handles_empty_file(self, tmp_path: Path):
        f = tmp_path / "compose.yaml"
        f.write_text("")
        cf = parse_compose_file(f)
        assert cf is not None
        assert cf.services == {}

    def test_handles_comments_only(self, tmp_path: Path):
        f = tmp_path / "compose.yaml"
        f.write_text("# just a comment\n# another one\n")
        cf = parse_compose_file(f)
        assert cf is not None
        assert cf.services == {}

    def test_handles_nonexistent_file(self, tmp_path: Path):
        f = tmp_path / "does_not_exist.yaml"
        cf = parse_compose_file(f)
        assert cf.parse_error is not None

    def test_multiple_services(self, tmp_path: Path):
        content = "services:\n  web:\n    image: nginx:1.0\n  api:\n    image: node:18\n  db:\n    image: postgres:15\n"
        f = tmp_path / "compose.yaml"
        f.write_text(content)
        cf = parse_compose_file(f)
        assert len(cf.services) == 3


class TestFindLineNumber:
    def test_finds_key(self):
        content = "services:\n  web:\n    image: nginx:1.0\n"
        line = find_line_number(content, "image:")
        assert line == 3

    def test_finds_key_value(self):
        content = "services:\n  web:\n    image: nginx:1.0\n"
        line = find_line_number(content, "image:", "nginx:1.0")
        assert line == 3

    def test_returns_none_for_missing(self):
        content = "services:\n  web:\n    image: nginx:1.0\n"
        line = find_line_number(content, "nonexistent:")
        assert line is None


# ── Env Resolver ─────────────────────────────────────────────


class TestEnvResolver:
    def test_loads_env_file(self, tmp_path: Path):
        env_file = tmp_path / ".env"
        env_file.write_text("PUID=1000\nPGID=1000\nTZ=Australia/Sydney\n")
        env_vars = load_env_file(env_file)
        assert env_vars["PUID"] == "1000"
        assert env_vars["TZ"] == "Australia/Sydney"

    def test_discovers_env_files(self, tmp_path: Path):
        (tmp_path / ".env").write_text("KEY=value\n")
        files = discover_env_files(tmp_path)
        assert len(files) >= 1

    def test_resolve_simple_variable(self):
        env = {"MY_VAR": "hello"}
        result = resolve_variable("${MY_VAR}", env)
        assert result == "hello"

    def test_resolve_with_default(self):
        env: dict[str, str] = {}
        result = resolve_variable("${MISSING:-fallback}", env)
        assert result == "fallback"

    def test_resolve_no_match(self):
        env: dict[str, str] = {}
        result = resolve_variable("plain_value", env)
        assert result == "plain_value"
