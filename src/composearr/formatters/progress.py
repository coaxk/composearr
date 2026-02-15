"""Rich progress reporter implementing ProgressCallback."""

from __future__ import annotations

from rich.console import Console
from rich.progress import (
    BarColumn,
    Progress,
    SpinnerColumn,
    TextColumn,
)

# Beszel color tokens
C_TEAL = "#2dd4bf"
C_MUTED = "#71717a"
C_DIM = "#3f3f46"
C_OK = "#22c55e"

PHASE_LABELS = {
    "discovery": "Discovering compose files",
    "parse": "Parsing compose files",
    "per_file": "Running per-file rules",
    "cross_file": "Cross-file analysis",
}


class RichProgressReporter:
    """Rich-based progress that implements ProgressCallback protocol."""

    def __init__(self, console: Console | None = None, stderr_mode: bool = False) -> None:
        if stderr_mode:
            import sys
            self._console = Console(file=sys.stderr, force_terminal=True)
        else:
            self._console = console or Console()
        self._progress: Progress | None = None
        self._task_id: int | None = None
        self._phase: str = ""

    def on_phase_start(self, phase: str, total: int | None) -> None:
        self._phase = phase
        label = PHASE_LABELS.get(phase, phase)

        if total is not None and total > 0:
            self._progress = Progress(
                SpinnerColumn(style=C_TEAL),
                TextColumn(f"[{C_MUTED}]{{task.description}}[/]"),
                BarColumn(
                    bar_width=30,
                    style=C_DIM,
                    complete_style=C_TEAL,
                    finished_style=C_OK,
                ),
                TextColumn(f"[{C_DIM}]{{task.completed}}/{{task.total}}[/]"),
                console=self._console,
                transient=True,
            )
        else:
            self._progress = Progress(
                SpinnerColumn(style=C_TEAL),
                TextColumn(f"[{C_MUTED}]{{task.description}}[/]"),
                console=self._console,
                transient=True,
            )

        self._progress.start()
        self._task_id = self._progress.add_task(label, total=total)

    def on_progress(self, phase: str, current: int, description: str = "") -> None:
        if self._progress is None or self._task_id is None:
            return

        label = PHASE_LABELS.get(phase, phase)
        if description:
            # Show current file/rule name
            short = description.split("\\")[-1].split("/")[-1]
            label = f"{label} [{C_TEAL}]{short}[/]"

        self._progress.update(self._task_id, completed=current, description=label)

    def on_phase_end(self, phase: str) -> None:
        if self._progress is not None:
            self._progress.stop()
            self._progress = None
            self._task_id = None

        label = PHASE_LABELS.get(phase, phase)
        self._console.print(f"  [{C_OK}]\u2713[/] [{C_MUTED}]{label}[/]")
