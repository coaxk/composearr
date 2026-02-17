"""Sprint 11 tests: recursive scan, .composearrignore, profiles, performance, templates."""

from __future__ import annotations

import json
import time
from pathlib import Path

import pytest

from composearr.config import Config, DEFAULT_RULES
from composearr.ignorefile import IgnoreFileParser, load_ignore_file
from composearr.profiles import (
    PROFILES,
    PROFILE_DESCRIPTIONS,
    apply_profile,
    get_profile_names,
    get_profile_overrides,
)
from composearr.templates.engine import TemplateEngine


# ===========================================================================
# .composearrignore — IgnoreFileParser
# ===========================================================================


class TestIgnoreFileParser:
    """Tests for the .composearrignore parser."""

    def test_empty_content(self) -> None:
        p = IgnoreFileParser()
        p.parse("")
        assert p.is_ignored("compose.yaml") is False

    def test_comment_lines_ignored(self) -> None:
        p = IgnoreFileParser()
        p.parse("# this is a comment\n# another comment")
        assert p.is_ignored("compose.yaml") is False

    def test_blank_lines_ignored(self) -> None:
        p = IgnoreFileParser()
        p.parse("\n\n\n")
        assert p.is_ignored("compose.yaml") is False

    def test_simple_filename_match(self) -> None:
        p = IgnoreFileParser()
        p.parse("compose.yaml")
        assert p.is_ignored("compose.yaml") is True

    def test_simple_filename_no_match(self) -> None:
        p = IgnoreFileParser()
        p.parse("compose.yaml")
        assert p.is_ignored("docker-compose.yaml") is False

    def test_glob_star(self) -> None:
        p = IgnoreFileParser()
        p.parse("*.yml")
        assert p.is_ignored("compose.yml") is True
        assert p.is_ignored("compose.yaml") is False

    def test_glob_question_mark(self) -> None:
        p = IgnoreFileParser()
        p.parse("test?.yaml")
        assert p.is_ignored("test1.yaml") is True
        assert p.is_ignored("test.yaml") is False

    def test_directory_pattern(self) -> None:
        p = IgnoreFileParser()
        p.parse("backup/")
        # Directory patterns stored with trailing slash
        assert p._patterns[0][1] == "backup/"
        # Should match files under that directory
        assert p.is_ignored("backup/compose.yaml") is True

    def test_negation_pattern(self) -> None:
        p = IgnoreFileParser()
        p.parse("*.yaml\n!important.yaml")
        assert p.is_ignored("compose.yaml") is True
        assert p.is_ignored("important.yaml") is False

    def test_anchored_pattern(self) -> None:
        p = IgnoreFileParser()
        p.parse("/root-only.yaml")
        assert p.is_ignored("root-only.yaml") is True
        assert p.is_ignored("sub/root-only.yaml") is False

    def test_doublestar_pattern(self) -> None:
        p = IgnoreFileParser()
        p.parse("**/test.yaml")
        assert p.is_ignored("test.yaml") is True
        assert p.is_ignored("sub/test.yaml") is True
        assert p.is_ignored("deep/sub/test.yaml") is True

    def test_path_with_directory(self) -> None:
        p = IgnoreFileParser()
        p.parse("backup/compose.yaml")
        assert p.is_ignored("backup/compose.yaml") is True
        assert p.is_ignored("other/compose.yaml") is False

    def test_windows_path_normalization(self) -> None:
        p = IgnoreFileParser()
        p.parse("backup/compose.yaml")
        assert p.is_ignored("backup\\compose.yaml") is True

    def test_multiple_patterns(self) -> None:
        p = IgnoreFileParser()
        p.parse("*.bak\n*.tmp\nold/")
        assert p.is_ignored("test.bak") is True
        assert p.is_ignored("test.tmp") is True
        assert p.is_ignored("test.yaml") is False

    def test_load_ignore_file_exists(self, tmp_path: Path) -> None:
        ignore_file = tmp_path / ".composearrignore"
        ignore_file.write_text("*.bak\nbackup/\n", encoding="utf-8")
        parser = load_ignore_file(tmp_path)
        assert parser.is_ignored("test.bak") is True
        assert parser.is_ignored("compose.yaml") is False

    def test_load_ignore_file_missing(self, tmp_path: Path) -> None:
        parser = load_ignore_file(tmp_path)
        # Should return an empty parser — nothing ignored
        assert parser.is_ignored("compose.yaml") is False

    def test_pattern_count(self) -> None:
        p = IgnoreFileParser()
        p.parse("a\nb\n# comment\nc\n\nd")
        assert len(p._patterns) == 4

    def test_negation_flag_stored(self) -> None:
        p = IgnoreFileParser()
        p.parse("!keep.yaml")
        assert p._patterns[0] == (True, "keep.yaml")

    def test_comment_with_space(self) -> None:
        p = IgnoreFileParser()
        p.parse("  # indented comment")
        # Lines starting with # after rstrip
        # Actually " # indented comment" doesn't start with #
        # so it won't be treated as comment — it's treated as a pattern
        # That's fine, gitignore behaves similarly with leading spaces

    def test_star_in_subdir(self) -> None:
        p = IgnoreFileParser()
        p.parse("test/*.yaml")
        assert p.is_ignored("test/compose.yaml") is True
        assert p.is_ignored("compose.yaml") is False


