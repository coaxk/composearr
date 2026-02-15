# ComposeArr Production Requirements
## The Stuff Nobody Thinks About Until It's Too Late

---

## 1. PERFORMANCE REQUIREMENTS (NON-NEGOTIABLE)

### Hard Performance Targets

```python
"""
PERFORMANCE BENCHMARKS - Must Pass Before v0.1 Ships

If any of these fail, ComposeArr is not ready.
"""

PERFORMANCE_REQUIREMENTS = {
    # File scanning
    'discover_1000_files': {
        'max_time': 2.0,  # seconds
        'test': 'Scan directory tree with 1000 compose files'
    },
    
    # Parsing
    'parse_100_files': {
        'max_time': 5.0,
        'test': 'Parse 100 compose files (avg 50 lines each)'
    },
    
    # Rule execution
    'run_all_rules_35_files': {
        'max_time': 10.0,
        'test': "Run all 10 rules on Judd's 35-service stack"
    },
    
    # Cross-file analysis
    'port_conflict_1000_services': {
        'max_time': 1.0,
        'test': 'Detect port conflicts across 1000 services'
    },
    
    # Output generation
    'format_1000_issues': {
        'max_time': 2.0,
        'test': 'Format and display 1000 lint issues'
    },
    
    # Memory usage
    'memory_100_files': {
        'max_memory_mb': 200,
        'test': 'Parse and analyze 100 files without exceeding 200MB'
    },
    
    # Startup time
    'cli_startup': {
        'max_time': 0.5,
        'test': 'Time from `composearr` to first output'
    },
}
```

### Performance Testing Framework

```python
# tests/test_performance.py

import pytest
import time
import psutil
import os

class TestPerformance:
    """Performance benchmarks - must pass before release"""
    
    @pytest.mark.benchmark
    def test_scan_1000_files(self, benchmark_stack):
        """Must scan 1000 files in < 2 seconds"""
        
        start = time.time()
        files = discover_compose_files(benchmark_stack)
        elapsed = time.time() - start
        
        assert len(files) >= 1000
        assert elapsed < 2.0, f"Scan took {elapsed:.2f}s, must be < 2.0s"
    
    @pytest.mark.benchmark
    def test_parse_100_files(self, realistic_stack):
        """Must parse 100 files in < 5 seconds"""
        
        files = list(realistic_stack.glob("**/compose.yaml"))[:100]
        
        start = time.time()
        for file in files:
            parse_compose_file(file)
        elapsed = time.time() - start
        
        assert elapsed < 5.0, f"Parsing took {elapsed:.2f}s, must be < 5.0s"
    
    @pytest.mark.benchmark
    def test_memory_usage(self, large_stack):
        """Must stay under 200MB for 100 files"""
        
        process = psutil.Process(os.getpid())
        initial_memory = process.memory_info().rss / 1024 / 1024  # MB
        
        # Parse 100 files
        files = list(large_stack.glob("**/compose.yaml"))[:100]
        for file in files:
            parse_compose_file(file)
        
        peak_memory = process.memory_info().rss / 1024 / 1024
        memory_used = peak_memory - initial_memory
        
        assert memory_used < 200, f"Used {memory_used:.1f}MB, must be < 200MB"
    
    @pytest.mark.benchmark
    def test_cli_startup_time(self):
        """CLI must start in < 500ms"""
        
        start = time.time()
        result = subprocess.run(
            ['composearr', '--version'],
            capture_output=True
        )
        elapsed = time.time() - start
        
        assert elapsed < 0.5, f"Startup took {elapsed:.2f}s, must be < 0.5s"
```

### Optimization Requirements

**If performance tests fail, Code Claude must:**

1. **Profile the bottleneck:**
```python
# Use cProfile to find slow code
python -m cProfile -o profile.stats -m composearr audit /path/to/stack
python -m pstats profile.stats

# Analyze with snakeviz
snakeviz profile.stats
```

2. **Optimize common paths:**
```python
# Bad: Re-parsing same file multiple times
for rule in rules:
    compose = parse_compose_file(path)  # SLOW!
    rule.check(compose)

# Good: Parse once, reuse
compose = parse_compose_file(path)
for rule in rules:
    rule.check(compose)
```

3. **Lazy loading:**
```python
# Bad: Load all features at import time
from composearr.smart_features import TagAnalyzer, SystemProfiler, HealthcheckHelper

# Good: Import only when needed
def suggest_tag(image: str):
    from composearr.smart_features import TagAnalyzer  # Lazy
    analyzer = TagAnalyzer()
    return analyzer.analyze(image)
```

