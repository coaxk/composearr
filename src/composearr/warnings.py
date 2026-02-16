"""Warnings for special stack conditions."""

from __future__ import annotations

from rich.console import Console
from rich.panel import Panel

from composearr.scoring import StackTier, TIER_CONFIG


def show_tier_warning(console: Console, service_count: int) -> None:
    """Show warning when approaching or at MECHA NECKBEARD tier."""
    services_to_final = 201 - service_count

    if 0 < services_to_final <= 10:
        console.print()
        console.print(Panel(
            f"[bold yellow]APPROACHING FINAL BOSS TIER[/]\n\n"
            f"Current: {service_count} services (DATACENTER)\n"
            f"Next: 201 services (MECHA NECKBEARD)\n"
            f"Services remaining: [bold]{services_to_final}[/]\n\n"
            f"[dim]The Final Boss tier awaits...[/]\n\n"
            f"Disclaimer: Reaching MECHA NECKBEARD may result in:\n"
            f"  - Questions about your life choices\n"
            f"  - Hardware costs exceeding car payments\n"
            f"  - Time investment rivaling a part-time job\n"
            f"  - Becoming a r/homelab legend\n"
            f"  - Never explaining your setup to normies again\n\n"
            f"[bold]Are you ready to transcend?[/]",
            border_style="yellow",
            title="WARNING",
        ))
        console.print()

    elif service_count >= 201:
        console.print()
        console.print(Panel(
            f"[bold bright_magenta]FINAL BOSS ACHIEVED[/]\n\n"
            f"[bold bright_magenta]MECHA NECKBEARD TIER UNLOCKED[/]\n\n"
            f"You are no longer bound by mortal limits\n\n"
            f"  Services: {service_count}\n"
            f"  Status: TRANSCENDED\n\n"
            f'  "Are you even human?"\n'
            f"         - ComposeArr\n\n"
            f"[green]Achievement Unlocked: THE FINAL BOSS[/]\n"
            f"[dim]Secret Achievement: TOUCH GRASS (jk you're amazing)[/]",
            border_style="bright_magenta",
            title="TRANSCENDED",
        ))
        console.print()
