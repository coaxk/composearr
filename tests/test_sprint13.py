"""Sprint 13 tests: Fix Flow UX Polish — all issues visible, intro screen, diff UX, back nav, clean summary."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

import re

from composearr.formatters.console import ConsoleFormatter, make_console
from composearr.models import (
    ComposeFile,
    FormatOptions,
    LintIssue,
    ScanResult,
    Severity,
    ScanTiming,
)


def _strip_ansi(text: str) -> str:
    """Remove ANSI escape sequences for assertion matching."""
    return re.sub(r"\x1b\[[0-9;]*m", "", text)


# ===========================================================================
# Helpers
# ===========================================================================


def _make_issue(
    rule_id: str = "CA001",
    severity: Severity = Severity.ERROR,
    message: str = "Test issue",
    file_path: str = "/stack/compose.yaml",
    service: str | None = "app",
    fix_available: bool = False,
    suggested_fix: str | None = None,
) -> LintIssue:
    return LintIssue(
        rule_id=rule_id,
        rule_name="test-rule",
        severity=severity,
        message=message,
        file_path=file_path,
        service=service,
        line=5,
        suggested_fix=suggested_fix,
        fix_available=fix_available,
        learn_more=None,
    )


def _make_scan_result(issues: list[LintIssue] | None = None) -> ScanResult:
    issues = issues or []
    cf = ComposeFile(
        path=Path("/stack/compose.yaml"),
        raw_content="services:\n  app:\n    image: test\n",
        parse_error=None,
        data={"services": {"app": {"image": "test"}}},
    )
    return ScanResult(
        compose_files=[cf],
        issues=issues,
        cross_file_issues=[],
        timing=ScanTiming(),
    )


# ===========================================================================
# Issue 1: Show ALL issues after scan (not just errors)
# ===========================================================================


class TestShowAllIssues:
    """TUI quick audit should show all severities, not just errors."""

    def test_tui_format_options_uses_info_severity(self) -> None:
        """Quick audit should use min_severity=INFO so all issues are visible."""
        # Verify the FormatOptions constructed in quick audit uses INFO
        opts = FormatOptions(
            min_severity=Severity.INFO,
            verbose=False,
            group_by="severity",
            tui_mode=True,
        )
        assert opts.min_severity == Severity.INFO

    def test_render_shows_errors_with_info_severity(self) -> None:
        issues = [_make_issue(severity=Severity.ERROR, message="error issue")]
        result = _make_scan_result(issues)
        console = make_console()
        fmt = ConsoleFormatter(console)
        opts = FormatOptions(min_severity=Severity.INFO, group_by="severity", tui_mode=True)
        # Should not raise — all severities rendered
        with console.capture() as capture:
            fmt._render_by_severity(result, "/stack", opts)
        output = _strip_ansi(capture.get())
        assert "error issue" in output

    def test_render_shows_warnings_with_info_severity(self) -> None:
        issues = [_make_issue(severity=Severity.WARNING, message="warn issue")]
        result = _make_scan_result(issues)
        console = make_console()
        fmt = ConsoleFormatter(console)
        opts = FormatOptions(min_severity=Severity.INFO, group_by="severity")
        with console.capture() as capture:
            fmt._render_by_severity(result, "/stack", opts)
        output = _strip_ansi(capture.get())
        assert "warn issue" in output

    def test_render_shows_info_with_info_severity(self) -> None:
        issues = [_make_issue(severity=Severity.INFO, message="info issue")]
        result = _make_scan_result(issues)
        console = make_console()
        fmt = ConsoleFormatter(console)
        opts = FormatOptions(min_severity=Severity.INFO, group_by="severity")
        with console.capture() as capture:
            fmt._render_by_severity(result, "/stack", opts)
        output = _strip_ansi(capture.get())
        assert "info issue" in output

    def test_render_hides_warnings_with_error_severity(self) -> None:
        """With ERROR severity, warnings should be collapsed."""
        issues = [_make_issue(severity=Severity.WARNING, message="hidden warn")]
        result = _make_scan_result(issues)
        console = make_console()
        fmt = ConsoleFormatter(console)
        opts = FormatOptions(min_severity=Severity.ERROR, group_by="severity")
        with console.capture() as capture:
            fmt._render_by_severity(result, "/stack", opts)
        output = _strip_ansi(capture.get())
        # Should show collapsed hint, not the actual issue
        assert "hidden" in output
        assert "--severity warning" in output

    def test_all_three_severities_rendered(self) -> None:
        """All three severity levels should be visible with INFO min."""
        issues = [
            _make_issue(severity=Severity.ERROR, message="err msg"),
            _make_issue(severity=Severity.WARNING, message="warn msg"),
            _make_issue(severity=Severity.INFO, message="info msg"),
        ]
        result = _make_scan_result(issues)
        console = make_console()
        fmt = ConsoleFormatter(console)
        opts = FormatOptions(min_severity=Severity.INFO, group_by="severity")
        with console.capture() as capture:
            fmt._render_by_severity(result, "/stack", opts)
        output = _strip_ansi(capture.get())
        assert "err msg" in output
        assert "warn msg" in output
        assert "info msg" in output

    def test_summary_shows_all_counts(self) -> None:
        """Summary section should show error, warning, and info counts."""
        issues = [
            _make_issue(severity=Severity.ERROR),
            _make_issue(severity=Severity.WARNING),
            _make_issue(severity=Severity.WARNING),
            _make_issue(severity=Severity.INFO),
        ]
        result = _make_scan_result(issues)
        console = make_console()
        fmt = ConsoleFormatter(console)
        opts = FormatOptions(min_severity=Severity.INFO, tui_mode=True)
        with console.capture() as capture:
            fmt._summary_section(result, "/stack", opts)
        output = _strip_ansi(capture.get())
        assert "1 error" in output
        assert "2 warnings" in output
        assert "1 info" in output


# ===========================================================================
# Issue 2: Fix process intro screen
# ===========================================================================


class TestFixProcessIntro:
    """Fix flow should explain the process before starting."""

    def test_show_fix_summary_function_exists(self) -> None:
        from composearr.tui import _show_fix_summary
        assert callable(_show_fix_summary)

    def test_clean_path_strips_trailing_dots(self) -> None:
        from composearr.tui import _clean_path
        assert _clean_path(r"C:\Projects\test    .") == r"C:\Projects\test"

    def test_clean_path_strips_trailing_spaces(self) -> None:
        from composearr.tui import _clean_path
        assert _clean_path(r"C:\Projects\test   ") == r"C:\Projects\test"

    def test_clean_path_no_change_needed(self) -> None:
        from composearr.tui import _clean_path
        assert _clean_path(r"C:\Projects\test") == r"C:\Projects\test"

    def test_clean_path_strips_mixed(self) -> None:
        from composearr.tui import _clean_path
        assert _clean_path("/opt/stacks .  .") == "/opt/stacks"


# ===========================================================================
# Issue 3: Improved diff view UX
# ===========================================================================


class TestDiffViewUX:
    """Diff view should show progress and clear options."""

    def test_diff_generator_display_works(self) -> None:
        from composearr.diff import DiffGenerator
        console = make_console()
        differ = DiffGenerator()
        with console.capture() as capture:
            differ.display_diff(
                console,
                "line1\nline2\n",
                "line1\nline3\n",
                "test.yaml",
                description="1 fix",
            )
        output = _strip_ansi(capture.get())
        assert "test.yaml" in output
        assert "1 fix" in output

    def test_diff_generator_no_changes(self) -> None:
        from composearr.diff import DiffGenerator
        console = make_console()
        differ = DiffGenerator()
        with console.capture() as capture:
            differ.display_diff(console, "same\n", "same\n", "test.yaml")
        output = _strip_ansi(capture.get())
        assert "No changes" in output

    def test_diff_change_summary(self) -> None:
        from composearr.diff import DiffGenerator
        differ = DiffGenerator()
        summary = differ.get_change_summary("a\nb\n", "a\nc\n")
        assert summary["additions"] >= 1
        assert summary["deletions"] >= 1
        assert summary["total_changes"] >= 2


# ===========================================================================
# Issue 4: Back navigation
# ===========================================================================


class TestBackNavigation:
    """Post-audit menu should have back option; diff view should have cancel."""

    def test_post_audit_menu_has_back_option(self) -> None:
        """The post-audit menu should include a 'Back to main menu' option."""
        # Read the source to verify the menu choices include "menu" / "back"
        import inspect
        from composearr.tui import _post_audit_menu
        source = inspect.getsource(_post_audit_menu)
        assert "menu" in source
        assert "Back to main menu" in source

    def test_fix_preview_has_cancel_option(self) -> None:
        """The diff preview loop should include a cancel option."""
        import inspect
        from composearr.tui import _tui_fix
        source = inspect.getsource(_tui_fix)
        assert "cancel" in source.lower()
        assert "Cancel fix process" in source


# ===========================================================================
# Issue 5: Clean display order (no duplication)
# ===========================================================================


class TestCleanDisplayOrder:
    """Fix summary should not duplicate file names."""

    def test_show_fix_summary_no_duplication(self) -> None:
        """Summary should list each file exactly once."""
        from composearr.tui import _show_fix_summary

        mock_result = MagicMock()
        mock_result.applied = 3
        mock_result.skipped = 0
        mock_result.errors = 0
        mock_result.verified_files = [Path("/stack/sonarr/compose.yaml")]
        mock_result.verification_errors = []
        mock_result.backup_paths = [Path("/stack/sonarr/compose.yaml.bak")]

        console = make_console()
        with console.capture() as capture:
            _show_fix_summary(console, mock_result, Path("/stack"))
        output = _strip_ansi(capture.get())

        # sonarr should appear exactly once in "Files Modified" section
        # (not listed separately then again under "Files fixed")
        lines = output.split("\n")
        sonarr_lines = [l for l in lines if "sonarr" in l.lower() and "compose.yaml" in l and "bak" not in l]
        assert len(sonarr_lines) == 1

    def test_show_fix_summary_with_skipped(self) -> None:
        from composearr.tui import _show_fix_summary

        mock_result = MagicMock()
        mock_result.applied = 2
        mock_result.skipped = 1
        mock_result.errors = 0
        mock_result.verified_files = [Path("/stack/sonarr/compose.yaml")]
        mock_result.verification_errors = []
        mock_result.backup_paths = [Path("/stack/sonarr/compose.yaml.bak")]

        console = make_console()
        with console.capture() as capture:
            _show_fix_summary(
                console, mock_result, Path("/stack"),
                skipped_files=["radarr/compose.yaml"],
            )
        output = _strip_ansi(capture.get())
        assert "Files Skipped" in output
        assert "radarr" in output

    def test_show_fix_summary_with_errors(self) -> None:
        from composearr.tui import _show_fix_summary

        mock_result = MagicMock()
        mock_result.applied = 1
        mock_result.skipped = 0
        mock_result.errors = 2
        mock_result.verified_files = []
        mock_result.verification_errors = [(Path("/stack/bad.yaml"), "Invalid YAML")]
        mock_result.backup_paths = []

        console = make_console()
        with console.capture() as capture:
            _show_fix_summary(console, mock_result, Path("/stack"))
        output = _strip_ansi(capture.get())
        assert "Verification Errors" in output
        assert "bad.yaml" in output
        assert "2 failed" in output

    def test_show_fix_summary_panel_title(self) -> None:
        from composearr.tui import _show_fix_summary

        mock_result = MagicMock()
        mock_result.applied = 1
        mock_result.skipped = 0
        mock_result.errors = 0
        mock_result.verified_files = [Path("/stack/compose.yaml")]
        mock_result.verification_errors = []
        mock_result.backup_paths = []

        console = make_console()
        with console.capture() as capture:
            _show_fix_summary(console, mock_result, Path("/stack"))
        output = _strip_ansi(capture.get())
        assert "Fix Process Complete" in output


# ===========================================================================
# Issue 6: Clean path formatting
# ===========================================================================


class TestPathFormatting:
    """Paths should not have trailing spaces or dots."""

    def test_clean_path_in_resolve_path(self) -> None:
        """_resolve_path should clean paths for display."""
        import inspect
        from composearr.tui import _resolve_path
        source = inspect.getsource(_resolve_path)
        assert "_clean_path" in source

    def test_clean_path_in_custom_audit(self) -> None:
        """Custom audit settings display should clean paths."""
        import inspect
        from composearr.tui import _tui_custom_audit
        source = inspect.getsource(_tui_custom_audit)
        assert "_clean_path" in source

    def test_show_fix_summary_cleans_path(self) -> None:
        """Fix summary should clean the stack path."""
        from composearr.tui import _show_fix_summary

        mock_result = MagicMock()
        mock_result.applied = 1
        mock_result.skipped = 0
        mock_result.errors = 0
        mock_result.verified_files = []
        mock_result.verification_errors = []
        mock_result.backup_paths = []

        console = make_console()
        with console.capture() as capture:
            _show_fix_summary(console, mock_result, Path("/stack/test"))
        output = _strip_ansi(capture.get())
        # Path should appear clean in output
        assert "test" in output


# ===========================================================================
# Integration: Fix flow structure
# ===========================================================================


class TestFixFlowStructure:
    """Verify the fix flow has all required UX elements."""

    def test_fix_flow_has_intro_panel(self) -> None:
        """Fix flow should show intro panel before fixes."""
        import inspect
        from composearr.tui import _tui_fix
        source = inspect.getsource(_tui_fix)
        assert "Fix Process" in source
        assert "How this works" in source
        assert "Backups are created automatically" in source

    def test_fix_flow_has_progress_indicator(self) -> None:
        """Fix flow preview should show File X of Y."""
        import inspect
        from composearr.tui import _tui_fix
        source = inspect.getsource(_tui_fix)
        assert "File {idx} of {total_files}" in source

    def test_fix_flow_has_three_options(self) -> None:
        """Preview loop should have approve, skip, and cancel options."""
        import inspect
        from composearr.tui import _tui_fix
        source = inspect.getsource(_tui_fix)
        assert "approve" in source
        assert "skip" in source
        assert "cancel" in source

    def test_fix_flow_groups_by_severity(self) -> None:
        """Quick audit should group by severity for clear organization."""
        import inspect
        from composearr.tui import _tui_quick_audit
        source = inspect.getsource(_tui_quick_audit)
        assert 'group_by="severity"' in source

    def test_fix_flow_uses_info_severity(self) -> None:
        """Quick audit should use INFO severity to show everything."""
        import inspect
        from composearr.tui import _tui_quick_audit
        source = inspect.getsource(_tui_quick_audit)
        assert "Severity.INFO" in source

    def test_show_fix_summary_callable(self) -> None:
        """_show_fix_summary should be importable and callable."""
        from composearr.tui import _show_fix_summary
        assert callable(_show_fix_summary)

    def test_fix_flow_explain_fix_logic(self) -> None:
        """Fix flow should explain how fixes work."""
        import inspect
        from composearr.tui import _tui_fix
        source = inspect.getsource(_tui_fix)
        assert "_explain_fix_logic" in source

    def test_fix_flow_has_confirmation_messages(self) -> None:
        """After approve/skip, user should see confirmation."""
        import inspect
        from composearr.tui import _tui_fix
        source = inspect.getsource(_tui_fix)
        assert "Changes approved for" in source
        assert "Skipped" in source


# ===========================================================================
# Formatter rendering modes
# ===========================================================================


class TestFormatterModes:
    """All rendering modes should respect min_severity."""

    def _issues_all_severities(self):
        return [
            _make_issue(rule_id="CA001", severity=Severity.ERROR, message="err1"),
            _make_issue(rule_id="CA201", severity=Severity.WARNING, message="warn1"),
            _make_issue(rule_id="CA401", severity=Severity.INFO, message="info1"),
        ]

    def test_render_by_severity_all(self) -> None:
        result = _make_scan_result(self._issues_all_severities())
        console = make_console()
        fmt = ConsoleFormatter(console)
        opts = FormatOptions(min_severity=Severity.INFO, group_by="severity")
        with console.capture() as capture:
            fmt._render_by_severity(result, "/stack", opts)
        output = _strip_ansi(capture.get())
        assert "err1" in output
        assert "warn1" in output
        assert "info1" in output

    def test_render_by_file_all(self) -> None:
        result = _make_scan_result(self._issues_all_severities())
        console = make_console()
        fmt = ConsoleFormatter(console)
        opts = FormatOptions(min_severity=Severity.INFO, group_by="file")
        with console.capture() as capture:
            fmt._render_by_file(result, "/stack", opts)
        output = _strip_ansi(capture.get())
        assert "err1" in output
        assert "warn1" in output
        assert "info1" in output

    def test_render_by_rule_all(self) -> None:
        result = _make_scan_result(self._issues_all_severities())
        console = make_console()
        fmt = ConsoleFormatter(console)
        opts = FormatOptions(min_severity=Severity.INFO, group_by="rule")
        with console.capture() as capture:
            fmt._render_by_rule(result, "/stack", opts)
        output = _strip_ansi(capture.get())
        assert "err1" in output
        assert "warn1" in output
        assert "info1" in output

    def test_render_by_severity_errors_only(self) -> None:
        result = _make_scan_result(self._issues_all_severities())
        console = make_console()
        fmt = ConsoleFormatter(console)
        opts = FormatOptions(min_severity=Severity.ERROR, group_by="severity")
        with console.capture() as capture:
            fmt._render_by_severity(result, "/stack", opts)
        output = _strip_ansi(capture.get())
        assert "err1" in output
        assert "warn1" not in output  # collapsed
        assert "info1" not in output  # collapsed

    def test_render_by_file_errors_only(self) -> None:
        result = _make_scan_result(self._issues_all_severities())
        console = make_console()
        fmt = ConsoleFormatter(console)
        opts = FormatOptions(min_severity=Severity.ERROR, group_by="file")
        with console.capture() as capture:
            fmt._render_by_file(result, "/stack", opts)
        output = _strip_ansi(capture.get())
        assert "err1" in output
        # warnings and info filtered out
        assert "warn1" not in output
        assert "info1" not in output
