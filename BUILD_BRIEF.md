# ComposeArr — Definitive Build Brief

## What We're Building

A CLI-first Docker Compose hygiene linter and fixer. Think "hadolint for docker-compose"
with cross-file intelligence. No existing tool occupies this space.

---

## Technical Stack (Locked In)

| Component | Choice | Why |
|-----------|--------|-----|
| Language | **Python 3.11+** | Speed to market, rich ecosystem, your existing skill |
| CLI Framework | **Typer** | Modern type-hint API, built on Click, auto-help, subcommands |
| YAML Parser | **ruamel.yaml** | Preserves comments, key order, formatting on round-trip (critical for --fix) |
| Terminal Output | **Rich** | Tables, trees, syntax highlighting, diffs, progress — all-in-one, 50k+ stars |
| Interactive Prompts | **InquirerPy** | Fuzzy finder, checkbox, confirm — perfect for `init` flow |
| .env Parsing | **python-dotenv** (read) + custom line parser (round-trip) | dotenv for reading, custom for comment-preserving writes |
| Schema Validation | **jsonschema** + bundled compose-spec.json | First-pass structural validation |
| Config Format | **YAML** (`.composearr.yml`) | Natural for a YAML tool, users already know the format |
| Packaging | **PyPI** (`pip install composearr`) | Standard Python distribution, easy install |

### Dependencies (minimal)

```
typer[all]>=0.12.0        # CLI framework (includes Rich, shellingham)
ruamel.yaml>=0.18.0       # Comment-preserving YAML
python-dotenv>=1.0.0      # .env file parsing
jsonschema>=4.20.0        # Compose-spec schema validation
inquirerpy>=0.3.4         # Interactive prompts (init flow only)
```

Already available via Typer: `rich`, `click`, `colorama`, `shellingham`

---

## Architecture

```
composearr/
├── __init__.py                 # Version, metadata
├── __main__.py                 # python -m composearr
├── cli.py                      # Typer app — commands: audit, fix, init, ports, secrets
├── config.py                   # Pydantic model for .composearr.yml
├── models.py                   # LintIssue, Severity, PortMapping, FileReport
├── scanner/
│   ├── __init__.py
│   ├── discovery.py            # Find compose files + .env files in directory tree
│   ├── parser.py               # ruamel.yaml loading with error handling
│   ├── env_resolver.py         # .env loading, variable interpolation (${VAR:-default})
│   └── merge.py                # extends/include/override merging
├── rules/
│   ├── __init__.py             # Rule registry (auto-discovery)
│   ├── base.py                 # BaseRule abstract class + LintIssue dataclass
│   ├── CA0xx_images.py         # :latest tag, missing tag, no digest
│   ├── CA1xx_security.py       # Inline secrets, privileged, cap_add, docker.sock
│   ├── CA2xx_reliability.py    # Healthcheck, restart policy, resource limits, log rotation
│   ├── CA3xx_networking.py     # Port conflicts (cross-file!), host network, unbound ports
│   ├── CA4xx_consistency.py    # PUID/PGID mismatch, UMASK, TZ, env var format
│   ├── CA5xx_structure.py      # Deprecated version field, naming, key ordering
│   └── CA6xx_arrstack.py       # TRaSH compliance, hardlink paths, unified /data mount
├── formatters/
│   ├── __init__.py
│   ├── console.py              # Rich terminal output (default) — ruff-inspired
│   ├── json_fmt.py             # JSON output for scripting/CI
│   ├── github.py               # GitHub Actions annotations (::error, ::warning)
│   └── sarif.py                # SARIF 2.1.0 for GitHub Code Scanning (v2)
├── fixers/
│   ├── __init__.py
│   ├── base.py                 # BaseFixer abstract class
│   ├── secret_mover.py         # Move inline secrets to .env
│   ├── tag_pinner.py           # Replace :latest with specific version
│   ├── add_restart.py          # Add restart: unless-stopped
│   ├── add_logging.py          # Add logging config block
│   └── add_tz.py               # Add TZ variable
└── data/
    ├── compose-spec.json       # Bundled compose-spec JSON schema
    ├── default_config.yml      # Default .composearr.yml template
    └── secret_patterns.yml     # Regex patterns for secret detection
```