4. **Parallel processing (if needed):**
```python
from concurrent.futures import ThreadPoolExecutor

def scan_files_parallel(files: List[Path]) -> List[ComposeFile]:
    """Parse files in parallel (if > 50 files)"""
    
    if len(files) < 50:
        # Sequential for small stacks
        return [parse_compose_file(f) for f in files]
    
    # Parallel for large stacks
    with ThreadPoolExecutor(max_workers=4) as executor:
        return list(executor.map(parse_compose_file, files))
```

---

## 2. CI/CD INTEGRATION (MUST BE PERFECT)

### GitHub Action

Code Claude must create a reusable GitHub Action:

```yaml
# .github/actions/composearr-action/action.yml
name: 'ComposeArr Lint'
description: 'Lint Docker Compose files with ComposeArr'
author: 'Judd Howie'

branding:
  icon: 'check-circle'
  color: 'blue'

inputs:
  path:
    description: 'Path to scan for compose files'
    required: false
    default: '.'
  
  severity:
    description: 'Minimum severity to report (error, warning, info)'
    required: false
    default: 'error'
  
  fail-on:
    description: 'Fail workflow on this severity (error, warning, never)'
    required: false
    default: 'error'
  
  config:
    description: 'Path to .composearr.yml config file'
    required: false
    default: ''
  
  ignore:
    description: 'Comma-separated list of rules to ignore'
    required: false
    default: ''

outputs:
  errors:
    description: 'Number of errors found'
    value: ${{ steps.audit.outputs.errors }}
  
  warnings:
    description: 'Number of warnings found'
    value: ${{ steps.audit.outputs.warnings }}
  
  files-scanned:
    description: 'Number of files scanned'
    value: ${{ steps.audit.outputs.files }}

runs:
  using: 'composite'
  steps:
    - name: Set up Python
      uses: actions/setup-python@v5
      with:
        python-version: '3.11'
    
    - name: Install ComposeArr
      shell: bash
      run: pip install composearr
    
    - name: Run ComposeArr audit
      id: audit
      shell: bash
      run: |
        # Build command
        CMD="composearr audit ${{ inputs.path }}"
        CMD="$CMD --format github"
        CMD="$CMD --severity ${{ inputs.severity }}"
        
        if [ -n "${{ inputs.config }}" ]; then
          CMD="$CMD --config ${{ inputs.config }}"
        fi
        
        if [ -n "${{ inputs.ignore }}" ]; then
          CMD="$CMD --ignore ${{ inputs.ignore }}"
        fi
        
        # Run and capture output
        $CMD | tee audit.log
        
        # Parse results
        ERRORS=$(grep -c "::error" audit.log || true)
        WARNINGS=$(grep -c "::warning" audit.log || true)
        FILES=$(grep "Scanned:" audit.log | awk '{print $2}')
        
        echo "errors=$ERRORS" >> $GITHUB_OUTPUT
        echo "warnings=$WARNINGS" >> $GITHUB_OUTPUT
        echo "files=$FILES" >> $GITHUB_OUTPUT
        
        # Fail workflow if needed
        if [ "${{ inputs.fail-on }}" = "error" ] && [ $ERRORS -gt 0 ]; then
          echo "❌ Found $ERRORS error(s)"
          exit 1
        elif [ "${{ inputs.fail-on }}" = "warning" ] && [ $WARNINGS -gt 0 ]; then
          echo "⚠️ Found $WARNINGS warning(s)"
          exit 1
        fi
        
        echo "✅ ComposeArr audit passed"
```

**Example usage in user repo:**

```yaml
# .github/workflows/lint.yml
name: Lint Compose Files

on: [push, pull_request]

jobs:
  composearr:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      
      - name: Lint Docker Compose
        uses: juddh/composearr-action@v1
        with:
          path: ./docker
          severity: warning
          fail-on: error
```

### GitHub Annotations Format