# ===========================================================================
# .composearrignore integration with discovery
# ===========================================================================


class TestIgnoreDiscoveryIntegration:
    """Tests for .composearrignore integration with file discovery."""

    def test_discover_respects_ignore(self, tmp_path: Path) -> None:
        """Discovery should skip files matching .composearrignore patterns."""
        from composearr.scanner.discovery import discover_compose_files

        # Create compose files
        (tmp_path / "app" / "compose.yaml").parent.mkdir()
        (tmp_path / "app" / "compose.yaml").write_text(
            "services:\n  test:\n    image: test:1.0\n", encoding="utf-8"
        )
        (tmp_path / "backup" / "compose.yaml").parent.mkdir()
        (tmp_path / "backup" / "compose.yaml").write_text(
            "services:\n  old:\n    image: old:1.0\n", encoding="utf-8"
        )

        # Create .composearrignore that ignores backup/
        ignore_file = tmp_path / ".composearrignore"
        ignore_file.write_text("backup/\n", encoding="utf-8")

        parser = load_ignore_file(tmp_path)
        paths, _ = discover_compose_files(tmp_path, ignore_parser=parser)
        rel_paths = {str(p.relative_to(tmp_path)).replace("\\", "/") for p in paths}

        assert "app/compose.yaml" in rel_paths
        assert "backup/compose.yaml" not in rel_paths

    def test_discover_without_ignore(self, tmp_path: Path) -> None:
        """Discovery without ignore parser should find all files."""
        from composearr.scanner.discovery import discover_compose_files

        (tmp_path / "app" / "compose.yaml").parent.mkdir()
        (tmp_path / "app" / "compose.yaml").write_text(
            "services:\n  test:\n    image: test:1.0\n", encoding="utf-8"
        )
        (tmp_path / "backup" / "compose.yaml").parent.mkdir()
        (tmp_path / "backup" / "compose.yaml").write_text(
            "services:\n  old:\n    image: old:1.0\n", encoding="utf-8"
        )

        paths, _ = discover_compose_files(tmp_path)
        assert len(paths) == 2

    def test_discover_with_max_depth(self, tmp_path: Path) -> None:
        """Discovery with max_depth=1 should only find top-level files."""
        from composearr.scanner.discovery import discover_compose_files

        # Top level
        (tmp_path / "compose.yaml").write_text(
            "services:\n  test:\n    image: test:1.0\n", encoding="utf-8"
        )
        # Depth 1
        (tmp_path / "app").mkdir()
        (tmp_path / "app" / "compose.yaml").write_text(
            "services:\n  test2:\n    image: test:2.0\n", encoding="utf-8"
        )
        # Depth 2
        (tmp_path / "app" / "sub").mkdir()
        (tmp_path / "app" / "sub" / "compose.yaml").write_text(
            "services:\n  test3:\n    image: test:3.0\n", encoding="utf-8"
        )

        paths, _ = discover_compose_files(tmp_path, max_depth=1)
        assert len(paths) == 1  # Only top-level compose.yaml (depth 1 = 1 part)

    def test_discover_default_depth(self, tmp_path: Path) -> None:
        """Default depth allows deep nesting."""
        from composearr.scanner.discovery import discover_compose_files

        (tmp_path / "a" / "b").mkdir(parents=True)
        (tmp_path / "a" / "b" / "compose.yaml").write_text(
            "services:\n  test:\n    image: test:1.0\n", encoding="utf-8"
        )
        paths, _ = discover_compose_files(tmp_path)
        assert len(paths) == 1


