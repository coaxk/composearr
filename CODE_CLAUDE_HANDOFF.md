# ComposeArr - Development Handoff Brief
## Code Claude: You're Up! 🚀

---

## MISSION
Build ComposeArr v0.1 - a Docker Compose hygiene linter with cross-file intelligence.

**Your role:** Implement the foundation and core functionality.  
**Our role:** Design decisions, user experience, testing, refinement.

---

## PROJECT STATUS

**Location:** `C:\Projects\composearr\`

**What exists:**
- ✅ BUILD_BRIEF.md (your complete technical spec)
- ✅ compose-hygiene-research.txt (market research)
- ✅ ui_mockup.py & ui_mockup_v2.py (visual references)
- ✅ Repository initialized

**What you need to build:**
Everything in BUILD_BRIEF.md Phase 1-4, starting with foundation.

---

## MCP SERVERS AVAILABLE

You have these MCP servers enabled:
- **security-guidance** - Use for auth/security review
- **context7** - Keep Docker Compose spec current
- **code-review** - Get second opinion on architecture
- **explanatory-output-style** - Make code readable

**Use them liberally!** Especially context7 for Docker Compose spec lookups.

---

## PHASE 1 DELIVERABLES (Your First Sprint)

### 1. Project Skeleton ✅ (Done)
Already initialized in `C:\Projects\composearr\`

### 2. Core Models (`src/composearr/models.py`)
```python
from dataclasses import dataclass
from enum import Enum
from pathlib import Path

class Severity(Enum):
    ERROR = "error"
    WARNING = "warning"
    INFO = "info"

class Scope(Enum):
    SERVICE = "service"
    FILE = "file"
    PROJECT = "project"

@dataclass
class LintIssue:
    rule_id: str
    rule_name: str
    severity: Severity
    message: str
    file_path: str
    line: int | None = None
    service: str | None = None
    fix_available: bool = False
    suggested_fix: str | None = None
    learn_more: str | None = None
```

### 3. Rule Base Class (`src/composearr/rules/base.py`)
Abstract base class that all rules inherit from. See BUILD_BRIEF.md lines 85-125.

### 4. Scanner Module (`src/composearr/scanner/`)

**discovery.py** - Find all compose files in directory tree
```python
def discover_compose_files(root_path: Path) -> List[Path]:
    """Recursively find all compose.yaml files"""
    pass
```

**parser.py** - Load YAML with ruamel.yaml (comment-preserving)
```python
def parse_compose_file(file_path: Path) -> dict:
    """Parse compose.yaml, return dict + preserve formatting"""
    pass
```

**env_resolver.py** - Load and resolve .env files
```python
def load_env_file(env_path: Path) -> dict:
    """Parse .env file into key-value dict"""
    pass
```

### 5. First 5 Rules (Simple ones to start)

Implement these in order of difficulty:

**CA403** (easiest) - Missing TZ variable
```python
# src/composearr/rules/CA4xx_consistency.py
class MissingTimezone(BaseRule):
    id = "CA403"
    name = "missing-timezone"
    severity = Severity.WARNING
    scope = Scope.SERVICE
    
    def check(self, context) -> list[LintIssue]:
        # Check if TZ env var exists
        pass
```

**CA203** - Missing restart policy
**CA001** - Latest tag usage
**CA201** - Missing healthcheck
**CA101** - Inline secrets (use regex patterns)

### 6. Console Formatter (`src/composearr/formatters/console.py`)

Use Rich library (already in typer deps) to create beautiful output matching `ui_mockup_v2.py` aesthetic.

**Reference the Beszel-inspired design:**
- Muted colors (`C_MUTED = "#71717a"`)
- Thin borders
- File context with line numbers
- Fix suggestions

### 7. CLI Entry Point (`src/composearr/cli.py`)

```python
import typer
from rich.console import Console

app = typer.Typer()
console = Console()

@app.command()
def audit(
    path: str = typer.Argument(".", help="Path to scan"),
    format: str = typer.Option("console", help="Output format"),
):
    """Scan Docker Compose files for issues"""
    # Entry point - wire everything together
    pass

@app.command()
def rules():
    """List all available rules"""
    pass

if __name__ == "__main__":
    app()
