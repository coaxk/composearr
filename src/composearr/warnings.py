"""Warnings for special stack conditions."""

from __future__ import annotations

from rich.console import Console
from rich.panel import Panel

from composearr.scoring import StackTier, TIER_CONFIG


def show_tier_warning(console: Console, service_count: int) -> None:
    """Show warning when approaching or at TITAN tier."""
    services_to_titan = 201 - service_count

    if 0 < services_to_titan <= 10:
        console.print()
        console.print(Panel(
            f"[bold yellow]APPROACHING TITAN TIER[/]\n\n"
            f"Current: {service_count} services (DATACENTER)\n"
            f"Next: 201 services (TITAN)\n"
            f"Services remaining: [bold]{services_to_titan}[/]\n\n"
            f"[dim]The pinnacle awaits...[/]\n\n"
            f"Reaching TITAN tier means you're running:\n"
            f"  - More services than most small companies\n"
            f"  - Infrastructure that rivals production deployments\n"
            f"  - A stack that demands serious configuration hygiene\n"
            f"  - The kind of setup that earns respect on r/homelab\n\n"
            f"[bold]Almost there.[/]",
            border_style="yellow",
            title="WARNING",
        ))
        console.print()

    elif service_count >= 201:
        console.print()
        console.print(Panel(
            f"[bold bright_magenta]TITAN TIER ACHIEVED[/]\n\n"
            f"You've reached the pinnacle of stack management.\n\n"
            f"  Services: {service_count}\n"
            f"  Status: Elite\n\n"
            f"  Few run infrastructure at this scale.\n"
            f"  Fewer still keep it healthy.\n\n"
            f"[green]Achievement Unlocked: TITAN[/]\n"
            f"[dim]Your stack hygiene matters more than ever at this scale.[/]",
            border_style="bright_magenta",
            title="TITAN",
        ))
        console.print()