### Rule Base Class

```python
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum

class Severity(Enum):
    ERROR = "error"
    WARNING = "warning"
    INFO = "info"

class Scope(Enum):
    SERVICE = "service"     # Runs per-service
    FILE = "file"           # Runs per-compose-file
    PROJECT = "project"     # Runs across ALL files (cross-file analysis)

@dataclass
class LintIssue:
    rule_id: str            # CA001, CA101, etc.
    rule_name: str          # no-latest-tag
    severity: Severity
    message: str
    file_path: str
    line: int | None = None
    column: int | None = None
    service: str | None = None
    fix_available: bool = False
    suggested_fix: str | None = None
    learn_more: str | None = None  # URL to docs/TRaSH guide

class BaseRule(ABC):
    id: str                 # CA001
    name: str               # no-latest-tag
    severity: Severity      # Default severity (overridable in config)
    scope: Scope
    description: str
    category: str           # images, security, reliability, networking, consistency, arrstack

    @abstractmethod
    def check(self, context) -> list[LintIssue]:
        ...
```

### Two-Pass Architecture

**Pass 1 — Per-file analysis:**
Each compose file is parsed independently. Service-scope and file-scope rules run.
Results: list of LintIssues per file.

**Pass 2 — Cross-file correlation:**
All parsed files are fed into project-scope rules. These detect:
- Port conflicts across separate compose files
- container_name collisions
- PUID/PGID inconsistencies across the stack
- Network topology issues (services that should communicate but are on different networks)
- Duplicate/conflicting env vars across shared .env files

This two-pass design is ComposeArr's core differentiator.

---

## Rule Set (MVP — 20 Rules)

### CA0xx — Images (3 rules)

| ID | Name | Severity | Fix? | Description |
|----|------|----------|------|-------------|
| CA001 | no-latest-tag | warning | yes | Image uses `:latest` or has no tag |
| CA002 | no-digest-pin | info | no | Image has no `@sha256:` digest pin |
| CA003 | untrusted-registry | info | no | Image from unknown registry (configurable trusted list) |

### CA1xx — Security (5 rules)

| ID | Name | Severity | Fix? | Description |
|----|------|----------|------|-------------|
| CA101 | no-inline-secrets | error | yes | Secret value hardcoded in environment block |
| CA102 | no-privileged | error | no | Container runs in privileged mode |
| CA103 | no-docker-sock | warning | no | Docker socket mounted as volume |
| CA104 | no-cap-add-all | error | no | `cap_add: ALL` grants all capabilities |
| CA105 | unbound-port | warning | yes | Port published on 0.0.0.0 (all interfaces) |

### CA2xx — Reliability (5 rules)

| ID | Name | Severity | Fix? | Description |
|----|------|----------|------|-------------|
| CA201 | require-healthcheck | warning | no | Service has no healthcheck defined |
| CA202 | no-fake-healthcheck | warning | no | Healthcheck is `exit 0` or always-true |
| CA203 | require-restart-policy | warning | yes | No restart policy set |
| CA204 | require-resource-limits | warning | no | Missing `deploy.resources.limits` (memory/CPU) |
| CA205 | require-log-rotation | info | yes | No logging driver/max-size configured |

### CA3xx — Networking (3 rules)

| ID | Name | Severity | Fix? | Description |
|----|------|----------|------|-------------|
| CA301 | port-conflict | error | no | Same host port used by multiple services (CROSS-FILE) |
| CA302 | no-host-network | warning | no | Service uses `network_mode: host` |
| CA303 | no-default-network | info | no | Service uses default bridge network (no explicit network) |

### CA4xx — Consistency (3 rules)