```

---

## ARCHITECTURE PRINCIPLES

### Two-Pass Design (CRITICAL)
1. **Pass 1:** Scan each file independently (per-service, per-file rules)
2. **Pass 2:** Cross-file analysis (port conflicts, PUID mismatches, etc)

**Why:** This is ComposeArr's differentiator. Nobody else does cross-file analysis.

### Comment Preservation (CRITICAL)
Use `ruamel.yaml` NOT `pyyaml`. We need to preserve:
- Comments
- Key ordering  
- Formatting
- Whitespace

**Why:** If we mangle someone's carefully formatted compose file, trust is gone forever.

### Error Handling
Be paranoid about malformed YAML:
- Catch parse errors gracefully
- Report which file failed
- Continue scanning other files
- Never crash on bad input

---

## TESTING STRATEGY

### Real-World Test Data
Judd will provide his actual 35-service stack for testing. Use it.

**Location:** `C:\DockerContainers\` (he'll point you there)

### Unit Tests
Create `tests/test_scanner.py` with:
- Valid compose files
- Invalid YAML
- Missing files
- Edge cases (empty files, comments-only, etc)

### Integration Tests  
Create `tests/test_rules.py` with:
- Sample compose files that trigger each rule
- Verify correct LintIssue generation
- Check cross-file detection

---

## DEVELOPMENT WORKFLOW

### Use Agents Liberally
For well-defined tasks, spawn agents:
```bash
# Example: Build the scanner module
[Agent: Build scanner/discovery.py that finds all compose files]
[Agent: Build scanner/parser.py using ruamel.yaml]
[Agent: Write tests for scanner module]
```

### Iterate Fast
1. Build minimal working version
2. Test on Judd's real stack
3. Fix issues
4. Repeat

Don't over-engineer. Ship working code, refine later.

### Security Review
Before any commit:
1. Run security-guidance MCP server
2. Check for hardcoded secrets in our code
3. Validate input sanitization
4. Review error handling

---

## OUTPUT EXPECTATIONS

### What We Want to See

**File Structure:**
```
src/composearr/
├── __init__.py (with version)
├── __main__.py (python -m composearr)
├── cli.py (typer commands)
├── models.py (dataclasses)
├── config.py (load .composearr.yml)
├── scanner/
│   ├── discovery.py
│   ├── parser.py
│   └── env_resolver.py
├── rules/
│   ├── base.py
│   ├── CA0xx_images.py
│   ├── CA1xx_security.py
│   ├── CA2xx_reliability.py
│   ├── CA4xx_consistency.py
│   └── CA6xx_arrstack.py (can wait)
└── formatters/
    ├── console.py
    └── json_fmt.py
```

**Working CLI:**
```bash
# This should work after Phase 1
cd C:\DockerContainers
composearr audit

# Output should look like ui_mockup_v2.py
# - Beszel-inspired colors
# - File context
# - Line numbers
# - Fix suggestions
```

---

## REFERENCE MATERIALS

### Existing Code
- `ui_mockup_v2.py` - **Your output should look like this**
- `BUILD_BRIEF.md` - Complete technical spec (lines 1-669)
- `compose-hygiene-research.txt` - Market analysis, rule ideas

### External References
Use context7 to fetch:
- [Compose Spec](https://github.com/compose-spec/compose-spec)
- [ruamel.yaml docs](https://yaml.readthedocs.io/en/latest/)
- [Typer docs](https://typer.tiangolo.com/)
- [Rich docs](https://rich.readthedocs.io/)

### Standards to Follow
- Docker Compose spec (context7 this)
- LinuxServer.io conventions (PUID/PGID)
- TRaSH Guides (hardlinks, folder structure)

---

## COMMUNICATION PROTOCOL

### Status Updates
At each milestone, report:
1. What you built
2. What works
3. What's blocked
4. What you need from us

### Code Review Requests
When you want feedback:
1. Push to branch
2. Tag us with specific questions
3. We'll review and merge

### Blockers
If stuck:
1. Use code-review MCP server first
2. If still stuck, ask us
3. We'll unblock or pivot

---

## SUCCESS CRITERIA FOR PHASE 1

### Minimal Working Product
```bash
composearr audit C:\DockerContainers
```

Should:
- ✅ Find all compose.yaml files
- ✅ Parse them without crashing
- ✅ Run 5 basic rules (CA001, CA101, CA201, CA203, CA403)
- ✅ Output beautiful terminal display (Beszel-style)
- ✅ Show file context and line numbers
- ✅ Provide fix suggestions

### Code Quality
- ✅ Type hints everywhere
- ✅ Docstrings on public functions
- ✅ No hardcoded paths
- ✅ Graceful error handling
- ✅ Unit tests for core functions

### Performance
- ✅ Scan 35 files in < 3 seconds
- ✅ No memory leaks
- ✅ Handles malformed YAML gracefully

---

## HANDOFF COMPLETE

You have:
- ✅ Complete technical spec (BUILD_BRIEF.md)
- ✅ Visual reference (ui_mockup_v2.py)
- ✅ Market research (compose-hygiene-research.txt)
- ✅ MCP servers enabled
- ✅ Project initialized at C:\Projects\composearr

**Your mission:** Build Phase 1 foundation (scanner + 5 rules + console output).

**Our expectations:** Working `composearr audit` command that finds real issues in Judd's 35-service stack.

**Timeline:** Take as long as needed to get it right. Quality > speed.

---

## GO BUILD! 🚀

We'll be here for design decisions, user experience, and testing. You focus on the implementation.

**First task:** Build the scanner module (discovery + parser + env_resolver). Once that works, we'll tackle rules.

Questions? Ask anytime. Otherwise, ship working code! 💪