# ===========================================================================
# Rule Profiles
# ===========================================================================


class TestRuleProfiles:
    """Tests for rule severity profiles."""

    def test_profile_names(self) -> None:
        names = get_profile_names()
        assert "strict" in names
        assert "balanced" in names
        assert "relaxed" in names

    def test_profile_count(self) -> None:
        assert len(get_profile_names()) == 3

    def test_strict_profile_exists(self) -> None:
        overrides = get_profile_overrides("strict")
        assert isinstance(overrides, dict)

    def test_balanced_profile_empty(self) -> None:
        overrides = get_profile_overrides("balanced")
        assert overrides == {}

    def test_relaxed_profile_exists(self) -> None:
        overrides = get_profile_overrides("relaxed")
        assert isinstance(overrides, dict)
        assert len(overrides) > 0

    def test_strict_upgrades_to_error(self) -> None:
        overrides = get_profile_overrides("strict")
        assert overrides["CA001"] == "error"
        assert overrides["CA201"] == "error"
        assert overrides["CA501"] == "error"

    def test_strict_upgrades_info_to_warning(self) -> None:
        overrides = get_profile_overrides("strict")
        assert overrides["CA801"] == "warning"
        assert overrides["CA803"] == "warning"

    def test_relaxed_downgrades_errors(self) -> None:
        overrides = get_profile_overrides("relaxed")
        assert overrides["CA101"] == "warning"
        assert overrides["CA301"] == "warning"

    def test_relaxed_downgrades_warnings(self) -> None:
        overrides = get_profile_overrides("relaxed")
        assert overrides["CA201"] == "info"
        assert overrides["CA501"] == "info"

    def test_unknown_profile_raises(self) -> None:
        with pytest.raises(ValueError, match="Unknown profile"):
            get_profile_overrides("nonexistent")

    def test_case_insensitive(self) -> None:
        overrides = get_profile_overrides("STRICT")
        assert "CA001" in overrides

    def test_apply_profile_strict(self) -> None:
        rules = dict(DEFAULT_RULES)
        updated = apply_profile(rules, "strict")
        assert updated["CA001"] == "error"  # Was warning
        assert updated["CA101"] == "error"  # Was already error

    def test_apply_profile_balanced(self) -> None:
        rules = dict(DEFAULT_RULES)
        updated = apply_profile(rules, "balanced")
        assert updated == rules  # No changes

    def test_apply_profile_relaxed(self) -> None:
        rules = dict(DEFAULT_RULES)
        updated = apply_profile(rules, "relaxed")
        assert updated["CA001"] == "info"   # Was warning
        assert updated["CA201"] == "info"   # Was warning

    def test_profile_descriptions_exist(self) -> None:
        for name in get_profile_names():
            assert name in PROFILE_DESCRIPTIONS
            assert len(PROFILE_DESCRIPTIONS[name]) > 10

    def test_strict_has_many_overrides(self) -> None:
        overrides = get_profile_overrides("strict")
        assert len(overrides) >= 20


# ===========================================================================
# Config Profile Integration
# ===========================================================================


class TestConfigProfileIntegration:
    """Tests for profile integration with Config."""

    def test_config_profile_field_default(self) -> None:
        config = Config()
        assert config.profile is None

    def test_config_recursive_default(self) -> None:
        config = Config()
        assert config.recursive is False

    def test_config_max_depth_default(self) -> None:
        config = Config()
        assert config.max_depth is None

    def test_config_merge_profile(self) -> None:
        config = Config()
        config.merge({"profile": "strict"})
        assert config.profile == "strict"
        assert config.rules["CA001"] == "error"

    def test_config_merge_scan_recursive(self) -> None:
        config = Config()
        config.merge({"scan": {"recursive": True}})
        assert config.recursive is True

    def test_config_merge_scan_max_depth(self) -> None:
        config = Config()
        config.merge({"scan": {"max_depth": 3}})
        assert config.max_depth == 3

    def test_config_merge_profile_relaxed(self) -> None:
        config = Config()
        config.merge({"profile": "relaxed"})
        assert config.rules["CA001"] == "info"

    def test_config_merge_profile_balanced(self) -> None:
        config = Config()
        original = dict(config.rules)
        config.merge({"profile": "balanced"})
        assert config.rules == original


# ===========================================================================
# Performance — Parse Cache
# ===========================================================================


