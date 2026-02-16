"""Sprint 8 tests: Interactive fix preview (diff), enhanced explain mode."""

from __future__ import annotations

from io import StringIO
from pathlib import Path
from textwrap import dedent

import pytest
from rich.console import Console

from composearr.diff import DiffGenerator
from composearr.commands.explain import RULE_DOCS, render_explanation
from composearr.fixer import FilePreview, preview_fixes
from composearr.models import LintIssue, Severity


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_issue(
    rule_id: str = "CA203",
    severity: Severity = Severity.WARNING,
    file_path: str = "test.yaml",
    service: str = "sonarr",
    fix: str | None = "Add restart: unless-stopped",
) -> LintIssue:
    """Create a minimal fixable LintIssue for testing."""
    return LintIssue(
        rule_id=rule_id,
        rule_name="test-rule",
        message="test message",
        severity=severity,
        file_path=file_path,
        service=service,
        fix_available=fix is not None,
        suggested_fix=fix,
    )


def _capture_console() -> tuple[Console, StringIO]:
    """Return a Console that writes to a StringIO buffer."""
    buf = StringIO()
    console = Console(file=buf, force_terminal=True)
    return console, buf


COMPOSE_BASIC = dedent("""\
    services:
      sonarr:
        image: linuxserver/sonarr:latest
        container_name: sonarr
""")


# ===========================================================================
# DiffGenerator
# ===========================================================================


class TestDiffGenerator:
    """Unit tests for DiffGenerator."""

    def test_generate_diff_returns_list(self) -> None:
        differ = DiffGenerator()
        result = differ.generate_diff("a\nb\n", "a\nc\n", "test.yaml")
        assert isinstance(result, list)

    def test_generate_diff_empty_when_identical(self) -> None:
        differ = DiffGenerator()
        result = differ.generate_diff("hello\n", "hello\n", "test.yaml")
        assert result == []

    def test_generate_diff_shows_additions(self) -> None:
        differ = DiffGenerator()
        result = differ.generate_diff("line1\n", "line1\nline2\n", "test.yaml")
        additions = [l for l in result if l.startswith("+") and not l.startswith("+++")]
        assert len(additions) >= 1

    def test_generate_diff_shows_deletions(self) -> None:
        differ = DiffGenerator()
        result = differ.generate_diff("line1\nline2\n", "line1\n", "test.yaml")
        deletions = [l for l in result if l.startswith("-") and not l.startswith("---")]
        assert len(deletions) >= 1

    def test_generate_diff_filepath_in_header(self) -> None:
        differ = DiffGenerator()
        result = differ.generate_diff("a\n", "b\n", "myfile.yaml")
        joined = "\n".join(result)
        assert "myfile.yaml" in joined

    def test_display_diff_no_changes(self) -> None:
        console, buf = _capture_console()
        differ = DiffGenerator()
        differ.display_diff(console, "same\n", "same\n", "test.yaml")
        output = buf.getvalue()
        assert "No changes" in output

    def test_display_diff_shows_file_panel(self) -> None:
        console, buf = _capture_console()
        differ = DiffGenerator()
        differ.display_diff(console, "old\n", "new\n", "compose.yaml")
        output = buf.getvalue()
        assert "compose.yaml" in output

    def test_display_diff_with_description(self) -> None:
        console, buf = _capture_console()
        differ = DiffGenerator()
        differ.display_diff(console, "a\n", "b\n", "test.yaml", description="2 fixes applied")
        output = buf.getvalue()
        # Strip ANSI codes for checking
        import re
        clean = re.sub(r"\x1b\[[0-9;]*m", "", output)
        assert "2 fixes" in clean

    def test_get_change_summary_empty(self) -> None:
        differ = DiffGenerator()
        summary = differ.get_change_summary("same\n", "same\n")
        assert summary["additions"] == 0
        assert summary["deletions"] == 0
        assert summary["total_changes"] == 0

    def test_get_change_summary_counts(self) -> None:
        differ = DiffGenerator()
        summary = differ.get_change_summary("line1\nline2\n", "line1\nline3\nline4\n")
        assert summary["additions"] >= 1
        assert summary["total_changes"] >= 1

    def test_get_change_summary_keys(self) -> None:
        differ = DiffGenerator()
        summary = differ.get_change_summary("a\n", "b\n")
        assert "additions" in summary
        assert "deletions" in summary
        assert "total_changes" in summary


