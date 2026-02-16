"""Sprint 3 tests — Watch Mode + Volume Rules (CA701-CA702)."""

from __future__ import annotations

import time
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from composearr.models import ComposeFile, LintIssue, Severity
from composearr.rules.base import get_rule


# ═══════════════════════════════════════════════════════════════
# WATCH MODE TESTS
# ═══════════════════════════════════════════════════════════════


class TestComposeFileHandler:
    """Test the watchdog file handler."""

    def test_is_compose_file_yaml(self):
        from composearr.watcher import ComposeFileHandler

        handler = ComposeFileHandler(lambda p: None)
        assert handler._is_compose_file(Path("compose.yaml")) is True
        assert handler._is_compose_file(Path("compose.yml")) is True
        assert handler._is_compose_file(Path("docker-compose.yaml")) is True
        assert handler._is_compose_file(Path("docker-compose.yml")) is True

    def test_is_not_compose_file(self):
        from composearr.watcher import ComposeFileHandler

        handler = ComposeFileHandler(lambda p: None)
        assert handler._is_compose_file(Path("readme.md")) is False
        assert handler._is_compose_file(Path("Dockerfile")) is False
        assert handler._is_compose_file(Path(".env")) is False
        assert handler._is_compose_file(Path("config.yaml")) is False

    def test_case_insensitive(self):
        from composearr.watcher import ComposeFileHandler

        handler = ComposeFileHandler(lambda p: None)
        assert handler._is_compose_file(Path("Compose.yaml")) is True
        assert handler._is_compose_file(Path("COMPOSE.YML")) is True
        assert handler._is_compose_file(Path("Docker-Compose.Yaml")) is True

    def test_debounce_blocks_rapid_calls(self):
        from composearr.watcher import ComposeFileHandler

        triggered = []
        handler = ComposeFileHandler(lambda p: triggered.append(p))
        handler.debounce_seconds = 0.2

        # Create a mock event
        event = MagicMock()
        event.is_directory = False
        event.src_path = str(Path("compose.yaml"))

        # First call should trigger
        handler.on_modified(event)
        assert len(triggered) == 1

        # Immediate second call should be debounced
        handler.on_modified(event)
        assert len(triggered) == 1

        # After debounce window, should trigger again
        time.sleep(0.25)
        handler.on_modified(event)
        assert len(triggered) == 2

    def test_debounce_different_files(self):
        from composearr.watcher import ComposeFileHandler

        triggered = []
        handler = ComposeFileHandler(lambda p: triggered.append(p))
        handler.debounce_seconds = 0.5

        event1 = MagicMock()
        event1.is_directory = False
        event1.src_path = str(Path("compose.yaml"))

        event2 = MagicMock()
        event2.is_directory = False
        event2.src_path = str(Path("docker-compose.yml"))

        handler.on_modified(event1)
        handler.on_modified(event2)

        # Both should trigger (different files)
        assert len(triggered) == 2

    def test_ignores_directories(self):
        from composearr.watcher import ComposeFileHandler

        triggered = []
        handler = ComposeFileHandler(lambda p: triggered.append(p))

        event = MagicMock()
        event.is_directory = True
        event.src_path = str(Path("compose.yaml"))

        handler.on_modified(event)
        assert len(triggered) == 0

    def test_ignores_non_compose_files(self):
        from composearr.watcher import ComposeFileHandler

        triggered = []
        handler = ComposeFileHandler(lambda p: triggered.append(p))

        event = MagicMock()
        event.is_directory = False
        event.src_path = str(Path("README.md"))

        handler.on_modified(event)
        assert len(triggered) == 0


class TestWatchMode:
    """Test WatchMode class (without starting the actual watcher)."""

    def test_init(self, tmp_path):
        from composearr.watcher import WatchMode

        wm = WatchMode(tmp_path)
        assert wm.stack_path == tmp_path.resolve()
        assert wm.audit_count == 0
        assert wm.last_audit is None
        assert wm._running is False

    def test_stop_without_start(self, tmp_path):
        from composearr.watcher import WatchMode

        wm = WatchMode(tmp_path)
        # Should not raise
        wm.stop()

    def test_debounce_config(self, tmp_path):
        from composearr.watcher import WatchMode

        wm = WatchMode(tmp_path, debounce=2.5)
        assert wm.debounce == 2.5

    def test_on_audit_callback(self, tmp_path):
        from composearr.watcher import WatchMode

        results = []
        wm = WatchMode(tmp_path, on_audit=lambda p, r: results.append((p, r)))
        assert wm.on_audit is not None


