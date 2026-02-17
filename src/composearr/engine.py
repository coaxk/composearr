"""Two-pass lint engine with progress reporting."""

from __future__ import annotations

import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from functools import lru_cache
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

# ── Parse cache ──────────────────────────────────────────────
_parse_cache: dict[str, ComposeFile] = {}


def _cached_parse(path: Path) -> ComposeFile:
    """Parse a compose file with caching based on path + mtime."""
    try:
        mtime = path.stat().st_mtime
    except OSError:
        mtime = 0.0
    key = f"{path}:{mtime}"
    if key in _parse_cache:
        return _parse_cache[key]
    cf = parse_compose_file(path)
    _parse_cache[key] = cf
    return cf


def clear_parse_cache() -> None:
    """Clear the parsed compose file cache."""
    _parse_cache.clear()


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

    # Load .composearrignore
    from composearr.ignorefile import load_ignore_file
    ignore_parser = load_ignore_file(root_path)

    # ── Phase 1: Discovery ──────────────────────────────────────
    if progress:
        progress.on_phase_start("discovery", None)

    t0 = time.perf_counter()
    paths, managed = discover_compose_files(
        root_path,
        max_depth=config.max_depth,
        ignore_parser=ignore_parser,
    )
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

        cf = _cached_parse(path)
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

    # ── Phase 3: Per-file rules (parallel) ──────────────────────
    parseable = [cf for cf in result.compose_files if not cf.parse_error]

    if progress:
        progress.on_phase_start("per_file", len(parseable))

    t0 = time.perf_counter()

    def _audit_single_file(cf: ComposeFile) -> list:
        """Run all rules against a single compose file. Thread-safe."""
        if config.honor_suppressions:
            file_ignored, _, line_suppressions = parse_file_suppressions(cf.raw_content)
        else:
            file_ignored = False
            line_suppressions = {}
        if file_ignored:
            return []

        file_issues: list = []
        for rule in rules:
            if rule.scope == Scope.FILE:
                issues = rule.check_file(cf)
                file_issues.extend(_filter_suppressed(issues, line_suppressions))
            elif rule.scope == Scope.SERVICE:
                for svc_name, svc_config in cf.services.items():
                    if config.should_ignore_service(svc_name):
                        continue
                    svc_dict = dict(svc_config) if hasattr(svc_config, "items") else {}
                    issues = rule.check_service(svc_name, svc_dict, cf)
                    file_issues.extend(_filter_suppressed(issues, line_suppressions))
        return file_issues

    # Use parallel execution for multi-file stacks
    if len(parseable) >= 4:
        workers = min(len(parseable), 8)
        with ThreadPoolExecutor(max_workers=workers) as executor:
            futures = {executor.submit(_audit_single_file, cf): i for i, cf in enumerate(parseable)}
            for future in as_completed(futures):
                i = futures[future]
                try:
                    result.issues.extend(future.result())
                except Exception:
                    pass
                if progress:
                    progress.on_progress("per_file", i + 1, str(parseable[i].path.name))
    else:
        for i, cf in enumerate(parseable):
            result.issues.extend(_audit_single_file(cf))
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
        try:
            result.cross_file_issues.extend(rule.check_project(parseable))
        except Exception:
            pass  # Rule failure should not stop the audit
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
