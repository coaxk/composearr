# CLAUDE.md - AI Assistant Project Instructions

## Project Overview

ComposeArr is a Docker Compose hygiene linter and auditor. It scans compose files for
misconfigurations, missing best practices, and cross-service issues. Built with Python 3.11+
using the Hatch build system.

## Directory Structure

- `src/composearr/` - Main source package
- `src/composearr/rules/` - Lint rule definitions (BaseRule subclasses)
- `src/composearr/engine.py` - Core orchestrator: discovery -> parse -> per-file rules -> cross-file rules
- `src/composearr/cli.py` - Typer CLI entry points
- `src/composearr/tui.py` - Interactive TUI interface
- `src/composearr/models.py` - Data models
- `src/composearr/scanner/` - File discovery and parsing
- `src/composearr/formatters/` - Output formatters (github, json, table, etc.)
- `src/composearr/analyzers/` - Higher-level analysis (network, tag freshness)
- `src/composearr/security/` - Security-focused checks
- `tests/` - Test suite (pytest)

## Running the App

```bash
# Interactive TUI mode
python -m composearr

# CLI audit mode
python -m composearr audit <path>
```

## Running Tests

```bash
python -m pytest tests/ -v -p no:capture
```

## Architecture

The `engine.py` module orchestrates the full pipeline:
1. **Discovery** - Scan directories for compose files
2. **Parse** - Load YAML with ruamel.yaml (preserves comments/ordering)
3. **Per-file rules** - Run each BaseRule subclass against individual files
4. **Cross-file rules** - Run rules that compare across multiple compose files

### Rules System

All rules inherit from `BaseRule` and are auto-registered via `__init_subclass__`.
Rule files live in `src/composearr/rules/`. To add a rule, create a new file with a
class that subclasses `BaseRule` - it will be discovered automatically.

## Dependencies

**Required:** typer, ruamel.yaml, python-dotenv, jsonschema, inquirerpy, pyfiglet

**Optional (network extras):** requests, packaging (for image tag analysis)

Install for development:
```bash
pip install -e ".[dev,network]"
```

## Key Conventions

### File I/O
- Always use `encoding="utf-8"` on all file read/write operations
- Use `Path.as_posix()` for cross-platform path handling
- Never use bare `write_text()` without explicit encoding parameter

### Testing
- Use the `tmp_path` pytest fixture for temporary files
- Always pass `encoding="utf-8"` to `write_text()` in tests
- Mock network calls with `set_network_enabled(False)`
- Tests must pass on Linux, macOS, and Windows

### Code Style
- Formatted and linted with Ruff
- Type hints encouraged but not strictly enforced everywhere

## Session Discipline
**Before every commit and at end of session**, update knowledge files:
1. This `CLAUDE.md` — architecture, patterns, gotchas, key functions
2. Global `MEMORY.md` (at `~/.claude/projects/C--DockerContainers/memory/MEMORY.md`) — cross-project state, user prefs, ecosystem strategy
Do this proactively. Don't wait to be asked. If you built it, document it.

## Ecosystem Strategy
Part of a 4-tool ecosystem: MapArr, ComposeArr, SubBrainArr, Apart.
Shared code extraction planned for Phase 15+ into a `shared/` directory.
Cross-Claude communication via CLAUDE.md files and comprehensive code comments.
**Rumplestiltskin** — banked framework concept: extract ethos + methodology into pluggable analysis engine.