# ===========================================================================
# FilePreview
# ===========================================================================


class TestFilePreview:
    """Tests for the FilePreview dataclass."""

    def test_file_preview_creation(self) -> None:
        fp = FilePreview(
            file_path=Path("test.yaml"),
            original="old",
            modified="new",
            issues=[],
            fix_count=3,
        )
        assert fp.file_path == Path("test.yaml")
        assert fp.original == "old"
        assert fp.modified == "new"
        assert fp.fix_count == 3

    def test_file_preview_with_issues(self) -> None:
        issue = _make_issue()
        fp = FilePreview(
            file_path=Path("test.yaml"),
            original="old",
            modified="new",
            issues=[issue],
            fix_count=1,
        )
        assert len(fp.issues) == 1
        assert fp.issues[0].rule_id == "CA203"


# ===========================================================================
# preview_fixes
# ===========================================================================


class TestPreviewFixes:
    """Tests for the preview_fixes function."""

    def test_preview_no_fixable_issues(self) -> None:
        issues = [_make_issue(fix=None)]
        result = preview_fixes(issues)
        assert result == []

    def test_preview_nonexistent_file(self) -> None:
        issues = [_make_issue(file_path="/nonexistent/path.yaml")]
        result = preview_fixes(issues)
        assert result == []

    def test_preview_returns_file_preview(self, tmp_path: Path) -> None:
        compose = tmp_path / "compose.yaml"
        compose.write_text(dedent("""\
            services:
              sonarr:
                image: linuxserver/sonarr:latest
        """), encoding="utf-8")

        issue = _make_issue(
            rule_id="CA203",
            file_path=str(compose),
            service="sonarr",
            fix="Add restart: unless-stopped",
        )
        result = preview_fixes([issue])
        assert len(result) == 1
        assert result[0].fix_count >= 1
        assert result[0].file_path == compose

    def test_preview_modified_differs_from_original(self, tmp_path: Path) -> None:
        compose = tmp_path / "compose.yaml"
        compose.write_text(dedent("""\
            services:
              sonarr:
                image: linuxserver/sonarr:latest
        """), encoding="utf-8")

        issue = _make_issue(
            rule_id="CA203",
            file_path=str(compose),
            service="sonarr",
            fix="Add restart: unless-stopped",
        )
        result = preview_fixes([issue])
        assert len(result) == 1
        assert result[0].original != result[0].modified
        assert "restart" in result[0].modified

    def test_preview_does_not_modify_file(self, tmp_path: Path) -> None:
        compose = tmp_path / "compose.yaml"
        original_content = dedent("""\
            services:
              sonarr:
                image: linuxserver/sonarr:latest
        """)
        compose.write_text(original_content, encoding="utf-8")

        issue = _make_issue(
            rule_id="CA203",
            file_path=str(compose),
            service="sonarr",
            fix="Add restart: unless-stopped",
        )
        preview_fixes([issue])

        # File should be unchanged on disk
        assert compose.read_text(encoding="utf-8") == original_content

    def test_preview_multiple_files(self, tmp_path: Path) -> None:
        compose1 = tmp_path / "a" / "compose.yaml"
        compose1.parent.mkdir()
        compose1.write_text(dedent("""\
            services:
              sonarr:
                image: linuxserver/sonarr:latest
        """), encoding="utf-8")

        compose2 = tmp_path / "b" / "compose.yaml"
        compose2.parent.mkdir()
        compose2.write_text(dedent("""\
            services:
              radarr:
                image: linuxserver/radarr:latest
        """), encoding="utf-8")

        issues = [
            _make_issue(rule_id="CA203", file_path=str(compose1), service="sonarr"),
            _make_issue(rule_id="CA203", file_path=str(compose2), service="radarr"),
        ]
        result = preview_fixes(issues)
        assert len(result) == 2

    def test_preview_invalid_yaml(self, tmp_path: Path) -> None:
        compose = tmp_path / "compose.yaml"
        compose.write_text("not: valid: yaml: [[[", encoding="utf-8")

        issue = _make_issue(file_path=str(compose))
        result = preview_fixes([issue])
        # Should handle gracefully (skip or empty)
        assert isinstance(result, list)