```python
# src/composearr/formatters/github.py

def format_github_annotations(issues: List[LintIssue]) -> str:
    """
    Format issues as GitHub Actions annotations
    
    Syntax:
      ::error file={name},line={line},col={col}::{message}
      ::warning file={name},line={line},col={col}::{message}
      ::notice file={name},line={line},col={col}::{message}
    
    These appear as inline annotations in PR diffs!
    """
    
    output = []
    
    for issue in issues:
        # Map severity to GitHub level
        if issue.severity == Severity.ERROR:
            level = 'error'
        elif issue.severity == Severity.WARNING:
            level = 'warning'
        else:
            level = 'notice'
        
        # Build annotation
        parts = [f"file={issue.file_path}"]
        
        if issue.line:
            parts.append(f"line={issue.line}")
        
        if issue.column:
            parts.append(f"col={issue.column}")
        
        location = ','.join(parts)
        
        # Format message
        message = f"{issue.rule_id}: {issue.message}"
        
        if issue.suggested_fix:
            message += f" | Fix: {issue.suggested_fix}"
        
        output.append(f"::{level} {location}::{message}")
    
    return '\n'.join(output)
```

### GitLab CI Integration

```yaml
# .gitlab-ci.yml template
composearr-lint:
  stage: test
  image: python:3.11
  script:
    - pip install composearr
    - composearr audit . --format json > audit.json
  artifacts:
    reports:
      codequality: audit.json
    paths:
      - audit.json
    when: always
```

### JSON Format for CI

```python
# Must output Code Quality format for GitLab
{
  "version": "15.0.0",
  "vulnerabilities": [],
  "remediations": [],
  "dependency_files": [],
  "scan": {
    "scanner": {
      "id": "composearr",
      "name": "ComposeArr",
      "version": "0.1.0",
      "vendor": {
        "name": "BrainArr"
      }
    },
    "type": "sast",
    "start_time": "2026-02-16T00:00:00",
    "end_time": "2026-02-16T00:00:05",
    "status": "success"
  }
}
```

---

## 3. PRE-COMMIT HOOK (MUST BE FLAWLESS)

### Installation

```yaml
# .pre-commit-config.yaml
repos:
  - repo: https://github.com/juddh/composearr
    rev: v0.1.0
    hooks:
      - id: composearr
        name: ComposeArr Lint
        entry: composearr audit
        language: python
        types: [yaml]
        files: compose\.ya?ml$
        args: ['--severity', 'error']
```

### Hook Requirements

**Code Claude must ensure:**

1. **Fast on single files** (< 1 second)
```python
# Pre-commit passes changed files, not whole directory
# Must be optimized for single-file checks

def audit_single_file(file_path: Path) -> List[LintIssue]:
    """Optimized single-file audit for pre-commit"""
    
    # Skip cross-file rules (too slow for pre-commit)
    rules = [r for r in ALL_RULES if r.scope != Scope.PROJECT]
    
    compose = parse_compose_file(file_path)
    
    issues = []
    for rule in rules:
        issues.extend(rule.check(compose))
    
    return issues
```

2. **Only errors in pre-commit** (warnings optional)
```bash
# Default: block on errors only
composearr audit --severity error

# Strict mode: block on warnings too
composearr audit --severity warning
```

3. **Staged files only**
```python
# Pre-commit hook should only check staged files
# Not the whole repo
```

---

## 4. SARIF OUTPUT (GitHub Code Scanning)

### SARIF 2.1.0 Format

```python
# src/composearr/formatters/sarif.py

def format_sarif(issues: List[LintIssue]) -> dict:
    """
    Format issues as SARIF 2.1.0 for GitHub Advanced Security
    
    Enables:
    - Security tab integration
    - Code scanning alerts
    - Trend tracking
    """
    
    return {
        "$schema": "https://raw.githubusercontent.com/oasis-tcs/sarif-spec/master/Schemata/sarif-schema-2.1.0.json",
        "version": "2.1.0",
        "runs": [
            {
                "tool": {
                    "driver": {
                        "name": "ComposeArr",
                        "version": "0.1.0",
                        "informationUri": "https://github.com/juddh/composearr",
                        "rules": [
                            {
                                "id": rule.id,
                                "name": rule.name,
                                "shortDescription": {
                                    "text": rule.description
                                },
                                "fullDescription": {
                                    "text": rule.rationale
                                },
                                "help": {
                                    "text": rule.fix_guidance,
                                    "markdown": rule.fix_guidance_markdown
                                },
                                "defaultConfiguration": {
                                    "level": self._severity_to_level(rule.severity)
                                },
                                "properties": {
                                    "tags": rule.tags,
                                    "precision": "high"
                                }
                            }
                            for rule in ALL_RULES
                        ]
                    }
                },
                "results": [
                    {
                        "ruleId": issue.rule_id,
                        "level": self._severity_to_level(issue.severity),
                        "message": {
                            "text": issue.message
                        },
                        "locations": [
                            {
                                "physicalLocation": {
                                    "artifactLocation": {
                                        "uri": str(issue.file_path),
                                        "uriBaseId": "%SRCROOT%"
                                    },
                                    "region": {
                                        "startLine": issue.line,
                                        "startColumn": issue.column
                                    }
                                }
                            }
                        ],
                        "fixes": [
                            {
                                "description": {
                                    "text": issue.suggested_fix
                                }
                            }
                        ] if issue.suggested_fix else []
                    }
                    for issue in issues
                ]
            }
        ]
    }
```

