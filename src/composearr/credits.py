"""Closing credits — Hall of Fame display on exit."""

from __future__ import annotations

import time

from rich.align import Align
from rich.console import Console
from rich.panel import Panel
from rich.table import Table


def show_closing_credits(console: Console) -> None:
    """Show closing credits with Hall of Fame if legends exist."""
    try:
        from composearr.leaderboard import Leaderboard
        from composearr.scoring import TIER_CONFIG, StackTier
    except ImportError:
        return

    leaderboard = Leaderboard()
    legends = leaderboard.get_top_legends(limit=10)
    mechas = leaderboard.get_titans()

    if not legends and not mechas:
        return

    console.print()

    # Title
    title = Panel(
        "[bold bright_cyan]HALL OF FAME[/]\n\n"
        "[dim]Honoring those who run elite infrastructure...[/]",
        border_style="bright_cyan",
        padding=(1, 4),
    )
    console.print(Align.center(title))
    time.sleep(0.5)

    # TITANS
    if mechas:
        console.print()
        mecha_text = _format_titans(mechas)
        mecha_panel = Panel(
            mecha_text,
            title="THE TITANS",
            border_style="bright_magenta",
            padding=(1, 2),
        )
        console.print(Align.center(mecha_panel))
        time.sleep(1.0)

    # Top legends table
    if legends:
        console.print()
        table = Table(
            title="Top Legendary Stacks (Anonymous)",
            show_header=True,
            header_style="bold cyan",
        )
        table.add_column("Rank", style="yellow", justify="center", width=6)
        table.add_column("Tier", justify="center", width=20)
        table.add_column("Services", justify="right", width=10)
        table.add_column("Weighted", justify="right", width=10)
        table.add_column("User ID", style="dim", width=14)

        medals = {0: "1st", 1: "2nd", 2: "3rd"}

        for idx, entry in enumerate(legends[:10]):
            rank = medals.get(idx, f"#{idx + 1}")
            tier_name = entry.get("tier", "UNKNOWN")

            # Get tier emoji safely
            try:
                tier_enum = StackTier(tier_name)
                tier_emoji = TIER_CONFIG[tier_enum]["emoji"]
            except (ValueError, KeyError):
                tier_emoji = "?"

            table.add_row(
                rank,
                f"{tier_emoji} {tier_name}",
                str(entry.get("service_count", 0)),
                str(entry.get("weighted_score", 0)),
                entry.get("user_id", "?")[:8] + "...",
            )

        console.print(Align.center(table))
        time.sleep(1.0)

    # Footer
    console.print()
    footer = Panel(
        "[dim]These legends maintain perfect stacks at scale.\n"
        "Reach ENTERPRISE tier (61+ services) to join them.[/]\n\n"
        "[bold]Caring aggressively about your YAMLs since 2026.[/]",
        border_style="dim",
        padding=(1, 2),
    )
    console.print(Align.center(footer))
    time.sleep(0.5)
    console.print()


def _format_titans(mechas: list[dict]) -> str:
    """Format TITAN entries for display."""
    total = len(mechas)
    if total == 0:
        return "[dim]None yet... will you be the first?[/]"

    lines = [
        f"[bold]Total TITANS: {total}[/]\n",
        "[dim]You are one of the elite.[/]\n",
    ]

    mechas_sorted = sorted(mechas, key=lambda x: x.get("weighted_score", 0), reverse=True)

    rank_labels = {0: "1st", 1: "2nd", 2: "3rd"}
    for idx, entry in enumerate(mechas_sorted[:5]):
        rank = rank_labels.get(idx, f"#{idx + 1}")
        lines.append(
            f"{rank} Weighted: {entry.get('weighted_score', 0):>3} "
            f"({entry.get('service_count', 0)} services) "
            f"[dim]{entry.get('user_id', '?')[:8]}...[/]"
        )

    return "\n".join(lines)