# ═══════════════════════════════════════════════════════════════
# VOLUME RULES TESTS — CA701
# ═══════════════════════════════════════════════════════════════


def _make_compose_file(tmp_path, data_dict, raw_content=""):
    """Helper to create a ComposeFile for testing."""
    path = tmp_path / "compose.yaml"
    if not raw_content:
        # Generate minimal raw content
        lines = ["services:"]
        for svc_name in data_dict.get("services", {}):
            lines.append(f"  {svc_name}:")
            lines.append(f"    image: test")
        raw_content = "\n".join(lines)
    path.write_text(raw_content, encoding="utf-8")
    return ComposeFile(path=path, raw_content=raw_content, data=data_dict)


class TestCA701PreferNamedVolumes:
    """Test CA701: prefer-named-volumes rule."""

    def test_bind_mount_flagged(self, tmp_path):
        rule = get_rule("CA701")
        cf = _make_compose_file(tmp_path, {"services": {"app": {"image": "nginx", "volumes": ["/host/data:/data"]}}})
        issues = rule.check_service("app", {"image": "nginx", "volumes": ["/host/data:/data"]}, cf)
        assert len(issues) == 1
        assert issues[0].rule_id == "CA701"
        assert "Bind mount" in issues[0].message

    def test_named_volume_passes(self, tmp_path):
        rule = get_rule("CA701")
        cf = _make_compose_file(tmp_path, {"services": {"app": {"image": "nginx", "volumes": ["app_data:/data"]}}})
        issues = rule.check_service("app", {"image": "nginx", "volumes": ["app_data:/data"]}, cf)
        assert len(issues) == 0

    def test_relative_bind_mount_flagged(self, tmp_path):
        rule = get_rule("CA701")
        cf = _make_compose_file(tmp_path, {"services": {"app": {}}})
        issues = rule.check_service("app", {"image": "nginx", "volumes": ["./data:/data"]}, cf)
        assert len(issues) == 1

    def test_docker_socket_exception(self, tmp_path):
        rule = get_rule("CA701")
        cf = _make_compose_file(tmp_path, {"services": {"app": {}}})
        issues = rule.check_service("app", {"image": "nginx", "volumes": ["/var/run/docker.sock:/var/run/docker.sock"]}, cf)
        assert len(issues) == 0

    def test_etc_localtime_exception(self, tmp_path):
        rule = get_rule("CA701")
        cf = _make_compose_file(tmp_path, {"services": {"app": {}}})
        issues = rule.check_service("app", {"image": "nginx", "volumes": ["/etc/localtime:/etc/localtime:ro"]}, cf)
        assert len(issues) == 0

    def test_etc_timezone_exception(self, tmp_path):
        rule = get_rule("CA701")
        cf = _make_compose_file(tmp_path, {"services": {"app": {}}})
        issues = rule.check_service("app", {"image": "nginx", "volumes": ["/etc/timezone:/etc/timezone:ro"]}, cf)
        assert len(issues) == 0

    def test_dev_mount_exception(self, tmp_path):
        rule = get_rule("CA701")
        cf = _make_compose_file(tmp_path, {"services": {"app": {}}})
        issues = rule.check_service("app", {"image": "nginx", "volumes": ["/dev/dri:/dev/dri"]}, cf)
        assert len(issues) == 0

    def test_sys_mount_exception(self, tmp_path):
        rule = get_rule("CA701")
        cf = _make_compose_file(tmp_path, {"services": {"app": {}}})
        issues = rule.check_service("app", {"image": "nginx", "volumes": ["/sys/class:/sys/class:ro"]}, cf)
        assert len(issues) == 0

    def test_no_volumes(self, tmp_path):
        rule = get_rule("CA701")
        cf = _make_compose_file(tmp_path, {"services": {"app": {}}})
        issues = rule.check_service("app", {"image": "nginx"}, cf)
        assert len(issues) == 0

    def test_multiple_bind_mounts(self, tmp_path):
        rule = get_rule("CA701")
        cf = _make_compose_file(tmp_path, {"services": {"app": {}}})
        issues = rule.check_service("app", {
            "image": "nginx",
            "volumes": ["/host/data:/data", "/host/config:/config"]
        }, cf)
        assert len(issues) == 2

    def test_mixed_volumes(self, tmp_path):
        rule = get_rule("CA701")
        cf = _make_compose_file(tmp_path, {"services": {"app": {}}})
        issues = rule.check_service("app", {
            "image": "nginx",
            "volumes": [
                "/host/data:/data",              # Bind mount — flag
                "app_cache:/cache",               # Named volume — OK
                "/var/run/docker.sock:/var/run/docker.sock",  # Exception — OK
            ]
        }, cf)
        assert len(issues) == 1

    def test_severity_is_info(self):
        rule = get_rule("CA701")
        assert rule.severity == Severity.INFO

    def test_suggested_fix_present(self, tmp_path):
        rule = get_rule("CA701")
        cf = _make_compose_file(tmp_path, {"services": {"app": {}}})
        issues = rule.check_service("app", {"image": "nginx", "volumes": ["/host/data:/data"]}, cf)
        assert issues[0].suggested_fix is not None
        assert "named volume" in issues[0].suggested_fix.lower() or "data" in issues[0].suggested_fix