---

## 5. CONFIGURATION VALIDATION (BULLETPROOF)

### Schema Validation

```python
# src/composearr/config.py

from jsonschema import validate, ValidationError

CONFIG_SCHEMA = {
    "$schema": "http://json-schema.org/draft-07/schema#",
    "type": "object",
    "properties": {
        "rules": {
            "type": "object",
            "patternProperties": {
                "^[a-z-]+$": {
                    "enum": ["error", "warning", "info", "off"]
                }
            }
        },
        "ignore": {
            "type": "array",
            "items": {"type": "string"}
        }
    }
}

def validate_config(config_path: Path) -> None:
    """
    Validate .composearr.yml against schema
    
    Must catch:
    - Invalid YAML syntax
    - Unknown rule names
    - Invalid severity levels
    - Malformed glob patterns
    """
    
    # Parse YAML
    try:
        with open(config_path) as f:
            config = yaml.safe_load(f)
    except yaml.YAMLError as e:
        raise ConfigError(f"Invalid YAML in {config_path}: {e}")
    
    # Validate schema
    try:
        validate(config, CONFIG_SCHEMA)
    except ValidationError as e:
        raise ConfigError(f"Invalid config: {e.message}")
    
    # Validate rule names
    if 'rules' in config:
        for rule_name in config['rules']:
            if not is_valid_rule_name(rule_name):
                raise ConfigError(
                    f"Unknown rule: {rule_name}\n"
                    f"Run 'composearr rules' to see valid rule names"
                )
```

---

## 6. ERROR MESSAGES (WORLD-CLASS UX)

### Good vs Bad Error Messages

**BAD (what not to do):**
```
Error: Parse failed
Error: Invalid compose file
Error: Port conflict
```

**GOOD (what Code Claude must do):**
```
Error: Failed to parse sonarr/compose.yaml
  Line 15: Invalid YAML syntax
  Expected key-value pair, got: "invalid - syntax here"
  
  Fix: Check YAML syntax at line 15
  
Error: Port conflict on 8080
  sonarr/compose.yaml (line 7) → ports: ["8080:8989"]
  radarr/compose.yaml (line 7) → ports: ["8080:7878"]
  
  Only one service can bind to port 8080.
  
  Fix: Change one service to use a different port:
    - "8081:7878"  (for radarr)
  
  Or bind to different interfaces:
    - "127.0.0.1:8080:8989"  (sonarr on localhost)
    - "192.168.1.10:8080:7878"  (radarr on LAN IP)
```

### Error Message Template

```python
class LintIssue:
    """Lint issue with perfect error messages"""
    
    def format_terminal(self) -> str:
        """Format for terminal with Rich"""
        
        parts = []
        
        # Header with severity
        if self.severity == Severity.ERROR:
            parts.append(f"[bold red]✖ {self.rule_id}[/] [red](error)[/]")
        elif self.severity == Severity.WARNING:
            parts.append(f"[bold yellow]⚠ {self.rule_id}[/] [yellow](warning)[/]")
        else:
            parts.append(f"[bold blue]ℹ {self.rule_id}[/] [blue](info)[/]")
        
        # Message
        parts.append(f": {self.message}")
        
        # Location
        if self.file_path and self.line:
            parts.append(f"\n  [dim]{self.file_path}:{self.line}[/]")
        
        # Code context (if available)
        if self.context_lines:
            parts.append(self._format_context())
        
        # Fix suggestion
        if self.suggested_fix:
            parts.append(f"\n  [green]Fix:[/] {self.suggested_fix}")
        
        # Learn more link
        if self.learn_more:
            parts.append(f"\n  [blue underline]{self.learn_more}[/]")
        
        return ''.join(parts)
```

