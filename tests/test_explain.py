"""Tests for explain command."""

from __future__ import annotations

from io import StringIO

from rich.console import Console

from composearr.commands.explain import RULE_DOCS, render_explanation


class TestRuleDocs:
    def test_all_rules_have_docs(self):
        from composearr.rules import get_all_rules
        all_ids = {r.id for r in get_all_rules()}
        for rule_id in all_ids:
            assert rule_id in RULE_DOCS, f"Missing docs for {rule_id}"

    def test_docs_have_required_fields(self):
        for rule_id, docs in RULE_DOCS.items():
            assert "why" in docs, f"{rule_id} missing 'why'"
            assert "fix_examples" in docs, f"{rule_id} missing 'fix_examples'"
            assert "learn_more" in docs, f"{rule_id} missing 'learn_more'"
            assert len(docs["why"]) > 20, f"{rule_id} 'why' too short"


class TestRenderExplanation:
    def test_renders_known_rule(self):
        buf = StringIO()
        console = Console(file=buf, force_terminal=True, width=120)
        result = render_explanation("CA001", console)
        assert result is True
        output = buf.getvalue()
        assert "CA001" in output
        assert "no-latest-tag" in output

    def test_returns_false_for_unknown(self):
        buf = StringIO()
        console = Console(file=buf, force_terminal=True, width=120)
        result = render_explanation("CA999", console)
        assert result is False

    def test_all_rules_render(self):
        from composearr.rules import get_all_rules
        for rule in get_all_rules():
            buf = StringIO()
            console = Console(file=buf, force_terminal=True, width=120)
            result = render_explanation(rule.id, console)
            assert result is True, f"Failed to render {rule.id}"


class TestExplainCLI:
    def test_explain_command(self):
        from typer.testing import CliRunner
        from composearr.cli import app

        runner = CliRunner()
        result = runner.invoke(app, ["explain", "CA001"])
        assert result.exit_code == 0
        assert "CA001" in result.output

    def test_explain_unknown_rule(self):
        from typer.testing import CliRunner
        from composearr.cli import app

        runner = CliRunner()
        result = runner.invoke(app, ["explain", "CA999"])
        assert result.exit_code == 1

    def test_explain_by_name(self):
        from typer.testing import CliRunner
        from composearr.cli import app

        runner = CliRunner()
        result = runner.invoke(app, ["explain", "no-latest-tag"])
        assert result.exit_code == 0