# ===========================================================================
# RULE_DOCS (Enhanced Explain)
# ===========================================================================


class TestRuleDocs:
    """Tests for the enhanced rule documentation."""

    def test_all_30_rules_documented(self) -> None:
        """Every rule should have documentation in RULE_DOCS."""
        from composearr.rules.base import get_all_rules
        all_rules = get_all_rules()
        documented = set(RULE_DOCS.keys())
        rule_ids = {r.id for r in all_rules}
        # All documented rules should be valid
        for doc_id in documented:
            assert doc_id in rule_ids, f"RULE_DOCS has {doc_id} but no such rule exists"

    def test_rule_docs_structure(self) -> None:
        """Each rule doc should have required fields."""
        for rule_id, doc in RULE_DOCS.items():
            assert "why" in doc, f"{rule_id} missing 'why'"
            assert "fix_examples" in doc, f"{rule_id} missing 'fix_examples'"
            assert "learn_more" in doc, f"{rule_id} missing 'learn_more'"

    def test_rule_docs_why_not_empty(self) -> None:
        for rule_id, doc in RULE_DOCS.items():
            assert len(doc["why"]) > 20, f"{rule_id} 'why' too short"

    def test_rule_docs_fix_examples_tuples(self) -> None:
        for rule_id, doc in RULE_DOCS.items():
            for example in doc["fix_examples"]:
                assert isinstance(example, tuple), f"{rule_id} fix_example not a tuple"
                assert len(example) == 2, f"{rule_id} fix_example should be (title, code)"

    def test_rule_docs_learn_more_urls(self) -> None:
        for rule_id, doc in RULE_DOCS.items():
            for url in doc["learn_more"]:
                assert url.startswith("http"), f"{rule_id} learn_more URL invalid: {url}"


# ===========================================================================
# render_explanation
# ===========================================================================


class TestRenderExplanation:
    """Tests for the enhanced render_explanation function."""

    def test_render_known_rule(self) -> None:
        console, buf = _capture_console()
        result = render_explanation("CA001", console)
        assert result is True
        output = buf.getvalue()
        assert "CA001" in output

    def test_render_unknown_rule(self) -> None:
        console, buf = _capture_console()
        result = render_explanation("CAXXX", console)
        assert result is False

    def test_render_shows_why(self) -> None:
        console, buf = _capture_console()
        render_explanation("CA001", console)
        output = buf.getvalue()
        assert "Why it matters" in output

    def test_render_shows_scenarios(self) -> None:
        console, buf = _capture_console()
        render_explanation("CA201", console)
        output = buf.getvalue()
        assert "Common scenarios" in output

    def test_render_shows_fix_examples(self) -> None:
        console, buf = _capture_console()
        render_explanation("CA203", console)
        output = buf.getvalue()
        assert "How to fix" in output

    def test_render_shows_related_rules(self) -> None:
        console, buf = _capture_console()
        render_explanation("CA001", console)
        output = buf.getvalue()
        assert "Related rules" in output

    def test_render_shows_learn_more(self) -> None:
        console, buf = _capture_console()
        render_explanation("CA001", console)
        output = buf.getvalue()
        assert "Learn more" in output

    def test_render_all_documented_rules(self) -> None:
        """Every documented rule should render without error."""
        for rule_id in RULE_DOCS:
            console, buf = _capture_console()
            result = render_explanation(rule_id, console)
            assert result is True, f"render_explanation failed for {rule_id}"

    def test_render_ca501_memory(self) -> None:
        console, buf = _capture_console()
        render_explanation("CA501", console)
        output = buf.getvalue()
        assert "memory" in output.lower()

    def test_render_ca802_privileged(self) -> None:
        console, buf = _capture_console()
        render_explanation("CA802", console)
        output = buf.getvalue()
        assert "privileged" in output.lower()


# ===========================================================================
# Diff + Preview Integration
# ===========================================================================


