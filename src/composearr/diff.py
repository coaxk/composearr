"""Diff generation for fix preview."""

from __future__ import annotations

import difflib

from rich.console import Console
from rich.panel import Panel


class DiffGenerator:
    """Generate and display colored diffs for fix previews."""

    def generate_diff(
        self,
        original: str,
        modified: str,
        filepath: str,
    ) -> list[str]:
        """Generate unified diff lines."""
        original_lines = original.splitlines(keepends=True)
        modified_lines = modified.splitlines(keepends=True)

        diff = difflib.unified_diff(
            original_lines,
            modified_lines,
            fromfile=f"a/{filepath}",
            tofile=f"b/{filepath}",
            lineterm="",
        )

        return list(diff)

    def display_diff(
        self,
        console: Console,
        original: str,
        modified: str,
        filepath: str,
        description: str | None = None,
    ) -> None:
        """Display colored unified diff in terminal."""
        diff_lines = self.generate_diff(original, modified, filepath)

        if not diff_lines:
            console.print("  [dim]No changes detected[/]")
            return

        # Header
        console.print(Panel(
            f"[bold]File:[/] {filepath}",
            border_style="cyan",
            padding=(0, 1),
        ))

        if description:
            console.print(f"  [dim]{description}[/]")

        # Display diff with colors
        console.print()
        for line in diff_lines:
            line_stripped = line.rstrip("\n\r")
            if line_stripped.startswith("---") or line_stripped.startswith("+++"):
                console.print(f"  [bold]{line_stripped}[/]")
            elif line_stripped.startswith("@@"):
                console.print(f"  [cyan]{line_stripped}[/]")
            elif line_stripped.startswith("+"):
                console.print(f"  [green]{line_stripped}[/]")
            elif line_stripped.startswith("-"):
                console.print(f"  [red]{line_stripped}[/]")
            else:
                console.print(f"  [dim]{line_stripped}[/]")
        console.print()

    def get_change_summary(
        self,
        original: str,
        modified: str,
    ) -> dict[str, int]:
        """Get summary of changes (additions, deletions, total)."""
        diff_lines = self.generate_diff(original, modified, "file")

        additions = sum(
            1 for line in diff_lines
            if line.startswith("+") and not line.startswith("+++")
        )
        deletions = sum(
            1 for line in diff_lines
            if line.startswith("-") and not line.startswith("---")
        )

        return {
            "additions": additions,
            "deletions": deletions,
            "total_changes": additions + deletions,
        }
