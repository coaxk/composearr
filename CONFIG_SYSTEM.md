# ComposeArr Configuration System

Complete specification for `.composearr.yml` config files and inline suppression.

---

## Config File Hierarchy

ComposeArr looks for config in this priority order (highest to lowest):

```
1. CLI flags
   composearr audit --severity error --ignore CA001

2. Project config
   /path/to/project/.composearr.yml
   (Settings for THIS specific stack)

3. User config
   ~/.composearr.yml
   (Personal defaults across all projects)

4. Built-in defaults
   (Hardcoded in ComposeArr source)
```

**Example flow:**
- Built-in: CA001 is "warning"
- User config: CA001 = "off" (globally disabled)
- Project config: CA001 = "error" (THIS stack requires version pins)
- CLI flag: `--ignore CA001` (override for this single run)
- **Result:** CA001 is ignored for this run

---

## .composearr.yml Format

### Minimal Config

```yaml
# .composearr.yml
# ComposeArr configuration

# Override rule severity
rules:
  no-latest-tag: warning
  no-inline-secrets: error
  require-healthcheck: off
```

### Complete Config

```yaml
# .composearr.yml
# ComposeArr configuration for [project name]

# ─────────────────────────────────────────────────────────────
# Rule Configuration
# ─────────────────────────────────────────────────────────────

rules:
  # Images (CA0xx)
  no-latest-tag: warning           # CA001
  
  # Security (CA1xx)
  no-inline-secrets: error         # CA101
  
  # Reliability (CA2xx)
  require-healthcheck: warning     # CA201
  no-fake-healthcheck: warning     # CA202
  require-restart-policy: warning  # CA203
  
  # Networking (CA3xx)
  port-conflict: error             # CA301
  
  # Consistency (CA4xx)
  puid-pgid-mismatch: error        # CA401
  umask-inconsistent: warning      # CA402
  missing-timezone: warning        # CA403
  
  # Arr Stack (CA6xx)
  hardlink-path-mismatch: warning  # CA601

# ─────────────────────────────────────────────────────────────
# Ignore Patterns
# ─────────────────────────────────────────────────────────────

ignore:
  # Ignore entire directories
  - testing/
  - legacy/
  - experiments/
  
  # Ignore specific files
  - old-stack/compose.yaml
  - backup-configs/*.yaml
  
  # Ignore specific services
  services:
    - watchtower     # Intentionally uses :latest
    - diun          # No healthcheck needed

# ─────────────────────────────────────────────────────────────
# Custom Thresholds
# ─────────────────────────────────────────────────────────────

thresholds:
  # Entropy threshold for secret detection (0.0-1.0)
  # Higher = more strict (fewer false positives)
  secret_entropy: 0.6
  
  # Minimum string length to check for secrets
  secret_min_length: 20

# ─────────────────────────────────────────────────────────────
# Trusted Registries
# ─────────────────────────────────────────────────────────────

# Images from these registries won't trigger warnings
trusted_registries:
  - lscr.io              # LinuxServer.io
  - ghcr.io/hotio        # Hotio
  - ghcr.io/linuxserver  # LinuxServer.io (GitHub)
  - docker.io/library    # Official Docker images

# ─────────────────────────────────────────────────────────────
# Output Configuration
# ─────────────────────────────────────────────────────────────

output:
  # Show full file paths or relative paths
  paths: relative  # or "absolute"
  
  # Show fix suggestions
  show_fixes: true
  
  # Show "Learn More" links
  show_links: true
  
  # Colorize output (auto-detected in CI)
  color: auto  # or "always", "never"

# ─────────────────────────────────────────────────────────────
# Arr Stack Specific
# ─────────────────────────────────────────────────────────────

arrstack:
  # Services considered part of the arr stack
  services:
    - sonarr
    - radarr
    - lidarr
    - readarr
    - prowlarr
    - bazarr
  
  # Expected PUID/PGID for arr stack
  # (used to detect mismatches)
  expected_puid: 1000
  expected_pgid: 1000
  
  # Expected UMASK for arr stack
  expected_umask: "002"
  
  # Enforce TRaSH Guides folder structure
  enforce_trash_structure: true
```

---

## Inline Suppression

### Syntax

```yaml
# composearr-ignore: RULE_ID
# or
# composearr-ignore: RULE_NAME
# or
# composearr-ignore: RULE_ID,RULE_ID,RULE_ID
```

### Examples

