"""Tests for privacy-first telemetry system."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest

from composearr.telemetry import (
    TelemetryEvent,
    clear_pending_events,
    format_event_for_review,
    get_pending_events,
    has_been_prompted,
    is_telemetry_enabled,
    record_event,
    set_telemetry_enabled,
)


@pytest.fixture
def telemetry_home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """Redirect telemetry config to temp directory."""
    config_dir = tmp_path / ".composearr"
    config_file = config_dir / "telemetry.json"
    monkeypatch.setattr("composearr.telemetry._TELEMETRY_CONFIG", config_file)
    return config_dir


class TestTelemetryConfig:
    def test_disabled_by_default(self, telemetry_home):
        assert is_telemetry_enabled() is False

    def test_not_prompted_by_default(self, telemetry_home):
        assert has_been_prompted() is False

    def test_enable_telemetry(self, telemetry_home):
        set_telemetry_enabled(True)
        assert is_telemetry_enabled() is True
        assert has_been_prompted() is True

    def test_disable_telemetry(self, telemetry_home):
        set_telemetry_enabled(True)
        set_telemetry_enabled(False)
        assert is_telemetry_enabled() is False
        assert has_been_prompted() is True  # Still been prompted

    def test_creates_config_dir(self, telemetry_home):
        assert not telemetry_home.exists()
        set_telemetry_enabled(False)
        assert telemetry_home.exists()


class TestTelemetryEvent:
    def test_event_defaults(self):
        event = TelemetryEvent()
        assert event.event_type == "audit"
        assert event.files_scanned == 0
        assert event.platform in ("windows", "linux", "darwin")
        assert len(event.session_id) == 12

    def test_event_no_pii(self):
        """Verify events contain no personally identifiable information."""
        event = TelemetryEvent(
            files_scanned=10,
            error_count=3,
            rule_hits={"CA001": 5, "CA201": 3},
        )
        event_dict = json.loads(json.dumps(event.__dict__))
        event_str = json.dumps(event_dict)
        # Should not contain paths, IPs, hostnames, service names
        assert "C:" not in event_str
        assert "/home" not in event_str
        assert "sonarr" not in event_str.lower()
        assert "radarr" not in event_str.lower()


class TestEventRecording:
    def test_records_when_enabled(self, telemetry_home):
        set_telemetry_enabled(True)
        event = TelemetryEvent(files_scanned=5)
        record_event(event)
        events = get_pending_events()
        assert len(events) == 1
        assert events[0]["files_scanned"] == 5

    def test_ignores_when_disabled(self, telemetry_home):
        set_telemetry_enabled(False)
        event = TelemetryEvent(files_scanned=5)
        record_event(event)
        events = get_pending_events()
        assert len(events) == 0

    def test_multiple_events(self, telemetry_home):
        set_telemetry_enabled(True)
        record_event(TelemetryEvent(files_scanned=1))
        record_event(TelemetryEvent(files_scanned=2))
        events = get_pending_events()
        assert len(events) == 2

    def test_clear_events(self, telemetry_home):
        set_telemetry_enabled(True)
        record_event(TelemetryEvent())
        clear_pending_events()
        events = get_pending_events()
        assert len(events) == 0


class TestEventReview:
    def test_format_for_review(self):
        event = {
            "event_type": "audit",
            "version": "0.1.0",
            "platform": "linux",
            "timestamp": "2026-02-16T10:00:00Z",
            "duration_seconds": 2.5,
            "files_scanned": 10,
            "error_count": 3,
            "warning_count": 5,
            "info_count": 2,
            "rule_hits": {"CA001": 3, "CA201": 2},
        }
        output = format_event_for_review(event)
        assert "audit" in output
        assert "2.5s" in output
        assert "10" in output
        assert "CA001: 3" in output
        assert "CA201: 2" in output
        # Should NOT contain any path or PII
        assert "/home" not in output
        assert "C:" not in output
