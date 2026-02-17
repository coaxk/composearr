"""Warnings for stack tier progression."""

from __future__ import annotations

from rich.console import Console
from rich.panel import Panel

from composearr.scoring import TIER_CONFIG, StackTier, get_stack_tier


def show_tier_warning(console: Console, service_count: int) -> None:
    """Show informational message when approaching or reaching a new tier."""
    tier = get_stack_tier(service_count)
    tier_cfg = TIER_CONFIG[tier]

    # Check if approaching next tier
    tiers = list(StackTier)
    current_idx = tiers.index(tier)

    if current_idx < len(tiers) - 1:
        next_tier = tiers[current_idx + 1]
        next_cfg = TIER_CONFIG[next_tier]
        next_min = next_cfg["range"][0]
        remaining = next_min - service_count

        if 0 < remaining <= 10:
            console.print()
            console.print(Panel(
                f"[cyan]Approaching next tier[/]\n\n"
                f"Current: {service_count} services ({tier_cfg['emoji']} {tier.value})\n"
                f"Next: {next_min} services ({next_cfg['emoji']} {next_tier.value})\n"
                f"Services remaining: [bold]{remaining}[/]\n\n"
                f"[dim]Weighted score multiplier will increase "
                f"from \u00d7{tier_cfg['multiplier']} to \u00d7{next_cfg['multiplier']}[/]",
                border_style="cyan",
                title="\U0001f4ca Stack Growth",
            ))
            console.print()

    elif tier == StackTier.INFRASTRUCTURE:
        console.print()
        console.print(Panel(
            f"[bold cyan]INFRASTRUCTURE tier[/]\n\n"
            f"Services: {service_count}\n"
            f"Multiplier: \u00d7{tier_cfg['multiplier']}\n\n"
            f"[dim]Stack hygiene is critical at this scale.\n"
            f"Consider running audits regularly.[/]",
            border_style="cyan",
            title="\U0001f4ca Stack Growth",
        ))
        console.print()