**Suppress single rule:**
```yaml
services:
  watchtower:
    # composearr-ignore: CA001
    image: containrrr/watchtower:latest
    # Watchtower intentionally uses :latest to update itself
```

**Suppress multiple rules:**
```yaml
services:
  testing:
    # composearr-ignore: CA001,CA201,CA203
    image: nginx:latest
    # This is a test container, ignore all warnings
```

**Suppress by rule name:**
```yaml
services:
  diun:
    # composearr-ignore: no-healthcheck
    image: ghcr.io/crazy-max/diun:latest
```

**Suppress for specific line:**
```yaml
environment:
  # This is test data, not a real secret
  - API_KEY=test_key_12345  # composearr-ignore: CA101
```

**Suppress entire service:**
```yaml
services:
  # composearr-ignore-service
  legacy_app:
    image: oldimage:latest
    # All rules ignored for this service
```

**Suppress entire file:**
```yaml
# composearr-ignore-file
# This is a legacy stack, don't lint it

services:
  old_service:
    image: ancient:latest
```

### Suppression Scope

| Comment | Scope | Effect |
|---------|-------|--------|
| `# composearr-ignore: CA001` above service | Service block | Ignores CA001 for this service only |
| `# composearr-ignore: CA001` end of line | That line only | Ignores CA001 for this specific line |
| `# composearr-ignore-service` above service | Entire service | Ignores ALL rules for this service |
| `# composearr-ignore-file` at top of file | Entire file | Ignores ALL rules for this file |

---

## Configuration Schema

For validation and IDE autocomplete, here's the JSON Schema:

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "title": "ComposeArr Configuration",
  "type": "object",
  "properties": {
    "rules": {
      "type": "object",
      "properties": {
        "no-latest-tag": {"$ref": "#/definitions/severity"},
        "no-inline-secrets": {"$ref": "#/definitions/severity"},
        "require-healthcheck": {"$ref": "#/definitions/severity"},
        "no-fake-healthcheck": {"$ref": "#/definitions/severity"},
        "require-restart-policy": {"$ref": "#/definitions/severity"},
        "port-conflict": {"$ref": "#/definitions/severity"},
        "puid-pgid-mismatch": {"$ref": "#/definitions/severity"},
        "umask-inconsistent": {"$ref": "#/definitions/severity"},
        "missing-timezone": {"$ref": "#/definitions/severity"},
        "hardlink-path-mismatch": {"$ref": "#/definitions/severity"}
      }
    },
    "ignore": {
      "type": "array",
      "items": {"type": "string"},
      "description": "Glob patterns for files/directories to ignore"
    },
    "thresholds": {
      "type": "object",
      "properties": {
        "secret_entropy": {
          "type": "number",
          "minimum": 0,
          "maximum": 1,
          "default": 0.6
        },
        "secret_min_length": {
          "type": "integer",
          "minimum": 1,
          "default": 20
        }
      }
    },
    "trusted_registries": {
      "type": "array",
      "items": {"type": "string"},
      "default": ["lscr.io", "ghcr.io/hotio", "ghcr.io/linuxserver"]
    },
    "output": {
      "type": "object",
      "properties": {
        "paths": {
          "type": "string",
          "enum": ["relative", "absolute"],
          "default": "relative"
        },
        "show_fixes": {"type": "boolean", "default": true},
        "show_links": {"type": "boolean", "default": true},
        "color": {
          "type": "string",
          "enum": ["auto", "always", "never"],
          "default": "auto"
        }
      }
    },
    "arrstack": {
      "type": "object",
      "properties": {
        "services": {
          "type": "array",
          "items": {"type": "string"}
        },
        "expected_puid": {"type": "integer"},
        "expected_pgid": {"type": "integer"},
        "expected_umask": {"type": "string"},
        "enforce_trash_structure": {"type": "boolean"}
      }
    }
  },
  "definitions": {
    "severity": {
      "type": "string",
      "enum": ["error", "warning", "info", "off"]
    }
  }
}
```

---

## Default Configuration

Built into ComposeArr if no config file exists:

```yaml
# Built-in defaults (embedded in ComposeArr)

rules:
  no-latest-tag: warning
  no-inline-secrets: error
  require-healthcheck: warning
  no-fake-healthcheck: warning
  require-restart-policy: warning
  port-conflict: error
  puid-pgid-mismatch: error
  umask-inconsistent: warning
  missing-timezone: warning
  hardlink-path-mismatch: warning

ignore: []

thresholds:
  secret_entropy: 0.6
  secret_min_length: 20