| ID | Name | Severity | Fix? | Description |
|----|------|----------|------|-------------|
| CA401 | puid-pgid-mismatch | error | no | PUID/PGID values differ across services (CROSS-FILE) |
| CA402 | umask-inconsistent | warning | no | UMASK values differ across *arr services |
| CA403 | missing-timezone | warning | yes | TZ environment variable not set |

### CA6xx — Arr Stack (1 rule in MVP, more later)

| ID | Name | Severity | Fix? | Description |
|----|------|----------|------|-------------|
| CA601 | hardlink-path-mismatch | warning | no | *arr containers don't share a common /data root mount (TRaSH) |

---

## CLI Commands

```bash
# Core
composearr audit [PATH]                    # Lint all compose files (default: current dir)
composearr audit --fix [PATH]              # Apply auto-fixes
composearr audit --diff [PATH]             # Show what --fix would change (don't apply)
composearr audit --format json             # Machine-readable output
composearr audit --format github           # GitHub Actions annotations
composearr audit --severity error          # Only show errors
composearr audit --rule CA101,CA301        # Only run specific rules
composearr audit --ignore CA002,CA303      # Skip specific rules
composearr audit --service sonarr,radarr   # Only check specific services
composearr audit --strict                  # Warnings become errors (for CI)

# Utilities
composearr init                            # Interactive config setup
composearr ports [PATH]                    # Port allocation table across all files
composearr secrets [PATH]                  # Find all secrets/credentials in stack
composearr rules                           # List all available rules with descriptions

# Future (v2+)
composearr consolidate [PATH]              # Move inline secrets to central .env
composearr template apply [PATH]           # Apply hygiene template to services
composearr doctor [PATH]                   # Compare running stack vs compose definitions
```

---

## Terminal Output Design

### Default Audit Output (Ruff-inspired with code context)

```
composearr v0.1.0

── gluetun/compose.yaml ────────────────────────────

  gluetun:
    environment:
      - WIREGUARD_PRIVATE_KEY=bijL6fc...icRI=
        ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
        ✖ CA101 (error): Secret value hardcoded in environment block
        Move to .env file and reference as ${WIREGUARD_PRIVATE_KEY}

    image: qmcgaw/gluetun:v3
           (no issues)

── plex/compose.yaml ───────────────────────────────

  plex:
    image: lscr.io/linuxserver/plex:latest
           ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
        ⚠ CA001 (warning): Image uses :latest tag
        Pin to specific version for reproducibility

── qbittorrent/compose.yaml ────────────────────────

  qbittorrent:
    healthcheck:
      test: exit 0
            ~~~~~~
        ⚠ CA202 (warning): Healthcheck always passes (exit 0)
        Use: curl -sf http://localhost:8080/api/v2/app/version || exit 1

── Cross-file checks ──────────────────────────────

  ✖ CA401: PUID mismatch across stack
    PUID=1000 in sonarr, radarr, bazarr, prowlarr
    PUID=568  in qbittorrent, sabnzbd
    PUID=0    in huntarr, decypharr, gluetun
    All media stack services should use the same PUID

── Summary ─────────────────────────────────────────
Files scanned:   35 compose files (42 services)
Issues found:    8 errors, 12 warnings, 5 info

  ✖ 8 errors    — must fix
  ⚠ 12 warnings — recommended
  ℹ 5 info      — optional

  6 issues auto-fixable with composearr audit --fix
```

### Ports Command Output

