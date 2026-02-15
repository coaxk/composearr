"""Two-pass lint engine with progress reporting."""

from __future__ import annotations

import time
from pathlib import Path

from composearr.config import Config, load_config, parse_file_suppressions
from composearr.models import (
    ComposeFile,
    ProgressCallback,
    ScanResult,
    ScanTiming,
    Scope,
)
from composearr.rules.base import get_all_rules
from composearr.scanner.discovery import discover_compose_files
from composearr.scanner.env_resolver import discover_env_files, load_env_file
from composearr.scanner.parser import parse_compose_file


def run_audit(
    root_path: Path,
    config: Config | None = None,
    progress: ProgressCallback | None = None,
) -> ScanResult:
    """Run the full two-pass audit on a directory."""
    if config is None:
        config = load_config(root_path)

    result = ScanResult()
    timing = ScanTiming()

    # ── Phase 1: Discovery ──────────────────────────────────────
    if progress:
        progress.on_phase_start("discovery", None)

    t0 = time.perf_counter()
    paths, managed = discover_compose_files(root_path)
    timing.discovery_seconds = time.perf_counter() - t0

    result.skipped_managed = {name: len(files) for name, files in managed.items()}
    result.skipped_managed_paths = {
        name: [str(p.relative_to(root_path)) for p in files]
        for name, files in managed.items()
    }

    if progress:
        progress.on_phase_end("discovery")

    # ── Phase 2: Parsing ────────────────────────────────────────
    if progress:
        progress.on_phase_start("parse", len(paths))

    t0 = time.perf_counter()
    for i, path in enumerate(paths):
        try:
            rel = str(path.relative_to(root_path))
        except ValueError:
            rel = str(path)

        if config.should_ignore_file(rel):
            if progress:
                progress.on_progress("parse", i + 1, rel)
            continue

        cf = parse_compose_file(path)
        result.compose_files.append(cf)

        if progress:
            progress.on_progress("parse", i + 1, rel)

    timing.parse_seconds = time.perf_counter() - t0

    if progress:
        progress.on_phase_end("parse")

    # Load .env files from root
    env_files = discover_env_files(root_path)
    for env_path in env_files:
        result.env_vars.update(load_env_file(env_path))

    # Get enabled rules only
    all_rules = get_all_rules()
    rules = [r for r in all_rules if config.is_rule_enabled(r.id)]

    # Apply severity overrides from config
    for rule in rules:
        sev = config.get_severity(rule.id)
        if sev:
            rule.severity = sev

    # ── Phase 3: Per-file rules ─────────────────────────────────
    parseable = [cf for cf in result.compose_files if not cf.parse_error]

    if progress:
        progress.on_phase_start("per_file", len(parseable))

    t0 = time.perf_counter()
    for i, cf in enumerate(parseable):
        # Parse inline suppressions
        file_ignored, _, line_suppressions = parse_file_suppressions(cf.raw_content)
        if file_ignored:
            if progress:
                progress.on_progress("per_file", i + 1, str(cf.path.name))
            continue

        for rule in rules:
            if rule.scope == Scope.FILE:
                issues = rule.check_file(cf)
                result.issues.extend(_filter_suppressed(issues, line_suppressions))
            elif rule.scope == Scope.SERVICE:
                for svc_name, svc_config in cf.services.items():
                    if config.should_ignore_service(svc_name):
                        continue
                    svc_dict = dict(svc_config) if hasattr(svc_config, "items") else {}
                    issues = rule.check_service(svc_name, svc_dict, cf)
                    result.issues.extend(_filter_suppressed(issues, line_suppressions))

        if progress:
            progress.on_progress("per_file", i + 1, str(cf.path.name))

    timing.per_file_rules_seconds = time.perf_counter() - t0

    if progress:
        progress.on_phase_end("per_file")

    # ── Phase 4: Cross-file rules ───────────────────────────────
    project_rules = [r for r in rules if r.scope == Scope.PROJECT]

    if progress:
        progress.on_phase_start("cross_file", len(project_rules))

    t0 = time.perf_counter()
    for i, rule in enumerate(project_rules):
        result.cross_file_issues.extend(rule.check_project(parseable))
        if progress:
            progress.on_progress("cross_file", i + 1, rule.id)

    timing.cross_file_rules_seconds = time.perf_counter() - t0

    if progress:
        progress.on_phase_end("cross_file")

    result.timing = timing
    return result


def _filter_suppressed(
    issues: list,
    line_suppressions: dict[int, set[str]],
) -> list:
    """Remove issues that are suppressed by inline comments."""
    filtered = []
    for issue in issues:
        if issue.line and issue.line in line_suppressions:
            suppressed_ids = line_suppressions[issue.line]
            if issue.rule_id in suppressed_ids or issue.rule_name in suppressed_ids:
                continue
        filtered.append(issue)
    return filtered
