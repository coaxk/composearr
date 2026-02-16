"""Tests for configuration system."""

from __future__ import annotations

from pathlib import Path

import pytest

from composearr.config import Config, load_config, parse_file_suppressions
from composearr.models import Severity


class TestConfig:
    def test_default_rules(self):
        config = Config()
        assert config.is_rule_enabled("CA001")
        assert config.is_rule_enabled("CA101")

    def test_disable_rule(self):
        config = Config()
        config.rules["CA001"] = "off"
        assert not config.is_rule_enabled("CA001")

    def test_get_severity(self):
        config = Config()
        assert config.get_severity("CA101") == Severity.ERROR
        assert config.get_severity("CA001") == Severity.WARNING

    def test_ignore_file_pattern(self):
        config = Config()
        config.ignore_patterns.append("test/*")
        assert config.should_ignore_file("test/compose.yaml")
        assert not config.should_ignore_file("prod/compose.yaml")

    def test_ignore_service(self):
        config = Config()
        config.ignore_services.append("watchtower")
        assert config.should_ignore_service("watchtower")
        assert not config.should_ignore_service("sonarr")

    def test_merge_rules(self):
        config = Config()
        config.merge({"rules": {"no-latest-tag": "error"}})
        assert config.get_severity("CA001") == Severity.ERROR

    def test_merge_ignore_list(self):
        config = Config()
        config.merge({"ignore": ["test/**"]})
        assert "test/**" in config.ignore_patterns

    def test_merge_ignore_dict(self):
        config = Config()
        config.merge({"ignore": {"services": ["watchtower"], "files": ["test/*"]}})
        assert "watchtower" in config.ignore_services
        assert "test/*" in config.ignore_patterns


class TestLoadConfig:
    def test_loads_defaults(self, tmp_path: Path):
        config = load_config(tmp_path)
        assert isinstance(config, Config)
        assert config.is_rule_enabled("CA001")

    def test_loads_project_config(self, tmp_path: Path):
        cfg_file = tmp_path / ".composearr.yml"
        cfg_file.write_text("rules:\n  CA001: off\n", encoding="utf-8")
        config = load_config(tmp_path)
        assert not config.is_rule_enabled("CA001")

    def test_ignores_missing_config(self, tmp_path: Path):
        config = load_config(tmp_path)
        assert isinstance(config, Config)


class TestInlineSuppression:
    def test_file_level_ignore(self):
        content = "# composearr-ignore-file\nservices:\n  web:\n    image: nginx:latest\n"
        file_ignored, _, _ = parse_file_suppressions(content)
        assert file_ignored

    def test_line_level_ignore(self):
        content = "services:\n  web:\n    # composearr-ignore: CA001\n    image: nginx:latest\n"
        _, _, line_suppressions = parse_file_suppressions(content)
        assert len(line_suppressions) > 0
        # Line 3 has the comment, should suppress line 3 and 4
        suppressed_ids = set()
        for ids in line_suppressions.values():
            suppressed_ids.update(ids)
        assert "CA001" in suppressed_ids

    def test_multiple_rules_suppressed(self):
        content = "# composearr-ignore: CA001, CA201\nservices:\n  web:\n    image: nginx:latest\n"
        _, _, line_suppressions = parse_file_suppressions(content)
        suppressed_ids = set()
        for ids in line_suppressions.values():
            suppressed_ids.update(ids)
        assert "CA001" in suppressed_ids
        assert "CA201" in suppressed_ids

    def test_suppression_by_name(self):
        content = "# composearr-ignore: no-latest-tag\nservices:\n  web:\n    image: nginx:latest\n"
        _, _, line_suppressions = parse_file_suppressions(content)
        suppressed_ids = set()
        for ids in line_suppressions.values():
            suppressed_ids.update(ids)
        assert "CA001" in suppressed_ids

    def test_no_suppressions(self):
        content = "services:\n  web:\n    image: nginx:latest\n"
        file_ignored, _, line_suppressions = parse_file_suppressions(content)
        assert not file_ignored
        assert len(line_suppressions) == 0
