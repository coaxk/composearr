"""Rich console formatter — Beszel-inspired design, summary-first."""

from __future__ import annotations

import io
import os
import sys
from collections import Counter, defaultdict
from pathlib import Path

from rich import box
from rich.console import Console
from rich.padding import Padding
from rich.panel import Panel
from rich.style import Style
from rich.table import Table
from rich.text import Text

from composearr import __version__
from composearr.models import (
    ComposeFile,
    FormatOptions,
    LintIssue,
    ScanResult,
    Severity,
    SEVERITY_RANK,
)

# ── Beszel-inspired color tokens ──────────────────────────────────
C_BORDER = "#27272a"
C_TEXT = "#fafafa"
C_MUTED = "#71717a"
C_DIM = "#3f3f46"
C_OK = "#22c55e"
C_WARN = "#f59e0b"
C_ERR = "#ef4444"
C_INFO = "#3b82f6"
C_TEAL = "#2dd4bf"


_stdout_wrapped = False


def make_console() -> Console:
    """Create a Console that works on Windows with Unicode."""
    global _stdout_wrapped
    if os.name == "nt" and not _stdout_wrapped:
        try:
            sys.stdout = io.TextIOWrapper(
                sys.stdout.buffer, encoding="utf-8", errors="replace"
            )
            _stdout_wrapped = True
        except Exception:
            pass  # Already wrapped or buffer unavailable
    return Console(force_terminal=True, color_system="truecolor")


def _muted(text: str) -> str:
    return f"[{C_MUTED}]{text}[/]"


def _dim(text: str) -> str:
    return f"[{C_DIM}]{text}[/]"


def _ok(text: str) -> str:
    return f"[{C_OK}]{text}[/]"


def _severity_color(severity: Severity) -> str:
    return {Severity.ERROR: C_ERR, Severity.WARNING: C_WARN, Severity.INFO: C_INFO}[severity]


def _severity_dot(severity: Severity) -> str:
    return f"[{_severity_color(severity)}]\u25cf[/]"


def _rel_path(file_path: str, root_path: str) -> str:
    try:
        return str(Path(file_path).relative_to(root_path))
    except ValueError:
        return file_path


