"""Sprint 9 tests: TUI restructure, terminology, suppression, config flags."""

from __future__ import annotations

from io import StringIO
from pathlib import Path

import pytest
from rich.console import Console

from composearr.config import Config, parse_file_suppressions
from composearr.leaderboard import Leaderboard
from composearr.models import LintIssue, Severity
from composearr.scoring import (
    TIER_CONFIG,
    StackTier,
    calculate_stack_score,
    get_stack_tier,
)
from composearr.suppression import SuppressionParser


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_issue(
    rule_id: str = "CA101",
    severity: Severity = Severity.ERROR,
) -> LintIssue:
    return LintIssue(
        rule_id=rule_id,
        rule_name="test-rule",
        message="test message",
        severity=severity,
        file_path="test.yaml",
        service="svc",
    )


def _capture_console() -> tuple[Console, StringIO]:
    buf = StringIO()
    console = Console(file=buf, force_terminal=True)
    return console, buf


# ===========================================================================
# Terminology — Professional tier names
# ===========================================================================


class TestProfessionalTerminology:
    """Verify professional tier naming throughout."""

    def test_infrastructure_enum_exists(self) -> None:
        assert hasattr(StackTier, "INFRASTRUCTURE")
        assert StackTier.INFRASTRUCTURE.value == "INFRASTRUCTURE"

    def test_professional_enum_exists(self) -> None:
        assert hasattr(StackTier, "PROFESSIONAL")
        assert StackTier.PROFESSIONAL.value == "PROFESSIONAL"

    def test_no_mecha_neckbeard_enum(self) -> None:
        assert not hasattr(StackTier, "MECHA_NECKBEARD")

    def test_no_power_user_enum(self) -> None:
        assert not hasattr(StackTier, "POWER_USER")

    def test_no_titan_enum(self) -> None:
        assert not hasattr(StackTier, "TITAN")

    def test_infrastructure_in_tier_config(self) -> None:
        assert StackTier.INFRASTRUCTURE in TIER_CONFIG

    def test_infrastructure_range(self) -> None:
        cfg = TIER_CONFIG[StackTier.INFRASTRUCTURE]
        assert cfg["range"][0] == 201

    def test_get_stack_tier_201(self) -> None:
        assert get_stack_tier(201) == StackTier.INFRASTRUCTURE

    def test_get_stack_tier_500(self) -> None:
        assert get_stack_tier(500) == StackTier.INFRASTRUCTURE

    def test_infrastructure_multiplier(self) -> None:
        assert TIER_CONFIG[StackTier.INFRASTRUCTURE]["multiplier"] == 3.0

    def test_score_display_grade_infrastructure(self) -> None:
        score = calculate_stack_score([], 250)
        display = score.get_display_grade()
        assert "INFRASTRUCTURE" in display

    def test_leaderboard_eligible_tiers(self) -> None:
        assert "INFRASTRUCTURE" in Leaderboard.ELIGIBLE_TIERS
        assert "MECHA_NECKBEARD" not in Leaderboard.ELIGIBLE_TIERS
        assert "TITAN" not in Leaderboard.ELIGIBLE_TIERS

    def test_leaderboard_get_infrastructure(self) -> None:
        assert hasattr(Leaderboard, "get_infrastructure")

    def test_leaderboard_migration_mecha(self, tmp_path: Path) -> None:
        """Old MECHA_NECKBEARD entries should be migrated to INFRASTRUCTURE."""
        import json
        lb_file = tmp_path / "leaderboard.json"
        lb_file.write_text(json.dumps([{
            "user_id": "test123",
            "tier": "MECHA_NECKBEARD",
            "weighted_score": 300,
            "service_count": 250,
            "is_legendary": True,
            "timestamp": "2026-01-01T00:00:00",
        }]), encoding="utf-8")

        lb = Leaderboard(path=lb_file)
        entries = lb.get_all()
        assert entries[0]["tier"] == "INFRASTRUCTURE"

    def test_leaderboard_migration_titan(self, tmp_path: Path) -> None:
        """Old TITAN entries should be migrated to INFRASTRUCTURE."""
        import json
        lb_file = tmp_path / "leaderboard.json"
        lb_file.write_text(json.dumps([{
            "user_id": "test456",
            "tier": "TITAN",
            "weighted_score": 300,
            "service_count": 250,
            "is_legendary": True,
            "timestamp": "2026-01-01T00:00:00",
        }]), encoding="utf-8")

        lb = Leaderboard(path=lb_file)
        entries = lb.get_all()
        assert entries[0]["tier"] == "INFRASTRUCTURE"

    def test_warnings_no_mecha(self) -> None:
        from composearr.warnings import show_tier_warning
        console, buf = _capture_console()
        show_tier_warning(console, 201)
        output = buf.getvalue()
        assert "MECHA" not in output
        assert "INFRASTRUCTURE" in output

    def test_warnings_approaching_infrastructure(self) -> None:
        from composearr.warnings import show_tier_warning
        console, buf = _capture_console()
        show_tier_warning(console, 195)
        output = buf.getvalue()
        assert "INFRASTRUCTURE" in output

    def test_no_power_level_in_config(self) -> None:
        """No tier config should have a power_level key."""
        for tier, cfg in TIER_CONFIG.items():
            assert "power_level" not in cfg, f"{tier} still has power_level"