# ═══════════════════════════════════════════════════════════════
# VOLUME RULES TESTS — CA702
# ═══════════════════════════════════════════════════════════════


class TestCA702UndefinedVolumeRef:
    """Test CA702: undefined-volume-ref rule."""

    def test_undefined_named_volume_flagged(self, tmp_path):
        rule = get_rule("CA702")
        cf = _make_compose_file(tmp_path, {
            "services": {"app": {"image": "nginx", "volumes": ["mydata:/data"]}},
            # No top-level volumes section
        })
        issues = rule.check_file(cf)
        assert len(issues) == 1
        assert issues[0].rule_id == "CA702"
        assert "mydata" in issues[0].message

    def test_defined_named_volume_passes(self, tmp_path):
        rule = get_rule("CA702")
        cf = _make_compose_file(tmp_path, {
            "services": {"app": {"image": "nginx", "volumes": ["mydata:/data"]}},
            "volumes": {"mydata": None},
        })
        issues = rule.check_file(cf)
        assert len(issues) == 0

    def test_bind_mount_not_flagged(self, tmp_path):
        rule = get_rule("CA702")
        cf = _make_compose_file(tmp_path, {
            "services": {"app": {"image": "nginx", "volumes": ["/host/data:/data"]}},
        })
        issues = rule.check_file(cf)
        assert len(issues) == 0

    def test_relative_bind_mount_not_flagged(self, tmp_path):
        rule = get_rule("CA702")
        cf = _make_compose_file(tmp_path, {
            "services": {"app": {"image": "nginx", "volumes": ["./data:/data"]}},
        })
        issues = rule.check_file(cf)
        assert len(issues) == 0

    def test_multiple_undefined_volumes(self, tmp_path):
        rule = get_rule("CA702")
        cf = _make_compose_file(tmp_path, {
            "services": {"app": {"image": "nginx", "volumes": ["vol_a:/a", "vol_b:/b"]}},
        })
        issues = rule.check_file(cf)
        assert len(issues) == 2
        names = {i.message.split("'")[1] for i in issues}
        assert names == {"vol_a", "vol_b"}

    def test_some_defined_some_not(self, tmp_path):
        rule = get_rule("CA702")
        cf = _make_compose_file(tmp_path, {
            "services": {"app": {"image": "nginx", "volumes": ["defined:/a", "undefined:/b"]}},
            "volumes": {"defined": None},
        })
        issues = rule.check_file(cf)
        assert len(issues) == 1
        assert "undefined" in issues[0].message

    def test_severity_is_error(self):
        rule = get_rule("CA702")
        assert rule.severity == Severity.ERROR

    def test_fix_available(self, tmp_path):
        rule = get_rule("CA702")
        cf = _make_compose_file(tmp_path, {
            "services": {"app": {"image": "nginx", "volumes": ["mydata:/data"]}},
        })
        issues = rule.check_file(cf)
        assert len(issues) == 1
        assert issues[0].fix_available is True

    def test_no_volumes_at_all(self, tmp_path):
        rule = get_rule("CA702")
        cf = _make_compose_file(tmp_path, {
            "services": {"app": {"image": "nginx"}},
        })
        issues = rule.check_file(cf)
        assert len(issues) == 0

    def test_empty_data(self, tmp_path):
        rule = get_rule("CA702")
        cf = _make_compose_file(tmp_path, {})
        issues = rule.check_file(cf)
        assert len(issues) == 0

    def test_multiple_services(self, tmp_path):
        rule = get_rule("CA702")
        cf = _make_compose_file(tmp_path, {
            "services": {
                "app": {"image": "nginx", "volumes": ["appdata:/data"]},
                "db": {"image": "postgres", "volumes": ["dbdata:/var/lib/postgresql"]},
            },
            "volumes": {"appdata": None},  # Only appdata defined
        })
        issues = rule.check_file(cf)
        assert len(issues) == 1
        assert "dbdata" in issues[0].message
        assert issues[0].service == "db"