---

## 7. CACHING (PERFORMANCE MULTIPLIER)

### File Change Detection

```python
# src/composearr/cache.py

import hashlib
import json
from pathlib import Path

class ResultsCache:
    """Cache lint results to avoid re-scanning unchanged files"""
    
    CACHE_VERSION = "1.0"
    CACHE_FILE = Path.home() / ".cache" / "composearr" / "results.json"
    
    def __init__(self):
        self.cache = self._load_cache()
    
    def get_cached_result(self, file_path: Path) -> Optional[List[LintIssue]]:
        """Get cached result if file hasn't changed"""
        
        file_hash = self._compute_hash(file_path)
        cache_key = str(file_path)
        
        if cache_key in self.cache:
            cached = self.cache[cache_key]
            
            if cached['hash'] == file_hash:
                # File unchanged, return cached result
                return cached['issues']
        
        return None
    
    def cache_result(
        self,
        file_path: Path,
        issues: List[LintIssue]
    ) -> None:
        """Cache result for this file"""
        
        file_hash = self._compute_hash(file_path)
        
        self.cache[str(file_path)] = {
            'hash': file_hash,
            'issues': [issue.to_dict() for issue in issues],
            'timestamp': time.time()
        }
        
        self._save_cache()
    
    def _compute_hash(self, file_path: Path) -> str:
        """Compute SHA256 hash of file content"""
        sha256 = hashlib.sha256()
        
        with open(file_path, 'rb') as f:
            while chunk := f.read(8192):
                sha256.update(chunk)
        
        return sha256.hexdigest()
```

### Cache Invalidation

```python
def audit_with_cache(files: List[Path]) -> List[LintIssue]:
    """Audit with intelligent caching"""
    
    cache = ResultsCache()
    all_issues = []
    files_to_scan = []
    
    # Check cache first
    for file in files:
        cached = cache.get_cached_result(file)
        
        if cached:
            all_issues.extend(cached)
        else:
            files_to_scan.append(file)
    
    # Scan uncached files
    if files_to_scan:
        new_issues = run_audit(files_to_scan)
        
        # Cache results
        for file in files_to_scan:
            file_issues = [i for i in new_issues if i.file_path == file]
            cache.cache_result(file, file_issues)
        
        all_issues.extend(new_issues)
    
    return all_issues
```

---

## 8. WATCH MODE (DEVELOPER EXPERIENCE)

### File Watcher

```python
# src/composearr/watch.py

from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

class ComposeWatcher(FileSystemEventHandler):
    """Watch compose files for changes and re-lint"""
    
    def __init__(self, path: Path):
        self.path = path
        self.last_run = {}
    
    def on_modified(self, event):
        """File was modified"""
        
        if event.is_directory:
            return
        
        if not event.src_path.endswith(('compose.yaml', 'compose.yml')):
            return
        
        # Debounce (don't re-run if changed < 1 second ago)
        file_path = Path(event.src_path)
        now = time.time()
        
        if file_path in self.last_run:
            if now - self.last_run[file_path] < 1.0:
                return
        
        self.last_run[file_path] = now
        
        # Re-lint this file
        console.print(f"\n[dim]Change detected: {file_path}[/]")
        self.lint_file(file_path)
    
    def lint_file(self, file_path: Path):
        """Lint single file and show results"""
        
        issues = audit_single_file(file_path)
        
        if not issues:
            console.print(f"[green]✓ {file_path.name} - no issues[/]")
        else:
            console.print(f"\n[bold]{file_path}[/]")
            for issue in issues:
                console.print(issue.format_terminal())

def watch(path: Path):
    """Watch mode - continuously monitor compose files"""
    
    console.print(f"[bold]👀 Watching {path} for changes...[/]")
    console.print("[dim]Press Ctrl+C to stop[/]\n")
    
    event_handler = ComposeWatcher(path)
    observer = Observer()
    observer.schedule(event_handler, str(path), recursive=True)
    observer.start()
    
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        observer.stop()
        console.print("\n[dim]Stopped watching[/]")
    
    observer.join()
```

---

## 9. LANGUAGE SERVER PROTOCOL (FUTURE)

### LSP Server Spec

```python
"""
ComposeArr Language Server

Provides real-time linting in VS Code, Neovim, etc.

Features:
- Live error highlighting
- Hover tooltips with fix suggestions
- Code actions (apply fixes)
- Completion for common patterns
"""

# Not required for v0.1 but architecture must support it
```

