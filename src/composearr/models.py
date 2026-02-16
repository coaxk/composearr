"""Core data models for ComposeArr."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Protocol, runtime_checkable


class Severity(Enum):
    ERROR = "error"
    WARNING = "warning"
    INFO = "info"


# Severity ordering: lower = more severe
SEVERITY_RANK: dict[Severity, int] = {
    Severity.ERROR: 0,
    Severity.WARNING: 1,
    Severity.INFO: 2,
}


class Scope(Enum):
    SERVICE = "service"
    FILE = "file"
    PROJECT = "project"


@runtime_checkable
class ProgressCallback(Protocol):
    """Protocol for progress reporting during audit."""

    def on_phase_start(self, phase: str, total: int | None) -> None: ...
    def on_progress(self, phase: str, current: int, description: str = "") -> None: ...
    def on_phase_end(self, phase: str) -> None: ...


@dataclass
class ScanTiming:
    """Timing data for each audit phase."""

    discovery_seconds: float = 0.0
    parse_seconds: float = 0.0
    per_file_rules_seconds: float = 0.0
    cross_file_rules_seconds: float = 0.0

    @property
    def total_seconds(self) -> float:
        return (
            self.discovery_seconds
            + self.parse_seconds
            + self.per_file_rules_seconds
            + self.cross_file_rules_seconds
        )


@dataclass
class FormatOptions:
    """Options controlling how output is rendered."""

    min_severity: Severity = Severity.ERROR
    verbose: bool = False
    group_by: str = "rule"  # "rule" | "file" | "severity"


@dataclass
class LintIssue:
    """A single issue found during linting."""

    rule_id: str
    rule_name: str
    severity: Severity
    message: str
    file_path: str
    line: int | None = None
    column: int | None = None
    service: str | None = None
    fix_available: bool = False
    suggested_fix: str | None = None
    learn_more: str | None = None


@dataclass
class PortMapping:
    """A parsed port mapping from a compose file."""

    host_port: int
    container_port: int
    protocol: str = "tcp"
    host_ip: str = "0.0.0.0"
    service: str = ""
    file_path: str = ""


@dataclass
class ComposeFile:
    """A parsed compose file with its metadata."""

    path: Path
    raw_content: str = ""
    data: dict = field(default_factory=dict)
    parse_error: str | None = None

    @property
    def services(self) -> dict:
        if self.data and "services" in self.data and self.data["services"]:
            return dict(self.data["services"])
        return {}


@dataclass
class ScanResult:
    """Results from scanning a directory."""

    compose_files: list[ComposeFile] = field(default_factory=list)
    env_vars: dict[str, str] = field(default_factory=dict)
    issues: list[LintIssue] = field(default_factory=list)
    cross_file_issues: list[LintIssue] = field(default_factory=list)
    timing: ScanTiming = field(default_factory=ScanTiming)
    skipped_managed: dict[str, int] = field(default_factory=dict)
    skipped_managed_paths: dict[str, list[str]] = field(default_factory=dict)

    @property
    def all_issues(self) -> list[LintIssue]:
        return self.issues + self.cross_file_issues

    @property
    def total_services(self) -> int:
        return sum(len(cf.services) for cf in self.compose_files if not cf.parse_error)

    @property
    def error_count(self) -> int:
        return sum(1 for i in self.all_issues if i.severity == Severity.ERROR)

    @property
    def warning_count(self) -> int:
        return sum(1 for i in self.all_issues if i.severity == Severity.WARNING)

    @property
    def info_count(self) -> int:
        return sum(1 for i in self.all_issues if i.severity == Severity.INFO)

    @property
    def fixable_count(self) -> int:
        return sum(1 for i in self.all_issues if i.fix_available)