# ═══════════════════════════════════════════════════════════════
# VOLUME HELPERS TESTS
# ═══════════════════════════════════════════════════════════════


class TestVolumeHelpers:
    """Test volume parsing helpers."""

    def test_parse_volume_string_bind(self):
        from composearr.rules.CA7xx_volumes import _parse_volume_entry

        source, target, mode = _parse_volume_entry("/host/data:/data")
        assert source == "/host/data"
        assert target == "/data"
        assert mode == ""

    def test_parse_volume_string_named(self):
        from composearr.rules.CA7xx_volumes import _parse_volume_entry

        source, target, mode = _parse_volume_entry("mydata:/data")
        assert source == "mydata"
        assert target == "/data"

    def test_parse_volume_with_mode(self):
        from composearr.rules.CA7xx_volumes import _parse_volume_entry

        source, target, mode = _parse_volume_entry("/host/data:/data:ro")
        assert source == "/host/data"
        assert target == "/data"
        assert mode == "ro"

    def test_parse_volume_single_path(self):
        from composearr.rules.CA7xx_volumes import _parse_volume_entry

        source, target, mode = _parse_volume_entry("/data")
        assert source == ""
        assert target == "/data"

    def test_parse_volume_dict(self):
        from composearr.rules.CA7xx_volumes import _parse_volume_entry

        source, target, mode = _parse_volume_entry({"source": "mydata", "target": "/data"})
        assert source == "mydata"
        assert target == "/data"

    def test_is_bind_mount(self):
        from composearr.rules.CA7xx_volumes import _is_bind_mount

        assert _is_bind_mount("/host/data") is True
        assert _is_bind_mount("./data") is True
        assert _is_bind_mount("../data") is True
        assert _is_bind_mount("mydata") is False

    def test_is_exception_mount(self):
        from composearr.rules.CA7xx_volumes import _is_exception_mount

        assert _is_exception_mount("/var/run/docker.sock") is True
        assert _is_exception_mount("/dev/dri") is True
        assert _is_exception_mount("/sys/class") is True
        assert _is_exception_mount("/etc/localtime") is True
        assert _is_exception_mount("/host/data") is False


# ═══════════════════════════════════════════════════════════════
# FIXER TESTS — CA702
# ═══════════════════════════════════════════════════════════════


