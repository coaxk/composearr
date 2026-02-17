"""Simple exit message."""

from __future__ import annotations

from rich.console import Console


def show_closing_message(console: Console) -> None:
    """Show a clean, professional exit message."""
    console.print()
    console.print("[dim]Thank you for using ComposeArr.[/]")
    console.print()


# Keep old name as alias for backward compatibility during transition
show_closing_credits = show_closing_message