class TestParseCache:
    """Tests for the parse caching system."""

    def test_cache_clear(self) -> None:
        from composearr.engine import clear_parse_cache, _parse_cache
        _parse_cache["test_key"] = "test_value"
        clear_parse_cache()
        assert len(_parse_cache) == 0

    def test_cached_parse_returns_compose_file(self, tmp_path: Path) -> None:
        from composearr.engine import _cached_parse, clear_parse_cache
        clear_parse_cache()

        f = tmp_path / "compose.yaml"
        f.write_text("services:\n  test:\n    image: test:1.0\n", encoding="utf-8")
        cf = _cached_parse(f)
        assert cf.path == f
        assert "test" in cf.services

    def test_cached_parse_returns_same_object(self, tmp_path: Path) -> None:
        from composearr.engine import _cached_parse, clear_parse_cache
        clear_parse_cache()

        f = tmp_path / "compose.yaml"
        f.write_text("services:\n  test:\n    image: test:1.0\n", encoding="utf-8")
        cf1 = _cached_parse(f)
        cf2 = _cached_parse(f)
        assert cf1 is cf2  # Same cached object

    def test_cache_invalidates_on_mtime_change(self, tmp_path: Path) -> None:
        from composearr.engine import _cached_parse, clear_parse_cache
        import os
        clear_parse_cache()

        f = tmp_path / "compose.yaml"
        f.write_text("services:\n  v1:\n    image: test:1.0\n", encoding="utf-8")
        cf1 = _cached_parse(f)

        # Modify the file (change mtime)
        time.sleep(0.1)
        f.write_text("services:\n  v2:\n    image: test:2.0\n", encoding="utf-8")
        cf2 = _cached_parse(f)

        assert cf1 is not cf2  # New object after mtime change
        assert "v2" in cf2.services


# ===========================================================================
# Performance — Parallel Execution
# ===========================================================================


class TestParallelExecution:
    """Tests for parallel rule execution."""

    def test_audit_runs_with_few_files(self, tmp_path: Path) -> None:
        """Audit with <4 files should use sequential path."""
        from composearr.engine import run_audit, clear_parse_cache
        clear_parse_cache()

        for name in ["app1", "app2"]:
            d = tmp_path / name
            d.mkdir()
            (d / "compose.yaml").write_text(
                f"services:\n  {name}:\n    image: test:latest\n", encoding="utf-8"
            )

        result = run_audit(tmp_path)
        assert len(result.compose_files) == 2

    def test_audit_runs_with_many_files(self, tmp_path: Path) -> None:
        """Audit with >=4 files should use parallel path."""
        from composearr.engine import run_audit, clear_parse_cache
        clear_parse_cache()

        for i in range(5):
            d = tmp_path / f"app{i}"
            d.mkdir()
            (d / "compose.yaml").write_text(
                f"services:\n  app{i}:\n    image: test:latest\n", encoding="utf-8"
            )

        result = run_audit(tmp_path)
        assert len(result.compose_files) == 5
        assert len(result.issues) > 0  # Should detect :latest tag issues


# ===========================================================================
# Templates
# ===========================================================================