```
composearr ports

Port Allocation Map — C:\DockerContainers
═════════════════════════════════════════

  PORT   PROTO  SERVICE          FILE                      BINDING
  ─────  ─────  ───────────────  ────────────────────────  ───────────
  2375   tcp    socketproxy      socketproxy/compose.yaml  0.0.0.0 ⚠
  3000   tcp    subsyncarrplus   subsyncarrplus/compose.yaml  0.0.0.0
  3001   tcp    meshmonitor      meshmonitor/compose.yaml  0.0.0.0
  5341   tcp    seq              seq/compose.yaml          0.0.0.0
  7878   tcp    radarr           radarr/compose.yaml       0.0.0.0
  8000   tcp    komodo-core      komodo/compose.yaml       0.0.0.0
  8080   tcp    glances          glances/compose.yaml      0.0.0.0
  8085   tcp    termix           termix/compose.yaml       0.0.0.0
  8095   tcp    qbittorrent      qbittorent/compose.yaml   0.0.0.0
  8787   tcp    bazarr           bazarr/compose.yaml       0.0.0.0
  8888   tcp    gluetun          gluetun/compose.yaml      0.0.0.0
  8889   tcp    signal-api       signal-api/compose.yaml   0.0.0.0
  8989   tcp    sonarr           sonarr/compose.yaml       0.0.0.0
  9696   tcp    prowlarr         prowlarr/compose.yaml     0.0.0.0
  30055  tcp    sabnzbd          sabnzbd/compose.yaml      0.0.0.0
  32400  tcp    plex             plex/compose.yaml         0.0.0.0

  ⚠ 2375 (socketproxy): Docker API exposed on all interfaces — bind to 127.0.0.1
  ✔ No port conflicts detected

  16 host ports in use across 35 compose files
```

### Init Flow

```
$ composearr init

  Scanning directory...
  Found 35 compose files, 42 services

  ? Select a profile:
    ❯ arrstack    — Media server rules (Sonarr, Radarr, TRaSH compliance)
      homelab     — General self-hosted rules
      production  — Strict production-readiness
      security    — Security-focused only
      minimal     — Just the essentials

  ? Strictness:
    ❯ recommended — Errors for critical, warnings for best practices
      strict      — Most rules as errors (CI mode)
      relaxed     — Mostly warnings

  ✔ Created .composearr.yml

  Quick start:
    composearr audit              # Run audit
    composearr audit --fix        # Auto-fix issues
    composearr audit --diff       # Preview fixes
    composearr ports              # View port map
```

---

## Exit Codes

| Code | Meaning | CI Behavior |
|------|---------|-------------|
| 0 | Clean (no errors, warnings OK) | Pass |
| 1 | Errors found | Fail |
| 2 | Tool error (bad config, parse failure, crash) | Fail |

`--strict` flag promotes warnings to errors (exit 1 if any warnings).
`--max-warnings N` fails if warning count exceeds N.

---

## Config File (.composearr.yml)

```yaml
# .composearr.yml
profile: arrstack                    # Built-in profile (overridden by rules below)

severity: warning                    # Minimum severity to report

rules:
  CA001: error                       # Promote no-latest-tag to error
  CA002: off                         # Disable no-digest-pin
  CA105: warning                     # Unbound ports as warning
  CA205: info                        # Log rotation as info

ignore:
  files:
    - "komodo/periphery/**"          # Skip Komodo agent repos
    - "*.dev.yaml"                   # Skip dev overrides
  services:
    watchtower:
      - CA001                        # Watchtower should use :latest

trusted_registries:
  - docker.io
  - ghcr.io
  - lscr.io
  - gcr.io

env_file: .env                       # Central .env for secret consolidation checks
```

---

## Secret Detection (Hybrid Approach)

### Layer 1: Pattern Matching (fast, low false-positive)

Known secret formats with specific regexes:
- WireGuard private keys (Base64, 44 chars)
- SSH keys (ssh-rsa/ssh-ed25519 AAAA...)
- AWS keys (AKIA..., 40-char base64)
- GitHub tokens (ghp_/gho_/ghu_/ghs_/ghr_ + 36 chars)
- Plex tokens
- Generic PASSWORD/SECRET/KEY variable names with non-placeholder values

### Layer 2: Entropy Analysis (catches unknown formats)

For any env var with `key`, `secret`, `token`, `password`, `credential` in the name:
- Compute Shannon entropy of the value
- Hex strings > 3.0 bits/char flagged
- Base64 strings > 4.5 bits/char flagged

### Layer 3: Placeholder Exclusion