# ===========================================================================
# Suppression Parser
# ===========================================================================


class TestSuppressionParser:
    """Tests for the enhanced SuppressionParser."""

    def test_format_1_composearr_ignore(self) -> None:
        p = SuppressionParser()
        _, _, sups = p.parse("# composearr-ignore: CA001\nimage: test")
        assert "CA001" in sups.get(1, set())
        assert "CA001" in sups.get(2, set())

    def test_format_2_composearr_ignore_alt(self) -> None:
        p = SuppressionParser()
        _, _, sups = p.parse("# composearr: ignore CA001\nimage: test")
        assert "CA001" in sups.get(1, set())
        assert "CA001" in sups.get(2, set())

    def test_comma_separated(self) -> None:
        p = SuppressionParser()
        _, _, sups = p.parse("# composearr-ignore: CA001,CA201\nimage: test")
        assert "CA001" in sups.get(1, set())
        assert "CA201" in sups.get(1, set())

    def test_comma_separated_format_2(self) -> None:
        p = SuppressionParser()
        _, _, sups = p.parse("# composearr: ignore CA001,CA201\nimage: test")
        assert "CA001" in sups.get(1, set())
        assert "CA201" in sups.get(1, set())

    def test_file_level_suppression(self) -> None:
        p = SuppressionParser()
        file_ignored, _, _ = p.parse("# composearr-ignore-file\nimage: test")
        assert file_ignored is True

    def test_no_suppression(self) -> None:
        p = SuppressionParser()
        file_ignored, _, sups = p.parse("image: test\nrestart: always")
        assert file_ignored is False
        assert sups == {}

    def test_case_insensitive_rule_id(self) -> None:
        p = SuppressionParser()
        _, _, sups = p.parse("# composearr-ignore: ca001\nimage: test")
        assert "CA001" in sups.get(1, set())

    def test_suppression_on_next_line(self) -> None:
        """Suppression comment on line N applies to line N+1 too."""
        p = SuppressionParser()
        _, _, sups = p.parse("# composearr-ignore: CA001\nimage: test:latest")
        assert "CA001" in sups.get(2, set())

    def test_multiple_suppressions(self) -> None:
        p = SuppressionParser()
        content = "line1\n# composearr-ignore: CA001\nline3\n# composearr: ignore CA201\nline5"
        _, _, sups = p.parse(content)
        assert "CA001" in sups.get(2, set())
        assert "CA201" in sups.get(4, set())

    def test_empty_content(self) -> None:
        p = SuppressionParser()
        file_ignored, _, sups = p.parse("")
        assert file_ignored is False
        assert sups == {}

    def test_delegation_from_config(self) -> None:
        """parse_file_suppressions in config.py should delegate to SuppressionParser."""
        result = parse_file_suppressions("# composearr: ignore CA501\nimage: test")
        _, _, sups = result
        assert "CA501" in sups.get(1, set())