class ConsoleFormatter:
    """Format scan results for Rich terminal output."""

    def __init__(self, console: Console | None = None) -> None:
        self.console = console or make_console()

    def render(
        self,
        result: ScanResult,
        root_path: str = ".",
        options: FormatOptions | None = None,
    ) -> None:
        """Render the full audit output."""
        opts = options or FormatOptions()

        self._header()
        self._summary_section(result, root_path, opts)

        if opts.group_by == "file":
            self._render_by_file(result, root_path, opts)
        elif opts.group_by == "rule":
            self._render_by_rule(result, root_path, opts)
        else:
            self._render_by_severity(result, root_path, opts)

        self._footer(result, opts)

    # ── Header ──────────────────────────────────────────────────

    def _header(self) -> None:
        left = Text.from_markup(
            f"  [bold {C_TEAL}]\u25c6[/] [bold]composearr[/]  {_muted(f'v{__version__}')}"
        )
        self.console.print(Panel(
            left,
            border_style=Style(color=C_BORDER),
            box=box.HORIZONTALS,
            padding=(0, 0),
        ))
        self.console.print()

    # ── Summary Section (always shown first) ────────────────────

    def _summary_section(
        self, result: ScanResult, root_path: str, opts: FormatOptions | None = None,
    ) -> None:
        opts = opts or FormatOptions()
        files = len(result.compose_files)
        services = result.total_services
        errors = result.error_count
        warnings = result.warning_count
        infos = result.info_count
        scan_time = result.timing.total_seconds

        # Scan stats
        time_str = f" in {scan_time:.2f}s" if scan_time > 0 else ""
        self.console.print(
            f"  Scanned [bold {C_TEXT}]{files}[/] files, "
            f"[bold {C_TEXT}]{services}[/] services{_muted(time_str)}"
        )

        # Skipped managed platforms
        for platform, count in result.skipped_managed.items():
            self.console.print(
                f"  [{C_INFO}]\u2139[/]  [{C_TEXT}]Detected {platform}-managed stack[/]"
            )
            self.console.print(
                f"     {_muted(f'Skipped {count} duplicate compose files \u2014 these are copies managed by {platform}')}"
            )
            self.console.print(
                f"     {_muted(f'Scanning {files} original compose files from your stack')}"
            )
            if opts.verbose and platform in result.skipped_managed_paths:
                skipped = result.skipped_managed_paths[platform]
                shown = skipped[:5]
                for sp in shown:
                    self.console.print(f"     {_dim(f'\u2022 {sp}')}")
                if len(skipped) > 5:
                    self.console.print(f"     {_dim(f'... and {len(skipped) - 5} more')}")

        # Parse errors
        parse_errors = [cf for cf in result.compose_files if cf.parse_error]
        if parse_errors:
            self.console.print(
                f"  [{C_WARN}]\u25cf[/] {_muted(f'{len(parse_errors)} files failed to parse')}"
            )
            for cf in parse_errors:
                rel = _rel_path(str(cf.path), root_path)
                self.console.print(
                    f"     [{C_WARN}]\u2022[/] [{C_TEXT}]{rel}[/]  {_muted(cf.parse_error)}"
                )

        self.console.print()

        # Issue counts
        self.console.print(
            f"  [{C_ERR}]\u25cf {errors} error{'s' if errors != 1 else ''}[/]    "
            f"[{C_WARN}]\u25cf {warnings} warning{'s' if warnings != 1 else ''}[/]    "
            f"[{C_INFO}]\u25cf {infos} info[/]"
        )

        fixable = result.fixable_count
        if fixable:
            self.console.print(f"  {_ok(f'{fixable} auto-fixable')} {_muted('\u2192')} [{C_TEAL}]composearr audit --fix[/]")

        self.console.print()

        # Top offending rules
        if result.all_issues:
            rule_counts: Counter[str] = Counter()
            for issue in result.all_issues:
                rule_counts[f"{issue.rule_id} ({issue.rule_name})"] += 1

            self.console.print(f"  {_muted('By rule:')}")
            for rule_label, count in rule_counts.most_common(5):
                self.console.print(f"    {_muted(f'{count:>3}')}  {rule_label}")
            self.console.print()

        # Clean file count
        files_with_issues = {i.file_path for i in result.all_issues}
        clean_count = files - len(files_with_issues) - len(parse_errors)
        if clean_count > 0:
            self.console.print(f"  {_ok(f'\u2713 {clean_count} files passed all checks')}")
            self.console.print()

    # ── Render by Severity (default) ────────────────────────────

    def _render_by_severity(
        self, result: ScanResult, root_path: str, opts: FormatOptions
    ) -> None:
        all_issues = result.all_issues
        min_rank = SEVERITY_RANK[opts.min_severity]

        for sev in [Severity.ERROR, Severity.WARNING, Severity.INFO]:
            issues = [i for i in all_issues if i.severity == sev]
            if not issues:
                continue

            if SEVERITY_RANK[sev] <= min_rank:
                # Show these issues
                color = _severity_color(sev)
                self.console.print(
                    f"  [{color}]\u2501\u2501[/] [{color}]{sev.value.upper()}S ({len(issues)})[/]"
                )
                self.console.print()

                for issue in issues:
                    cf = self._find_compose_file(result, issue.file_path)
                    self._render_issue(issue, cf, root_path, opts.verbose)
            else:
                # Collapsed hint
                color = _severity_color(sev)
                self.console.print(
                    f"  {_muted(f'{len(issues)} {sev.value}s hidden')} "
                    f"{_muted('\u2192')} [{C_TEAL}]--severity {sev.value}[/]"
                )

        # Cross-file issues (always show if above threshold)
        cross = [i for i in result.cross_file_issues if SEVERITY_RANK[i.severity] <= min_rank]
        if cross:
            self._cross_file_panel(cross, root_path, opts.verbose)

    # ── Render by File ──────────────────────────────────────────

    def _render_by_file(
        self, result: ScanResult, root_path: str, opts: FormatOptions
    ) -> None:
        min_rank = SEVERITY_RANK[opts.min_severity]
        by_file: dict[str, list[LintIssue]] = defaultdict(list)
        for issue in result.issues:
            by_file[issue.file_path].append(issue)

        for file_path in sorted(by_file.keys()):
            issues = [i for i in by_file[file_path] if SEVERITY_RANK[i.severity] <= min_rank]
            if not issues:
                continue

            rel = _rel_path(file_path, root_path)
            self.console.print(f"  [{C_TEXT}]{rel}[/]")
            self.console.print()

            cf = self._find_compose_file(result, file_path)
            for issue in issues:
                self._render_issue(issue, cf, root_path, opts.verbose)

        # Cross-file
        cross = [i for i in result.cross_file_issues if SEVERITY_RANK[i.severity] <= min_rank]
        if cross:
            self._cross_file_panel(cross, root_path, opts.verbose)

    # ── Render by Rule ──────────────────────────────────────────

    def _render_by_rule(
        self, result: ScanResult, root_path: str, opts: FormatOptions
    ) -> None:
        min_rank = SEVERITY_RANK[opts.min_severity]
        by_rule: dict[str, list[LintIssue]] = defaultdict(list)
        for issue in result.all_issues:
            by_rule[issue.rule_id].append(issue)

        for rule_id in sorted(by_rule.keys()):
            issues = [i for i in by_rule[rule_id] if SEVERITY_RANK[i.severity] <= min_rank]
            if not issues:
                continue

            first = issues[0]
            color = _severity_color(first.severity)
            self.console.print(
                f"  [{color}]\u2501\u2501[/] [{color}]{rule_id}[/] {first.rule_name} "
                f"{_muted(f'({len(issues)} issues)')}"
            )
            self.console.print()

            # Sub-group by file for better readability
            by_file: dict[str, list[LintIssue]] = defaultdict(list)
            for issue in issues:
                by_file[issue.file_path].append(issue)

            for file_path in sorted(by_file.keys()):
                rel = _rel_path(file_path, root_path)
                file_issues = by_file[file_path]
                if len(by_file) > 1:
                    self.console.print(f"    {_dim(rel)}")
                cf = self._find_compose_file(result, file_path)
                for issue in file_issues:
                    self._render_issue(issue, cf, root_path, opts.verbose)
                if len(by_file) > 1:
                    self.console.print()

    # ── Issue Rendering ─────────────────────────────────────────

    def _render_issue(
        self,
        issue: LintIssue,
        compose_file: ComposeFile | None,
        root_path: str,
        verbose: bool,
    ) -> None:
        sev_color = _severity_color(issue.severity)
        rel = _rel_path(issue.file_path, root_path)

        if verbose and issue.line and compose_file and compose_file.raw_content:
            # Full context mode
            lines = compose_file.raw_content.splitlines()
            if 0 < issue.line <= len(lines):
                self.console.print(f"    {_dim(f'{issue.line:>3}')}  {lines[issue.line - 1]}")

            svc_str = f" ({issue.service})" if issue.service else ""
            # Use Padding for proper wrap indentation (10 = "    ...  " prefix width)
            header = Text.from_markup(
                f"[{sev_color}]\u25cf[/] [{sev_color}]{issue.rule_id}[/]  "
                f"{issue.message}{_muted(svc_str)}"
            )
            self.console.print(Padding(header, (0, 0, 0, 9)))
            if issue.suggested_fix:
                fix_text = Text.from_markup(
                    f"{_ok('\u2192')} [{C_TEAL}]{issue.suggested_fix}[/]"
                )
                self.console.print(Padding(fix_text, (0, 0, 0, 9)))
            if issue.learn_more:
                self.console.print(Padding(
                    Text.from_markup(_muted(issue.learn_more)), (0, 0, 0, 9)
                ))
            self.console.print()
        else:
            # Compact mode — use Padding for proper continuation line indentation
            svc_str = f" [bold {C_TEAL}]{issue.service}[/]" if issue.service else ""
            line_str = f":{issue.line}" if issue.line else ""
            loc = _dim(f"  {rel}{line_str}")
            text = Text.from_markup(
                f"[{sev_color}]\u25cf[/] [{sev_color}]{issue.rule_id}[/]  "
                f"{issue.message}{svc_str}{loc}"
            )
            self.console.print(Padding(text, (0, 0, 0, 4)))

    def _cross_file_panel(
        self, issues: list[LintIssue], root_path: str, verbose: bool
    ) -> None:
        from rich.console import Group

        renderables = []
        for issue in issues:
            sev_color = _severity_color(issue.severity)
            header = Text.from_markup(
                f"  [{sev_color}]\u25cf[/] [{sev_color}]{issue.rule_id}[/]  {issue.message}"
            )
            renderables.append(header)
            if issue.suggested_fix:
                fix_text = Text.from_markup(
                    f"{_ok('\u2192')} [{C_TEAL}]{issue.suggested_fix}[/]"
                )
                renderables.append(Padding(fix_text, (0, 0, 0, 7)))
            if issue.learn_more:
                renderables.append(Padding(
                    Text.from_markup(_muted(issue.learn_more)), (0, 0, 0, 7)
                ))
            renderables.append(Text(""))  # spacing

        self.console.print()
        self.console.print(Panel(
            Group(*renderables),
            title=f"[{C_MUTED}]cross-file[/]",
            title_align="left",
            border_style=Style(color=C_BORDER),
            box=box.ROUNDED,
            padding=(1, 2),
        ))
        self.console.print()

    # ── Footer ──────────────────────────────────────────────────

    def _footer(self, result: ScanResult, opts: FormatOptions) -> None:
        hints: list[str] = []

        if opts.min_severity == Severity.ERROR and result.warning_count > 0:
            hints.append(f"[{C_TEAL}]--severity warning[/] {_muted('to see all warnings')}")
        if opts.min_severity != Severity.INFO and result.info_count > 0:
            hints.append(f"[{C_TEAL}]--severity info[/] {_muted('to see everything')}")
        if not opts.verbose:
            hints.append(f"[{C_TEAL}]--verbose[/] {_muted('for full file context')}")
        if opts.group_by == "rule":
            hints.append(f"[{C_TEAL}]--group-by file[/] {_muted('to group by file')}")
        elif opts.group_by != "rule":
            hints.append(f"[{C_TEAL}]--group-by rule[/] {_muted('to group by rule')}")

        if hints:
            self.console.print(f"  {_muted('Try:')}  {'  \u2022  '.join(hints)}")
            self.console.print()

    # ── Helpers ──────────────────────────────────────────────────

    def _find_compose_file(self, result: ScanResult, file_path: str) -> ComposeFile | None:
        return next((f for f in result.compose_files if str(f.path) == file_path), None)