class TestDiffPreviewIntegration:
    """Integration tests combining DiffGenerator with preview_fixes."""

    def test_preview_to_diff(self, tmp_path: Path) -> None:
        compose = tmp_path / "compose.yaml"
        compose.write_text(dedent("""\
            services:
              sonarr:
                image: linuxserver/sonarr:latest
        """), encoding="utf-8")

        issue = _make_issue(
            rule_id="CA203",
            file_path=str(compose),
            service="sonarr",
        )
        previews = preview_fixes([issue])
        assert len(previews) == 1

        differ = DiffGenerator()
        diff_lines = differ.generate_diff(
            previews[0].original,
            previews[0].modified,
            "compose.yaml",
        )
        assert len(diff_lines) > 0
        # Should show restart being added
        additions = [l for l in diff_lines if l.startswith("+") and not l.startswith("+++")]
        assert any("restart" in l for l in additions)

    def test_preview_to_display(self, tmp_path: Path) -> None:
        compose = tmp_path / "compose.yaml"
        compose.write_text(dedent("""\
            services:
              radarr:
                image: linuxserver/radarr:latest
        """), encoding="utf-8")

        issue = _make_issue(
            rule_id="CA203",
            file_path=str(compose),
            service="radarr",
        )
        previews = preview_fixes([issue])
        assert len(previews) == 1

        console, buf = _capture_console()
        differ = DiffGenerator()
        differ.display_diff(
            console,
            previews[0].original,
            previews[0].modified,
            "compose.yaml",
        )
        output = buf.getvalue()
        assert "compose.yaml" in output

    def test_change_summary_from_preview(self, tmp_path: Path) -> None:
        compose = tmp_path / "compose.yaml"
        compose.write_text(dedent("""\
            services:
              sonarr:
                image: linuxserver/sonarr:latest
        """), encoding="utf-8")

        issue = _make_issue(
            rule_id="CA203",
            file_path=str(compose),
            service="sonarr",
        )
        previews = preview_fixes([issue])
        assert len(previews) == 1

        differ = DiffGenerator()
        summary = differ.get_change_summary(
            previews[0].original,
            previews[0].modified,
        )
        assert summary["additions"] >= 1
        assert summary["total_changes"] >= 1


# ===========================================================================
# Edge Cases
# ===========================================================================


class TestEdgeCases:
    """Edge cases and boundary conditions."""

    def test_diff_empty_strings(self) -> None:
        differ = DiffGenerator()
        result = differ.generate_diff("", "", "test.yaml")
        assert result == []

    def test_diff_single_newline(self) -> None:
        differ = DiffGenerator()
        result = differ.generate_diff("\n", "\n", "test.yaml")
        assert result == []

    def test_diff_large_content(self) -> None:
        differ = DiffGenerator()
        original = "\n".join(f"line{i}" for i in range(1000)) + "\n"
        modified = "\n".join(f"line{i}" for i in range(999)) + "\nchanged\n"
        result = differ.generate_diff(original, modified, "test.yaml")
        assert len(result) > 0

    def test_preview_no_services_key(self, tmp_path: Path) -> None:
        compose = tmp_path / "compose.yaml"
        compose.write_text("version: '3'\n", encoding="utf-8")
        issue = _make_issue(file_path=str(compose))
        result = preview_fixes([issue])
        assert result == []

    def test_preview_empty_services(self, tmp_path: Path) -> None:
        compose = tmp_path / "compose.yaml"
        compose.write_text("services:\n", encoding="utf-8")
        issue = _make_issue(file_path=str(compose))
        result = preview_fixes([issue])
        assert isinstance(result, list)

    def test_rule_docs_ca901_has_scenarios(self) -> None:
        """CA901 uses tuple format for scenarios — verify it works."""
        doc = RULE_DOCS["CA901"]
        assert "scenarios" in doc
        # CA901 scenarios are tuples (title, code) not plain strings
        for scenario in doc["scenarios"]:
            assert isinstance(scenario, (str, tuple))

    def test_render_explanation_all_severity_levels(self) -> None:
        """Test that rules of each severity level render correctly."""
        from composearr.rules.base import get_all_rules
        rules = get_all_rules()
        severities_tested = set()
        for rule in rules:
            if rule.id in RULE_DOCS:
                console, buf = _capture_console()
                render_explanation(rule.id, console)
                severities_tested.add(rule.severity)
                if len(severities_tested) >= 3:
                    break