class TestFixCA702:
    """Test auto-fix for undefined volume references."""

    def test_fix_adds_volume(self):
        from composearr.fixer import _fix_undefined_volume

        data = {
            "services": {"app": {"image": "nginx", "volumes": ["mydata:/data"]}},
        }
        issue = LintIssue(
            rule_id="CA702",
            rule_name="undefined-volume-ref",
            severity=Severity.ERROR,
            message="Volume 'mydata' referenced but not defined in volumes section",
            file_path="compose.yaml",
            fix_available=True,
        )
        result = _fix_undefined_volume(data, issue)
        assert result is True
        assert "volumes" in data
        assert "mydata" in data["volumes"]

    def test_fix_preserves_existing_volumes(self):
        from composearr.fixer import _fix_undefined_volume

        data = {
            "services": {"app": {"image": "nginx"}},
            "volumes": {"existing": None},
        }
        issue = LintIssue(
            rule_id="CA702",
            rule_name="undefined-volume-ref",
            severity=Severity.ERROR,
            message="Volume 'newvol' referenced but not defined in volumes section",
            file_path="compose.yaml",
            fix_available=True,
        )
        result = _fix_undefined_volume(data, issue)
        assert result is True
        assert "existing" in data["volumes"]
        assert "newvol" in data["volumes"]

    def test_fix_already_defined(self):
        from composearr.fixer import _fix_undefined_volume

        data = {
            "services": {"app": {"image": "nginx"}},
            "volumes": {"mydata": None},
        }
        issue = LintIssue(
            rule_id="CA702",
            rule_name="undefined-volume-ref",
            severity=Severity.ERROR,
            message="Volume 'mydata' referenced but not defined in volumes section",
            file_path="compose.yaml",
            fix_available=True,
        )
        result = _fix_undefined_volume(data, issue)
        assert result is False  # Already defined

    def test_fix_no_message(self):
        from composearr.fixer import _fix_undefined_volume

        data = {"services": {"app": {}}}
        issue = LintIssue(
            rule_id="CA702",
            rule_name="undefined-volume-ref",
            severity=Severity.ERROR,
            message="",
            file_path="compose.yaml",
        )
        result = _fix_undefined_volume(data, issue)
        assert result is False

    def test_fix_null_volumes_section(self):
        from composearr.fixer import _fix_undefined_volume

        data = {
            "services": {"app": {}},
            "volumes": None,
        }
        issue = LintIssue(
            rule_id="CA702",
            rule_name="undefined-volume-ref",
            severity=Severity.ERROR,
            message="Volume 'mydata' referenced but not defined in volumes section",
            file_path="compose.yaml",
            fix_available=True,
        )
        result = _fix_undefined_volume(data, issue)
        assert result is True
        assert "mydata" in data["volumes"]


# ═══════════════════════════════════════════════════════════════
# EXPLAIN DOCS TESTS
# ═══════════════════════════════════════════════════════════════


class TestVolumeRuleDocs:
    """Ensure RULE_DOCS entries exist for new rules."""

    def test_ca701_has_docs(self):
        from composearr.commands.explain import RULE_DOCS

        assert "CA701" in RULE_DOCS
        doc = RULE_DOCS["CA701"]
        assert "why" in doc
        assert "scenarios" in doc
        assert "fix_examples" in doc

    def test_ca702_has_docs(self):
        from composearr.commands.explain import RULE_DOCS

        assert "CA702" in RULE_DOCS
        doc = RULE_DOCS["CA702"]
        assert "why" in doc
        assert "scenarios" in doc
        assert "fix_examples" in doc


# ═══════════════════════════════════════════════════════════════
# SCORING CATEGORY MAPPING
# ═══════════════════════════════════════════════════════════════


class TestScoringCA7xx:
    """Test that CA7xx rules are categorized correctly."""

    def test_ca7_maps_to_reliability(self):
        from composearr.scoring import _categorize

        assert _categorize("CA701") == "reliability"
        assert _categorize("CA702") == "reliability"


# ═══════════════════════════════════════════════════════════════
# CONFIG TESTS
# ═══════════════════════════════════════════════════════════════


class TestConfigCA7xx:
    """Test that new rules are in config defaults."""

    def test_ca701_in_defaults(self):
        from composearr.config import DEFAULT_RULES

        assert "CA701" in DEFAULT_RULES
        assert DEFAULT_RULES["CA701"] == "info"

    def test_ca702_in_defaults(self):
        from composearr.config import DEFAULT_RULES

        assert "CA702" in DEFAULT_RULES
        assert DEFAULT_RULES["CA702"] == "error"

    def test_rule_name_to_id(self):
        from composearr.config import _RULE_NAME_TO_ID

        assert _RULE_NAME_TO_ID["prefer-named-volumes"] == "CA701"
        assert _RULE_NAME_TO_ID["undefined-volume-ref"] == "CA702"