---

## 10. RELEASE CHECKLIST

### Before v0.1 Ships

Code Claude must verify:

- [ ] All 10 rules implemented and tested
- [ ] Judd's 35-service stack scans without errors
- [ ] Performance benchmarks pass
- [ ] All output formats work (console, JSON, GitHub, SARIF)
- [ ] GitHub Action tested in real repo
- [ ] Pre-commit hook tested
- [ ] Config validation bulletproof
- [ ] Error messages are world-class
- [ ] Documentation complete
- [ ] PyPI package builds successfully
- [ ] No TODOs or FIXMEs in production code
- [ ] Test coverage > 80%
- [ ] No memory leaks
- [ ] Works on Windows, macOS, Linux
- [ ] Python 3.11+ compatibility verified
- [ ] All dependencies pinned with version ranges

---

## THE FINAL BOSS: THE INTEGRATION TEST

```python
# tests/test_the_final_boss.py

def test_the_ultimate_integration():
    """
    The test that proves ComposeArr is production-ready
    
    This test must pass before v0.1 ships.
    No exceptions.
    """
    
    # 1. Scan Judd's real stack
    results = run_audit("C:/DockerContainers")
    
    # Must complete without crashing
    assert results is not None
    
    # Must find known issues
    assert any(i.rule_id == 'CA401' for i in results)  # PUID mismatch
    assert any(i.rule_id == 'CA301' for i in results)  # Port conflict
    
    # Must complete in reasonable time
    assert results.elapsed_time < 10.0
    
    # 2. Generate all output formats
    console_output = format_console(results)
    json_output = format_json(results)
    github_output = format_github(results)
    sarif_output = format_sarif(results)
    
    # All formats must be valid
    assert console_output
    assert json.loads(json_output)  # Valid JSON
    assert '::error' in github_output  # Valid GitHub
    assert sarif_output['version'] == '2.1.0'  # Valid SARIF
    
    # 3. Test edge cases
    edge_cases = [
        'tests/fixtures/edge_cases/empty.yaml',
        'tests/fixtures/edge_cases/comments-only.yaml',
        'tests/fixtures/edge_cases/nested-includes.yaml',
        'tests/fixtures/edge_cases/circular-extends.yaml',
        'tests/fixtures/edge_cases/port-ranges.yaml',
        'tests/fixtures/edge_cases/ipv6-ports.yaml',
        'tests/fixtures/edge_cases/yaml-anchors.yaml',
    ]
    
    for edge_case in edge_cases:
        # Must handle gracefully (no crashes)
        try:
            audit_single_file(Path(edge_case))
        except Exception as e:
            pytest.fail(f"Crashed on {edge_case}: {e}")
    
    # 4. Performance check
    start = time.time()
    audit_with_cache("C:/DockerContainers")  # Should use cache
    cached_time = time.time() - start
    
    assert cached_time < 1.0, "Cached audit must be < 1 second"
    
    # 5. Config validation
    test_configs = [
        '.composearr-valid.yml',
        '.composearr-invalid-rule.yml',
        '.composearr-invalid-severity.yml',
    ]
    
    # Valid config must load
    config = load_config(test_configs[0])
    assert config is not None
    
    # Invalid configs must raise clear errors
    with pytest.raises(ConfigError):
        load_config(test_configs[1])
    
    # 6. Suppression test
    suppressed = """
# composearr-ignore: CA001
services:
  test:
    image: nginx:latest
"""
    
    issues = audit_string(suppressed)
    assert not any(i.rule_id == 'CA001' for i in issues)
    
    # 7. CLI integration
    result = subprocess.run(
        ['composearr', 'audit', 'tests/fixtures'],
        capture_output=True,
        text=True
    )
    
    assert result.returncode in [0, 1]  # 0 = no issues, 1 = issues found
    assert 'ComposeArr' in result.stdout
    
    # If we get here, ComposeArr is ready to ship 🚀
    print("\n" + "="*60)
    print("✅ ALL INTEGRATION TESTS PASSED")
    print("🚀 ComposeArr v0.1.0 is READY TO SHIP")
    print("="*60)
```

---

## CODE CLAUDE: IF YOU COMPLETE ALL OF THIS...

You're not just a code generator.

You're a **craftsman**.

And ComposeArr will be **legendary**.

**No pressure.** 😈🔥

---

**GO BUILD.** 💪
