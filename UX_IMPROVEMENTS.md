# ComposeArr UX Improvements - URGENT

Based on real-world testing with 35+ service stack.

---

## 1. PROGRESS INDICATORS (CRITICAL)

### Problem
Scanning 35 files takes time. User feels abandoned with no feedback.

### Solution
Add Rich progress bars for all operations:

```python
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn

def scan_directory(path: Path) -> List[ComposeFile]:
    """Scan directory with progress indicator"""
    
    # First pass: discover files
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        transient=True
    ) as progress:
        task = progress.add_task("Discovering compose files...", total=None)
        files = list(path.rglob("**/compose.yaml"))
        progress.update(task, completed=True)
    
    # Second pass: parse files
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
    ) as progress:
        task = progress.add_task(
            f"Parsing {len(files)} compose files...",
            total=len(files)
        )
        
        parsed = []
        for file_path in files:
            parsed.append(parse_compose(file_path))
            progress.advance(task)
    
    return parsed

def run_rules(files: List[ComposeFile]) -> List[LintIssue]:
    """Run rules with progress"""
    
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
    ) as progress:
        # Per-file rules
        file_task = progress.add_task(
            "Running per-file rules...",
            total=len(files)
        )
        
        issues = []
        for file in files:
            issues.extend(check_file_rules(file))
            progress.advance(file_task)
        
        # Cross-file rules
        cross_task = progress.add_task(
            "Running cross-file analysis...",
            total=4  # Number of cross-file rules
        )
        
        issues.extend(check_port_conflicts(files))
        progress.advance(cross_task)
        
        issues.extend(check_puid_mismatch(files))
        progress.advance(cross_task)
        
        # etc...
    
    return issues
```

**Add to ALL commands that take >1 second:**
- `composearr audit` (file discovery + parsing + rules)
- `composearr ports` (file scanning)
- Tag analyzer API calls (when fetching from Docker Hub)

---

## 2. OUTPUT MANAGEMENT (CRITICAL)

### Problem
35 services = huge wall of text. Unusable.

### Solution A: Summary-First Output

```
🎯 ComposeArr Audit Results

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📊 Summary
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Scanned:  35 files, 42 services
Issues:   4 errors, 12 warnings, 8 info

By Rule:
  CA301 (port-conflict)        1 error
  CA401 (puid-pgid-mismatch)   1 error
  CA101 (inline-secrets)       2 errors
  CA001 (no-latest-tag)        8 warnings
  CA201 (require-healthcheck)  4 warnings

By File:
  gluetun/compose.yaml         2 errors
  plex/compose.yaml            1 warning
  qbittorrent/compose.yaml     1 warning
  ... (32 files with no issues)

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🔴 Errors (must fix)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

[Only show ERRORS by default]

✖ CA301: Port conflict on 8080
  ├─ sonarr/compose.yaml (line 7)
  └─ radarr/compose.yaml (line 7)

✖ CA401: PUID mismatch across stack
  ├─ PUID=1000: sonarr, radarr, plex (8 services)
  ├─ PUID=568: qbittorrent, sabnzbd (2 services)
  └─ PUID=0: gluetun, huntarr (3 services)

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Run with --severity warning to see all warnings
Run with --verbose for full file context
Run with --format json for machine-readable output
```

**Default behavior:**
- Show summary
- Show ONLY errors
- Collapse warnings/info into counts

**Flags to expand:**
```bash
--severity warning  # Show errors + warnings
--severity info     # Show everything
--verbose          # Show full file context for each issue
--group-by file    # Group by file instead of rule
```

### Solution B: Interactive Filter (v0.2)

For terminal UI mode:
```bash
composearr audit --interactive

# Shows TUI with:
# - Filterable issue list
# - Group by rule/file/severity
# - Navigate with arrow keys
# - Press 'f' to see fix suggestion
# - Press 'i' to ignore this issue
```

---

## 3. MANAGEMENT PLATFORM DETECTION (CRITICAL)

### Problem
Komodo, Dockge, Portainer store compose files in their own directories.
These are duplicates of the "real" stack and should be ignored.

### Solution: Smart Detection + Warning