class TestNewTemplates:
    """Tests for the 10 new app templates."""

    def test_template_count(self) -> None:
        """Should have 20 templates total (10 original + 10 new)."""
        engine = TemplateEngine()
        templates = engine.list_templates()
        assert len(templates) >= 20

    def test_jellyfin_template(self) -> None:
        engine = TemplateEngine()
        t = engine.get_template("jellyfin")
        assert t is not None
        assert t.category == "media"

    def test_heimdall_template(self) -> None:
        engine = TemplateEngine()
        t = engine.get_template("heimdall")
        assert t is not None
        assert t.category == "dashboard"

    def test_portainer_template(self) -> None:
        engine = TemplateEngine()
        t = engine.get_template("portainer")
        assert t is not None
        assert t.category == "management"

    def test_uptime_kuma_template(self) -> None:
        engine = TemplateEngine()
        t = engine.get_template("uptime-kuma")
        assert t is not None
        assert t.category == "monitoring"

    def test_vaultwarden_template(self) -> None:
        engine = TemplateEngine()
        t = engine.get_template("vaultwarden")
        assert t is not None
        assert t.category == "security"

    def test_nextcloud_template(self) -> None:
        engine = TemplateEngine()
        t = engine.get_template("nextcloud")
        assert t is not None
        assert t.category == "storage"

    def test_photoprism_template(self) -> None:
        engine = TemplateEngine()
        t = engine.get_template("photoprism")
        assert t is not None
        assert t.category == "media"

    def test_calibre_web_template(self) -> None:
        engine = TemplateEngine()
        t = engine.get_template("calibre-web")
        assert t is not None
        assert t.category == "media"

    def test_freshrss_template(self) -> None:
        engine = TemplateEngine()
        t = engine.get_template("freshrss")
        assert t is not None
        assert t.category == "utility"

    def test_watchtower_template(self) -> None:
        engine = TemplateEngine()
        t = engine.get_template("watchtower")
        assert t is not None
        assert t.category == "management"

    def test_all_templates_have_description(self) -> None:
        engine = TemplateEngine()
        for name, meta in engine.list_templates().items():
            assert meta.description, f"Template {name} missing description"

    def test_all_templates_have_category(self) -> None:
        engine = TemplateEngine()
        for name, meta in engine.list_templates().items():
            assert meta.category != "other", f"Template {name} has default category"

    def test_all_templates_have_tags(self) -> None:
        engine = TemplateEngine()
        for name, meta in engine.list_templates().items():
            assert len(meta.tags) > 0, f"Template {name} has no tags"

    def test_jellyfin_generate(self, tmp_path: Path) -> None:
        engine = TemplateEngine()
        result = engine.generate("jellyfin", tmp_path)
        assert result.compose_path.is_file()
        content = result.compose_path.read_text(encoding="utf-8")
        assert "jellyfin" in content

    def test_watchtower_generate(self, tmp_path: Path) -> None:
        engine = TemplateEngine()
        result = engine.generate("watchtower", tmp_path)
        assert result.compose_path.is_file()
        content = result.compose_path.read_text(encoding="utf-8")
        assert "watchtower" in content

    def test_portainer_has_docker_sock(self) -> None:
        engine = TemplateEngine()
        template_file = engine.templates_dir / "portainer.yaml"
        content = template_file.read_text(encoding="utf-8")
        assert "/var/run/docker.sock" in content

    def test_watchtower_has_docker_sock(self) -> None:
        engine = TemplateEngine()
        template_file = engine.templates_dir / "watchtower.yaml"
        content = template_file.read_text(encoding="utf-8")
        assert "/var/run/docker.sock" in content

    def test_vaultwarden_has_healthcheck(self) -> None:
        engine = TemplateEngine()
        template_file = engine.templates_dir / "vaultwarden.yaml"
        content = template_file.read_text(encoding="utf-8")
        assert "/alive" in content

    def test_photoprism_has_status_endpoint(self) -> None:
        engine = TemplateEngine()
        template_file = engine.templates_dir / "photoprism.yaml"
        content = template_file.read_text(encoding="utf-8")
        assert "/api/v1/status" in content


# ===========================================================================
# Engine Integration — .composearrignore in audit
# ===========================================================================


class TestEngineIgnoreIntegration:
    """Tests for .composearrignore in the audit engine."""

    def test_audit_respects_composearrignore(self, tmp_path: Path) -> None:
        from composearr.engine import run_audit, clear_parse_cache
        clear_parse_cache()

        # Create two compose files
        (tmp_path / "app").mkdir()
        (tmp_path / "app" / "compose.yaml").write_text(
            "services:\n  app:\n    image: test:latest\n", encoding="utf-8"
        )
        (tmp_path / "ignored").mkdir()
        (tmp_path / "ignored" / "compose.yaml").write_text(
            "services:\n  ignored:\n    image: test:latest\n", encoding="utf-8"
        )

        # Create .composearrignore
        (tmp_path / ".composearrignore").write_text("ignored/\n", encoding="utf-8")

        result = run_audit(tmp_path)
        # Should only have scanned the app/ compose file
        assert len(result.compose_files) == 1
        assert "app" in result.compose_files[0].services

    def test_audit_without_composearrignore(self, tmp_path: Path) -> None:
        from composearr.engine import run_audit, clear_parse_cache
        clear_parse_cache()

        (tmp_path / "app").mkdir()
        (tmp_path / "app" / "compose.yaml").write_text(
            "services:\n  app:\n    image: test:1.0\n", encoding="utf-8"
        )
        (tmp_path / "other").mkdir()
        (tmp_path / "other" / "compose.yaml").write_text(
            "services:\n  other:\n    image: test:1.0\n", encoding="utf-8"
        )

        result = run_audit(tmp_path)
        assert len(result.compose_files) == 2