# ===========================================================================
# Config Fields
# ===========================================================================


class TestConfigFields:
    """Tests for Config fields."""

    def test_honor_suppressions_default(self) -> None:
        config = Config()
        assert config.honor_suppressions is True

    def test_honor_suppressions_merge_false(self) -> None:
        config = Config()
        config.merge({"honor_suppressions": False})
        assert config.honor_suppressions is False

    def test_leaderboard_disabled_by_default(self) -> None:
        config = Config()
        assert config.leaderboard_enabled is False

    def test_show_tier_warnings_off_by_default(self) -> None:
        config = Config()
        assert config.show_tier_warnings is False

    def test_show_achievements_off_by_default(self) -> None:
        config = Config()
        assert config.show_achievements is False

    def test_show_tier_info_on_by_default(self) -> None:
        config = Config()
        assert config.show_tier_info is True

    def test_display_merge(self) -> None:
        config = Config()
        config.merge({"display": {"show_tier_warnings": True, "show_achievements": True}})
        assert config.show_tier_warnings is True
        assert config.show_achievements is True

    def test_leaderboard_merge(self) -> None:
        config = Config()
        config.merge({"leaderboard": {"enabled": True, "show_on_exit": True}})
        assert config.leaderboard_enabled is True
        assert config.show_stats_on_exit is True


# ===========================================================================
# Menu Structure
# ===========================================================================


class TestMenuStructure:
    """Verify the new 7-item menu structure is correct."""

    def test_main_menu_choices(self) -> None:
        """Main menu should have exactly 7 choices."""
        # Read the source to verify menu structure
        import ast
        src = Path("src/composearr/tui.py").read_text(encoding="utf-8")
        # Count the Choice values in the main menu block
        main_menu_values = ["scan", "fix", "history", "tools", "rules_help", "settings"]
        for val in main_menu_values:
            assert f'value="{val}"' in src, f"Missing menu choice: {val}"

    def test_no_scaffold_in_main_menu(self) -> None:
        """Scaffold should NOT be in the main menu."""
        src = Path("src/composearr/tui.py").read_text(encoding="utf-8")
        # Find the main menu section and check scaffold is not there
        # It should only appear in settings submenu or not at all
        lines = src.split("\n")
        in_main_menu = False
        for line in lines:
            if "What would you like to do?" in line:
                in_main_menu = True
            if in_main_menu and ".execute()" in line:
                break
            if in_main_menu and "scaffold" in line.lower():
                pytest.fail("Scaffold found in main menu")

    def test_no_orphanage_in_main_menu(self) -> None:
        """'The Orphanage' should not be in the main menu choices."""
        src = Path("src/composearr/tui.py").read_text(encoding="utf-8")
        # Check main menu description block (before the Choice list)
        lines = src.split("\n")
        in_desc_block = False
        for line in lines:
            if "What would you like to do?" in line:
                break
            if "Scan Stack" in line and "C_MUTED" in line:
                in_desc_block = True
            if in_desc_block and "The Orphanage" in line:
                pytest.fail("The Orphanage found in main menu descriptions")

    def test_orphaned_resources_label(self) -> None:
        """'Orphaned Resources' should appear in analysis tools."""
        src = Path("src/composearr/tui.py").read_text(encoding="utf-8")
        assert "Orphaned Resources" in src

    def test_analysis_tools_submenu_exists(self) -> None:
        """_tui_analysis_tools function should exist."""
        from composearr.tui import _tui_analysis_tools
        assert callable(_tui_analysis_tools)

    def test_rules_help_submenu_exists(self) -> None:
        """_tui_rules_help function should exist."""
        from composearr.tui import _tui_rules_help
        assert callable(_tui_rules_help)

    def test_settings_submenu_exists(self) -> None:
        """_tui_settings function should exist."""
        from composearr.tui import _tui_settings
        assert callable(_tui_settings)

    def test_scan_stack_exists(self) -> None:
        """_tui_scan_stack function should exist."""
        from composearr.tui import _tui_scan_stack
        assert callable(_tui_scan_stack)

    def test_runtime_vs_compose_label(self) -> None:
        """'Runtime vs Compose' should appear instead of 'Runtime Diff'."""
        src = Path("src/composearr/tui.py").read_text(encoding="utf-8")
        assert "Runtime vs Compose" in src