trusted_registries:
  - lscr.io
  - ghcr.io/hotio
  - ghcr.io/linuxserver
  - docker.io/library

output:
  paths: relative
  show_fixes: true
  show_links: true
  color: auto

arrstack:
  services:
    - sonarr
    - radarr
    - lidarr
    - readarr
    - prowlarr
    - bazarr
    - whisparr
  expected_puid: 1000
  expected_pgid: 1000
  expected_umask: "002"
  enforce_trash_structure: true
```

---

## Config File Generation

### composearr init

Interactive wizard to generate `.composearr.yml`:

```bash
$ composearr init

🎯 ComposeArr Configuration Setup

Where should we save the config?
1. Project config (./.composearr.yml) - recommended
2. User config (~/.composearr.yml)
> 1

What type of stack are you running?
1. Media server (*arr stack)
2. General homelab
3. Production services
4. Custom
> 1

Detected services in your stack:
  ✓ sonarr, radarr, prowlarr, bazarr
  ✓ qbittorrent, sabnzbd
  ✓ plex

Configure PUID/PGID consistency?
Expected PUID [1000]: 1000
Expected PGID [1000]: 1000

Configure UMASK?
Expected UMASK [002]: 002

Enforce TRaSH Guides folder structure? [Y/n]: y

Enable strict mode (errors instead of warnings)? [y/N]: n

✅ Created .composearr.yml

Run 'composearr audit' to scan your stack!
```

---

## Usage Examples

### Override severity for one run
```bash
# Treat warnings as errors
composearr audit --severity error

# Only show errors
composearr audit --min-severity error

# Ignore specific rules
composearr audit --ignore CA001,CA002
```

### Use custom config
```bash
# Explicit config file
composearr audit --config /path/to/custom.yml

# Ignore config (use defaults only)
composearr audit --no-config
```

### Export current config
```bash
# Show effective config (after merging all sources)
composearr config show

# Show just the defaults
composearr config defaults

# Validate config file
composearr config validate
```

---

## Implementation Notes for Code Claude

### Config Loading Order

```python
def load_config() -> Config:
    # 1. Start with built-in defaults
    config = DEFAULT_CONFIG.copy()
    
    # 2. Merge user config if exists
    user_config_path = Path.home() / ".composearr.yml"
    if user_config_path.exists():
        config.merge(load_yaml(user_config_path))
    
    # 3. Merge project config if exists
    project_config_path = Path.cwd() / ".composearr.yml"
    if project_config_path.exists():
        config.merge(load_yaml(project_config_path))
    
    # 4. Apply CLI overrides
    config.apply_cli_args(args)
    
    return config
```

### Inline Suppression Parsing

```python
def parse_suppression_comment(line: str) -> set[str]:
    """Extract rule IDs from composearr-ignore comment"""
    match = re.search(r'#\s*composearr-ignore:\s*(.+)', line)
    if match:
        rules = match.group(1).strip()
        return {r.strip() for r in rules.split(',')}
    return set()

def is_suppressed(issue: LintIssue, yaml_lines: list[str]) -> bool:
    """Check if issue is suppressed by inline comment"""
    if issue.line is None:
        return False
    
    # Check line above
    if issue.line > 0:
        prev_line = yaml_lines[issue.line - 1]
        suppressed_rules = parse_suppression_comment(prev_line)
        if issue.rule_id in suppressed_rules or issue.rule_name in suppressed_rules:
            return True
    
    # Check same line (end-of-line comment)
    current_line = yaml_lines[issue.line]
    suppressed_rules = parse_suppression_comment(current_line)
    if issue.rule_id in suppressed_rules or issue.rule_name in suppressed_rules:
        return True
    
    return False
```

### Service-Level Suppression

```python
def get_service_suppressions(service_yaml: str) -> set[str]:
    """Get suppressions from # composearr-ignore-service comment"""
    lines = service_yaml.split('\n')
    for line in lines:
        if '# composearr-ignore-service' in line:
            return {'*'}  # Suppress all rules
    return set()
```

---

## NEXT STEPS

1. **Code Claude:** Implement config loading in `config.py`
2. **Code Claude:** Implement inline suppression parsing
3. **Us:** Design the `composearr init` interactive wizard flow
4. **Us:** Create example `.composearr.yml` files for different use cases

---

**Ready for the next piece?** We can tackle:
- Smart features implementation (tag analyzer, system profiler)
- Testing strategy
- CI/CD integration guide