Skip values matching: `changeme`, `password`, `example`, `<...>`, `${...}`, `TODO`, `xxx+`, repeated chars

### Layer 4: Duplication Detection

Flag when the same secret appears in both .env AND inline in a compose file (your gluetun case).

---

## YAML Round-Trip: Why ruamel.yaml Is Non-Negotiable

PyYAML destroys on round-trip:
- All comments (inline, block, end-of-line)
- Key ordering
- Blank lines between sections
- Flow vs block style choices
- String quoting style

ruamel.yaml preserves ALL of these. This means when ComposeArr runs `--fix` and adds
`restart: unless-stopped` to a service, the rest of the file stays exactly as the user
wrote it. This is the difference between a tool users trust and one they abandon.

```python
from ruamel.yaml import YAML

yaml = YAML()
yaml.preserve_quotes = True

# Load, modify, save — comments and formatting intact
doc = yaml.load(Path("compose.yaml"))
doc['services']['plex']['restart'] = 'unless-stopped'
yaml.dump(doc, Path("compose.yaml"))
```

---

## Cross-File Port Conflict Detection (Implementation)

This is the #1 feature that no existing tool provides:

```python
# Collect all port mappings from all compose files
all_ports: list[PortMapping] = []
for project in discover_projects(root_path):
    doc = yaml.load(project.compose_file)
    for svc_name, svc_config in doc.get('services', {}).items():
        for port_spec in svc_config.get('ports', []):
            all_ports.extend(parse_port_mapping(
                port_spec, str(project.compose_file), svc_name
            ))

# Check every pair for overlap
conflicts = detect_port_conflicts(all_ports)
```

Port parser handles all compose-spec formats:
- Short: `"8080:80"`, `"8080:80/udp"`, `"127.0.0.1:8080:80"`, `"8080-8090:80-90"`
- Long: `{target: 80, published: 8080, protocol: tcp, host_ip: 0.0.0.0}`

---

## Profiles (Built-In Presets)

### arrstack
Optimized for *arr media server stacks. Enables all rules plus:
- CA601 hardlink path compliance (TRaSH Guides)
- CA401 PUID/PGID consistency enforced as error
- CA402 UMASK consistency check
- Trusted registries: lscr.io, ghcr.io (linuxserver, hotio)
- Learn More links point to TRaSH Guides

### homelab
General self-hosted rules. All CA rules at default severity. No *arr-specific checks.

### production
Strict. Most rules promoted to error:
- CA001 (no :latest) = error
- CA105 (unbound ports) = error
- CA204 (resource limits) = error
- CA201 (healthcheck) = error
- CA205 (log rotation) = error

### security
Only security rules enabled (CA1xx). Everything else off.

### minimal
Only critical rules: CA101 (inline secrets), CA301 (port conflicts), CA401 (PUID/PGID mismatch).

---

## Output Formats

| Format | Flag | Use Case | Priority |
|--------|------|----------|----------|
| Rich terminal | default | Human reading | MVP |
| JSON | `--format json` | Scripting, piping to jq | MVP |
| GitHub Actions | `--format github` | CI annotations on PR diffs | MVP |
| Compact | `--format compact` | grep-friendly, one-line-per-issue | v1.1 |
| SARIF | `--format sarif` | GitHub Advanced Security | v1.2 |
| HTML | `--format html` | Shareable reports | v2 |

### JSON Output Structure

```json
{
  "version": "0.1.0",
  "timestamp": "2026-02-13T10:30:00Z",
  "profile": "arrstack",
  "files": [
    {
      "path": "gluetun/compose.yaml",
      "services": ["gluetun"],
      "issues": [
        {
          "rule": "CA101",
          "name": "no-inline-secrets",
          "severity": "error",
          "category": "security",
          "message": "WIREGUARD_PRIVATE_KEY contains secret value inline",
          "line": 18,
          "service": "gluetun",
          "fixable": true,
          "suggested_fix": "Move to .env and reference as ${WIREGUARD_PRIVATE_KEY}"
        }
      ]
    }
  ],
  "cross_file_issues": [
    {
      "rule": "CA401",
      "name": "puid-pgid-mismatch",
      "severity": "error",
      "message": "PUID values differ: 1000 (sonarr, radarr), 568 (qbittorrent, sabnzbd)",
      "affected_files": ["sonarr/compose.yaml", "qbittorrent/compose.yaml"],
      "fixable": false
    }
  ],
  "summary": {
    "files_scanned": 35,
    "services_scanned": 42,
    "errors": 8,
    "warnings": 12,
    "info": 5,
    "fixable": 6
  }
}
```

