"""Watch mode — monitor compose files and re-audit on changes."""

from __future__ import annotations

import time
from datetime import datetime
from pathlib import Path
from typing import Callable, Optional

from watchdog.events import FileSystemEventHandler
from watchdog.observers import Observer

# Compose file names to watch
COMPOSE_FILENAMES = frozenset({
    "compose.yaml",
    "compose.yml",
    "docker-compose.yaml",
    "docker-compose.yml",
})


class ComposeFileHandler(FileSystemEventHandler):
    """Watchdog handler that fires on compose file changes with debouncing."""

    def __init__(self, callback: Callable[[Path], None]) -> None:
        super().__init__()
        self.callback = callback
        self.last_triggered: dict[Path, float] = {}
        self.debounce_seconds: float = 1.0  # Editors often save multiple times

    def on_modified(self, event) -> None:
        if event.is_directory:
            return

        path = Path(event.src_path)

        if not self._is_compose_file(path):
            return

        # Debounce rapid saves
        now = time.time()
        last = self.last_triggered.get(path, 0.0)
        if now - last < self.debounce_seconds:
            return

        self.last_triggered[path] = now
        self.callback(path)

    def _is_compose_file(self, path: Path) -> bool:
        """Check if a file is a Docker Compose file."""
        return path.name.lower() in COMPOSE_FILENAMES


class WatchMode:
    """Watch mode manager — monitors a stack directory and re-audits on changes."""

    def __init__(
        self,
        stack_path: Path,
        *,
        on_audit: Optional[Callable[[Path, object], None]] = None,
        debounce: float = 1.0,
    ) -> None:
        self.stack_path = Path(stack_path).resolve()
        self.on_audit = on_audit
        self.debounce = debounce
        self.observer: Optional[Observer] = None
        self.audit_count: int = 0
        self.last_audit: Optional[datetime] = None
        self._running = False

    def start(self, console=None) -> None:
        """Start watching. Blocks until Ctrl+C."""
        from composearr.engine import run_audit
        from composearr.formatters.console import ConsoleFormatter, make_console
        from composearr.formatters.progress import RichProgressReporter
        from composearr.history import AuditHistory
        from composearr.models import FormatOptions, Severity
        from composearr.scoring import calculate_stack_score

        con = console or make_console()

        con.print()
        con.print(f"  [bold #2dd4bf]\u25c6 Watch Mode[/]  [#71717a]{self.stack_path}[/]")
        con.print(f"  [#71717a]Monitoring compose files for changes. Press Ctrl+C to stop.[/]")
        con.print()

        # Initial audit
        self._run_audit_cycle(con)

        # Set up file watcher
        handler = ComposeFileHandler(lambda p: self._on_change(p, con))
        handler.debounce_seconds = self.debounce

        self.observer = Observer()
        self.observer.schedule(handler, str(self.stack_path), recursive=True)
        self.observer.start()
        self._running = True

        con.print(f"  [#71717a]╶─────────────────────────────────────────────────╴[/]")
        con.print(f"  [#71717a]Watching for changes… (Ctrl+C to return to menu)[/]")
        con.print()

        try:
            while self._running:
                time.sleep(0.5)
        except KeyboardInterrupt:
            pass
        finally:
            self.stop(con)

    def stop(self, console=None) -> None:
        """Stop watching."""
        self._running = False
        if self.observer:
            self.observer.stop()
            self.observer.join()
            self.observer = None

        if console:
            console.print()
            console.print(f"  [#f59e0b]\u25a0[/] [#fafafa]Watch mode stopped[/]  "
                          f"[#71717a]{self.audit_count} audits performed[/]")
            console.print()

    def _on_change(self, changed_path: Path, console) -> None:
        """Handle a compose file change."""
        try:
            rel = changed_path.relative_to(self.stack_path)
        except ValueError:
            rel = changed_path

        console.print()
        console.print(f"  [#3b82f6]\u2139[/]  [#fafafa]File changed:[/] [#2dd4bf]{rel}[/]")
        self._run_audit_cycle(console)

    def _run_audit_cycle(self, console) -> None:
        """Run a single audit cycle."""
        from composearr.engine import run_audit
        from composearr.formatters.console import ConsoleFormatter
        from composearr.formatters.progress import RichProgressReporter
        from composearr.history import AuditHistory
        from composearr.models import FormatOptions, Severity
        from composearr.scoring import calculate_stack_score

        self.audit_count += 1
        self.last_audit = datetime.now()

        console.print(
            f"  [#f59e0b]\u25cf[/] [#fafafa]Audit #{self.audit_count}[/]  "
            f"[#71717a]{self.last_audit.strftime('%H:%M:%S')}[/]"
        )
        console.print()

        reporter = RichProgressReporter(console)
        result = run_audit(self.stack_path, progress=reporter)
        console.print()

        # Calculate score
        score = calculate_stack_score(result.all_issues, result.total_services)

        # Save to history
        try:
            history = AuditHistory(self.stack_path)
            history.save_audit(
                issues=result.all_issues,
                score=score,
                files_scanned=len(result.compose_files),
                services_scanned=result.total_services,
                duration_seconds=result.timing.total_seconds,
            )
        except Exception:
            pass

        # Display results
        fmt_opts = FormatOptions(
            min_severity=Severity.WARNING,
            verbose=False,
            group_by="rule",
        )
        formatter = ConsoleFormatter(console)
        formatter.render(result, str(self.stack_path), options=fmt_opts)

        # Notify callback if set
        if self.on_audit:
            try:
                self.on_audit(self.stack_path, result)
            except Exception:
                pass