```python
# src/composearr/scanner/platform_detector.py

MANAGEMENT_PLATFORMS = {
    'komodo': {
        'indicators': ['komodo', '.komodo'],
        'compose_location': 'stacks/**/compose.yaml',
        'warning': 'Detected Komodo-managed stacks. These may be duplicates.'
    },
    'dockge': {
        'indicators': ['dockge', 'opt/dockge'],
        'compose_location': 'stacks/**/compose.yaml',
        'warning': 'Detected Dockge-managed stacks. These may be duplicates.'
    },
    'portainer': {
        'indicators': ['portainer', 'docker/compose'],
        'compose_location': 'data/compose/**/docker-compose.yml',
        'warning': 'Detected Portainer-managed stacks. These may be duplicates.'
    },
}

def detect_management_platform(scan_path: Path) -> Optional[dict]:
    """Detect if path contains managed stacks"""
    path_str = str(scan_path).lower()
    
    for platform, config in MANAGEMENT_PLATFORMS.items():
        for indicator in config['indicators']:
            if indicator in path_str:
                return {
                    'platform': platform,
                    'warning': config['warning']
                }
    
    return None

def discover_compose_files(root_path: Path) -> List[Path]:
    """Discover compose files with platform detection"""
    
    # Check for management platform
    platform = detect_management_platform(root_path)
    
    if platform:
        console.print(f"\n[yellow]⚠️  {platform['warning']}[/]")
        console.print(f"[dim]Scanning {platform['platform']}-managed stacks[/]\n")
        
        # Ask user what to do
        choice = typer.confirm(
            "Scan these files anyway? (May include duplicates)",
            default=False
        )
        
        if not choice:
            console.print("[dim]Skipping managed stacks. Specify a different path.[/]")
            return []
    
    # Continue normal discovery
    return list(root_path.rglob("**/compose.yaml"))
```

**Better approach - Deduplication:**

```python
def deduplicate_stacks(files: List[Path]) -> List[Path]:
    """
    Detect duplicate stacks by comparing:
    - Service names
    - Image names
    - Container names
    
    If two compose files define the same services,
    prefer the one NOT in a management platform directory.
    """
    
    stacks = {}  # service_name -> List[Path]
    
    for file in files:
        compose = parse_compose(file)
        service_names = frozenset(compose['services'].keys())
        
        if service_names not in stacks:
            stacks[service_names] = []
        stacks[service_names].append(file)
    
    # For each duplicate set, prefer non-managed location
    deduplicated = []
    for service_set, file_list in stacks.items():
        if len(file_list) == 1:
            deduplicated.append(file_list[0])
        else:
            # Multiple files with same services - dedup
            preferred = choose_canonical_file(file_list)
            deduplicated.append(preferred)
            
            # Warn about skipped duplicates
            for skipped in file_list:
                if skipped != preferred:
                    console.print(
                        f"[dim]ℹ️  Skipping duplicate: {skipped} "
                        f"(using {preferred} instead)[/]"
                    )
    
    return deduplicated

def choose_canonical_file(files: List[Path]) -> Path:
    """Choose the 'real' file when duplicates exist"""
    
    # Prefer files NOT in management directories
    management_indicators = ['komodo', 'dockge', 'portainer']
    
    for file in files:
        path_str = str(file).lower()
        if not any(ind in path_str for ind in management_indicators):
            return file  # This is the real one
    
    # If all are managed, just pick first
    return files[0]
```

---

## 4. PORT CONFLICT INTELLIGENCE (IMPORTANT)

### Problem
Users intentionally change default ports to avoid conflicts.
We need to understand:
1. Image's default port
2. User's override
3. Entire port schema

### Solution: Port Intelligence