---

## MVP Scope (v0.1.0)

### What ships in v0.1.0

1. `composearr audit [PATH]` — scan directory, output results
2. `composearr audit --fix` — auto-fix simple issues
3. `composearr audit --diff` — preview fixes without applying
4. `composearr init` — interactive config setup with profile selection
5. `composearr ports` — port allocation table
6. `composearr rules` — list all rules
7. 20 rules (listed above)
8. 3 output formats: console (Rich), JSON, GitHub Actions
9. `.composearr.yml` config file support
10. 5 built-in profiles

### What does NOT ship in v0.1.0

- Web UI
- SARIF output
- HTML reports
- Image vulnerability checking (trivy integration)
- Secret rotation
- Config drift detection
- `composearr doctor` (running vs defined)
- `composearr consolidate` (automated secret migration)
- Plugin/extension system for custom rules

---

## Development Phases

### Phase 1: Foundation (Sprint 1)
- Project skeleton with Typer CLI
- Scanner: directory discovery, ruamel.yaml parsing, .env resolution
- Rule engine: BaseRule, registry, per-file + cross-file passes
- Console formatter (Rich)
- 5 core rules: CA001, CA101, CA201, CA203, CA301

### Phase 2: Rule Coverage (Sprint 2)
- Remaining 15 rules
- Secret detection (patterns + entropy)
- Port conflict detection (cross-file)
- PUID/PGID consistency check
- JSON + GitHub Actions formatters

### Phase 3: Fix Mode (Sprint 3)
- `--fix` implementation with ruamel.yaml round-trip
- `--diff` preview with Rich syntax highlighting
- Fixers for: inline secrets, :latest tag, restart policy, log rotation, TZ
- Interactive fix confirmation (`--fix --interactive`)

### Phase 4: Polish (Sprint 4)
- `composearr init` with InquirerPy
- `composearr ports` table
- Profiles system
- `.composearr.yml` config loading
- PyPI packaging
- README, docs, examples

---

## Competitive Positioning

```
                    Single-File        Cross-File       Auto-Fix
                    Analysis           Analysis         Mode
                    ─────────          ─────────        ────────
yamllint            YAML only          No               No
docker compose cfg  Schema only        No               No
dclint              Basic lint         No               No
KICS                Security           No               No
Checkov             Security           No               No

ComposeArr          Full hygiene       YES              YES
```

ComposeArr is the only tool that:
1. Understands compose semantics (not just YAML structure)
2. Analyzes across multiple compose files
3. Knows homelab conventions (LSIO, Hotio, TRaSH)
4. Can auto-fix issues while preserving file formatting
5. Has domain-specific profiles (arrstack, homelab, production)

---

## Target Users

### Primary: Homelab enthusiasts (free)
- Running 5-50+ Docker containers
- Using *arr stack, Plex, reverse proxies
- Per-service compose files or monolithic stacks
- Pain: "my compose files are a mess, I know there are problems but I don't know what"

### Secondary: DevOps teams (future paid tier)
- Managing compose-based deployments
- Need CI/CD integration (SARIF, GitHub Actions)
- Need audit trails and compliance reports
- Pain: "we have no guardrails on our compose configurations"

---

## Bottom Line

The gap is real, the community wants it, and the technical path is clear.
20 rules, CLI-first, cross-file intelligence, comment-preserving fixes.
Ship the MVP, get it on r/selfhosted, iterate.
