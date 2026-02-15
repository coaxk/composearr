"""Privacy-first opt-in telemetry system.

Principles:
- Opt-in only — never collects without explicit consent
- Anonymous — no personally identifiable information
- Transparent — users can review data before sending
- Easy opt-out — disable anytime via config or CLI flag

What we collect (when opted in):
- Rule hit counts (e.g. CA001: 5, CA201: 3)
- Audit duration (seconds)
- File count scanned
- Error/warning/info counts
- ComposeArr version
- OS platform (win32/linux/darwin)

What we NEVER collect:
- Service names, image names, paths
- IP addresses, hostnames
- Secrets, environment variables
- File contents
- Anything personally identifiable
"""

from __future__ import annotations

import json
import platform
import time
import uuid
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from pathlib import Path

from composearr import __version__

# Telemetry config location
_TELEMETRY_CONFIG = Path.home() / ".composearr" / "telemetry.json"


@dataclass
class TelemetryEvent:
    """A single anonymous telemetry event."""

    event_type: str = "audit"
    version: str = field(default_factory=lambda: __version__)
    platform: str = field(default_factory=lambda: platform.system().lower())
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    duration_seconds: float = 0.0
    files_scanned: int = 0
    error_count: int = 0
    warning_count: int = 0
    info_count: int = 0
    rule_hits: dict[str, int] = field(default_factory=dict)
    session_id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])


def is_telemetry_enabled() -> bool:
    """Check if telemetry is opted in."""
    if not _TELEMETRY_CONFIG.exists():
        return False
    try:
        data = json.loads(_TELEMETRY_CONFIG.read_text(encoding="utf-8"))
        return data.get("enabled", False)
    except Exception:
        return False


def set_telemetry_enabled(enabled: bool) -> None:
    """Set telemetry opt-in preference."""
    _TELEMETRY_CONFIG.parent.mkdir(parents=True, exist_ok=True)
    data = {}
    if _TELEMETRY_CONFIG.exists():
        try:
            data = json.loads(_TELEMETRY_CONFIG.read_text(encoding="utf-8"))
        except Exception:
            pass
    data["enabled"] = enabled
    data["updated_at"] = datetime.now(timezone.utc).isoformat()
    _TELEMETRY_CONFIG.write_text(json.dumps(data, indent=2), encoding="utf-8")


def has_been_prompted() -> bool:
    """Check if user has been prompted about telemetry before."""
    if not _TELEMETRY_CONFIG.exists():
        return False
    try:
        data = json.loads(_TELEMETRY_CONFIG.read_text(encoding="utf-8"))
        return "enabled" in data
    except Exception:
        return False


def record_event(event: TelemetryEvent) -> None:
    """Record a telemetry event to local storage (for review before sending)."""
    if not is_telemetry_enabled():
        return

    events_file = _TELEMETRY_CONFIG.parent / "events.jsonl"
    try:
        with events_file.open("a", encoding="utf-8") as f:
            f.write(json.dumps(asdict(event)) + "\n")
    except Exception:
        pass  # Never let telemetry crash the app


def get_pending_events() -> list[dict]:
    """Get events waiting to be reviewed/sent."""
    events_file = _TELEMETRY_CONFIG.parent / "events.jsonl"
    if not events_file.exists():
        return []
    events = []
    try:
        for line in events_file.read_text(encoding="utf-8").strip().splitlines():
            if line.strip():
                events.append(json.loads(line))
    except Exception:
        pass
    return events


def clear_pending_events() -> None:
    """Clear pending events after review/send."""
    events_file = _TELEMETRY_CONFIG.parent / "events.jsonl"
    if events_file.exists():
        events_file.unlink()


def format_event_for_review(event: dict) -> str:
    """Format a telemetry event for human-readable review."""
    lines = [
        f"  Event: {event.get('event_type', 'audit')}",
        f"  Version: {event.get('version', '?')}",
        f"  Platform: {event.get('platform', '?')}",
        f"  Time: {event.get('timestamp', '?')}",
        f"  Duration: {event.get('duration_seconds', 0):.1f}s",
        f"  Files: {event.get('files_scanned', 0)}",
        f"  Issues: {event.get('error_count', 0)} errors, "
        f"{event.get('warning_count', 0)} warnings, "
        f"{event.get('info_count', 0)} info",
    ]
    rule_hits = event.get("rule_hits", {})
    if rule_hits:
        lines.append("  Rule hits:")
        for rule_id, count in sorted(rule_hits.items()):
            lines.append(f"    {rule_id}: {count}")
    return "\n".join(lines)


def create_event_from_result(result: "AuditResult", duration: float) -> TelemetryEvent:
    """Create a telemetry event from an audit result."""
    from collections import Counter

    rule_hits = Counter(i.rule_id for i in result.all_issues)

    return TelemetryEvent(
        event_type="audit",
        duration_seconds=round(duration, 2),
        files_scanned=result.files_scanned,
        error_count=result.error_count,
        warning_count=result.warning_count,
        info_count=result.info_count,
        rule_hits=dict(rule_hits),
    )