```python
# src/composearr/analyzers/port_analyzer.py

# Database of default ports
DEFAULT_PORTS = {
    'sonarr': 8989,
    'radarr': 7878,
    'prowlarr': 9696,
    'bazarr': 6767,
    'plex': 32400,
    'jellyfin': 8096,
    'qbittorrent': 8080,
    # ... etc
}

@dataclass
class PortMapping:
    service: str
    image: str
    host_port: int
    container_port: int
    protocol: str
    host_ip: str
    is_default_mapping: bool
    file_path: str
    line: int

class PortAnalyzer:
    """Intelligent port conflict detection"""
    
    def detect_conflicts(self, all_files: List[ComposeFile]) -> List[LintIssue]:
        """
        Detect port conflicts with intelligence about:
        - Default vs custom ports
        - Intentional overrides
        - Common conflict patterns
        """
        
        all_mappings = self._collect_port_mappings(all_files)
        conflicts = self._find_conflicts(all_mappings)
        
        issues = []
        for conflict in conflicts:
            # Determine if this looks intentional
            if self._is_intentional_override(conflict):
                # Downgrade to warning, not error
                severity = Severity.WARNING
                message = (
                    f"Port {conflict.port} used by {conflict.services}. "
                    f"This may be intentional to avoid conflicts."
                )
            else:
                # Likely accidental
                severity = Severity.ERROR
                message = (
                    f"Port conflict: {conflict.port} used by "
                    f"{', '.join(conflict.services)}"
                )
            
            issues.append(LintIssue(
                rule_id="CA301",
                severity=severity,
                message=message,
                suggested_fix=self._suggest_port_fix(conflict)
            ))
        
        return issues
    
    def _is_intentional_override(self, conflict: PortConflict) -> bool:
        """
        Detect if port remapping looks intentional
        
        Indicators:
        - User changed from default port to custom port
        - Custom port follows a pattern (8081, 8082, 8083...)
        - Container port is still default (just host port changed)
        """
        
        for mapping in conflict.mappings:
            default_port = self._get_default_port(mapping.image)
            
            if default_port:
                # Check if container port is still default
                if mapping.container_port == default_port:
                    # User only changed host port - likely intentional
                    return True
        
        return False
    
    def _suggest_port_fix(self, conflict: PortConflict) -> str:
        """Suggest next available port"""
        
        # Find next available port in sequence
        base_port = conflict.port
        next_port = self._find_next_available(base_port, conflict.all_used_ports)
        
        return f"""
One service should use a different host port:
  - "{next_port}:{conflict.mappings[0].container_port}"

Or bind to different interfaces:
  - "127.0.0.1:{base_port}:{conflict.mappings[0].container_port}"
  - "192.168.1.10:{base_port}:{conflict.mappings[1].container_port}"
"""
```

---

## 5. OUTPUT FORMATTING OPTIONS

Add these flags:

```python
@app.command()
def audit(
    path: str = ".",
    severity: str = "error",  # error, warning, info
    verbose: bool = False,
    group_by: str = "rule",  # rule, file, severity
    limit: int = None,  # Show only first N issues
    summary_only: bool = False,  # Just show counts
):
    """Audit compose files"""
    
    if summary_only:
        # Just show summary, no details
        show_summary(results)
        return
    
    if limit:
        # Show first N issues only
        results = results[:limit]
        console.print(f"\n[dim]Showing first {limit} issues. "
                     f"Use --limit 0 for all.[/]")
```

---

## IMPLEMENTATION PRIORITY

**Phase 1 (Immediate):**
1. ✅ Progress indicators everywhere
2. ✅ Summary-first output format
3. ✅ `--severity error` default (only show errors)

**Phase 2 (This week):**
4. ✅ Management platform detection + deduplication
5. ✅ Smart port conflict detection
6. ✅ Output grouping options

**Phase 3 (v0.2):**
7. Interactive TUI mode
8. Watch mode with live updates

---

## EXAMPLE OUTPUT (IMPROVED)

```bash
$ composearr audit C:\DockerContainers

Discovering compose files...  ✓ Found 35 files
Parsing compose files...      ████████████████████ 100%
Running per-file rules...     ████████████████████ 100%
Running cross-file analysis... ████████████████████ 100%

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🎯 ComposeArr Audit Complete
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Scanned:  35 files, 42 services, 0 duplicates skipped
Found:    4 errors, 12 warnings, 8 info

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🔴 Errors (4)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

[Detailed errors here...]

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

✓ 28 files passed all checks
⚠ 7 files have warnings (use --severity warning to see)
ℹ 5 files have info notices (use --severity info to see)

Next steps:
  composearr audit --severity warning  # See all warnings
  composearr audit --format json       # Machine-readable output
  composearr ports                     # View port allocation
```

Much more manageable! ✨

---

## CODE CLAUDE ACTION ITEMS

1. **Add progress bars** to all operations (use Rich Progress)
2. **Change default output** to summary + errors only
3. **Add --severity flag** to control verbosity
4. **Detect management platforms** and warn about duplicates
5. **Smart port conflict** detection with intentional override detection

**Priority: High - This affects usability dramatically**