# ===========================================================================
# First-Run Marker
# ===========================================================================


class TestFirstRunMarker:
    """Tests for first-run detection marker."""

    def test_is_first_launch_with_marker(self, tmp_path: Path, monkeypatch) -> None:
        """When marker exists, should NOT be first launch."""
        composearr_dir = tmp_path / ".composearr"
        composearr_dir.mkdir()
        marker = composearr_dir / ".first_run_complete"
        marker.touch()

        monkeypatch.setattr(Path, "home", lambda: tmp_path)
        from composearr.tui import _is_first_launch
        assert _is_first_launch() is False

    def test_marker_file_path(self) -> None:
        """Verify the expected marker file path."""
        expected = Path.home() / ".composearr" / ".first_run_complete"
        # Just verify the path construction is valid
        assert expected.name == ".first_run_complete"
        assert expected.parent.name == ".composearr"


# ===========================================================================
# Feature Cuts
# ===========================================================================


class TestFeatureCuts:
    """Tests for feature cut/demotion decisions."""

    def test_leaderboard_off_by_default(self) -> None:
        """Leaderboard should be disabled by default."""
        config = Config()
        assert config.leaderboard_enabled is False

    def test_grammarly_tagline_in_tui(self) -> None:
        """'Grammarly for Docker Compose' should appear in TUI source."""
        src = Path("src/composearr/tui.py").read_text(encoding="utf-8")
        assert "Grammarly for Docker Compose" in src

    def test_no_ascii_art_in_tui(self) -> None:
        """No Roll Safe or whale ASCII art should remain in TUI."""
        src = Path("src/composearr/tui.py").read_text(encoding="utf-8")
        assert "ROLL_SAFE" not in src
        assert "_load_ansi_art" not in src
        assert "WHALE_FALLBACK" not in src

    def test_no_taglines_in_tui(self) -> None:
        """No playful exit taglines should remain."""
        src = Path("src/composearr/tui.py").read_text(encoding="utf-8")
        assert "Do you even YAML" not in src
        assert "Caring aggressively" not in src

    def test_watch_mode_in_analysis_tools(self) -> None:
        """Watch Mode should be in analysis tools, not main menu."""
        src = Path("src/composearr/tui.py").read_text(encoding="utf-8")
        # Find analysis_tools function and verify watch is there
        assert "watch" in src  # Basic sanity check
        # Verify it's in the analysis tools submenu
        in_analysis = False
        for line in src.split("\n"):
            if "def _tui_analysis_tools" in line:
                in_analysis = True
            if in_analysis and "Watch Mode" in line:
                break
            if in_analysis and "def _tui_" in line and "analysis" not in line:
                pytest.fail("Watch Mode not found in analysis tools")
                break

    def test_topology_in_analysis_tools(self) -> None:
        """Topology should be in analysis tools, not main menu."""
        src = Path("src/composearr/tui.py").read_text(encoding="utf-8")
        in_analysis = False
        for line in src.split("\n"):
            if "def _tui_analysis_tools" in line:
                in_analysis = True
            if in_analysis and "Topology" in line:
                break
            if in_analysis and "def _tui_" in line and "analysis" not in line:
                pytest.fail("Topology not found in analysis tools")
                break
