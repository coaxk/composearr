# ComposeArr

**Grammarly for Docker Compose**

Catch configuration mistakes before they cause 3am incidents.

[![Tests](https://github.com/composearr/composearr/actions/workflows/ci.yml/badge.svg)](https://github.com/composearr/composearr/actions)
[![GitHub Action](https://img.shields.io/badge/GitHub-Action-blue)](https://github.com/composearr/composearr)
[![Pre-commit](https://img.shields.io/badge/pre--commit-enabled-brightgreen)](https://github.com/pre-commit/pre-commit)
[![Python](https://img.shields.io/badge/python-%3E%3D3.11-blue)](https://www.python.org/)
[![License](https://img.shields.io/badge/license-MIT-green)](LICENSE)

---

## Features

- **30 rules** across 9 categories
- **Auto-fix** with interactive preview
- **CI/CD Ready** - GitHub Action + pre-commit hook
- **Stack Health Score** - Track your progress
- **Rule Profiles** - Strict, balanced, or relaxed
- **Fast** - Parallel execution, parse caching
- **Beautiful TUI** - Interactive terminal interface
- **Educational** - Learn Docker best practices
- **20 app templates** - Generate best-practice compose files
- **.composearrignore** - Gitignore-style file exclusions

## Quick Start

### CLI

```bash
pip install composearr
composearr audit
```

### GitHub Actions

```yaml
- uses: composearr/composearr@v1
```

### Pre-commit

```yaml
repos:
  - repo: https://github.com/composearr/composearr
    rev: v0.1.0
    hooks:
      - id: composearr-lint
```

---

## GitHub Actions Integration

ComposeArr provides an official GitHub Action for CI/CD pipelines.

### Basic Usage

```yaml
- name: Lint compose files
  uses: composearr/composearr@v1
  with:
    path: '.'
    severity: 'warning'
    fail-on: 'error'
```

### Full Example

```yaml
name: Lint Compose Files

on:
  pull_request:
    paths:
      - '**.yaml'
      - '**.yml'

jobs:
  lint:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Run ComposeArr
        uses: composearr/composearr@v1
        with:
          path: '.'
          recursive: true
          profile: 'balanced'
          fail-on: 'error'
```

### Inputs

| Input | Description | Default |
|-------|-------------|---------|
| `path` | Path to compose files | `.` |
| `severity` | Minimum severity (`error`, `warning`, `info`) | `warning` |
| `fail-on` | Fail build on (`error`, `warning`, `info`, `never`) | `error` |
| `recursive` | Scan subdirectories | `false` |
| `profile` | Rule profile (`strict`, `balanced`, `relaxed`) | `balanced` |
| `format` | Output format | `github` |

### Outputs

| Output | Description |
|--------|-------------|
| `issues-found` | Total issues |
| `errors` | Error count |
| `warnings` | Warning count |
| `score` | Health score (0-100) |
| `grade` | Letter grade (A+ to F) |

See [.github/workflows/composearr-example.yml](.github/workflows/composearr-example.yml) for complete examples.

---

## Pre-commit Hook

Prevent bad compose files from being committed.

### Quick Start

```bash
# Install pre-commit
pip install pre-commit

# Add to your repo
cat > .pre-commit-config.yaml << EOF
repos:
  - repo: https://github.com/composearr/composearr
    rev: v0.1.0
    hooks:
      - id: composearr-lint
EOF

# Install the hook
pre-commit install

# Now composearr runs before every commit!
```

### Profiles

Choose your strictness level:

```yaml
hooks:
  # Errors only (default)
  - id: composearr-lint

  # Production standards (strict)
  - id: composearr-lint-strict

  # Custom configuration
  - id: composearr-lint
    args: ['--severity', 'warning', '--profile', 'relaxed']
```

### Skip Hook (when needed)

```bash
# Skip for a single commit
git commit --no-verify

# Skip for specific files
SKIP=composearr-lint git commit
```

See [.pre-commit-config.yaml.example](.pre-commit-config.yaml.example) for full configuration.

---

## 30 Lint Rules

ComposeArr ships with 30 rules across 9 categories, each with actionable fix suggestions:

| Category | Rules | Examples |
|----------|-------|---------|
| Images (CA0xx) | 2 | Unpinned tags, untrusted registries |
| Security (CA1xx) | 1 | Inline secrets |
| Reliability (CA2xx) | 3 | Healthchecks, restart policies |
| Networking (CA3xx) | 4 | Port conflicts, unreachable deps |
| Consistency (CA4xx) | 4 | PUID/PGID, timezone, env vars |
| Resources (CA5xx) | 5 | Memory/CPU limits, logging |
| Arr Stack (CA6xx) | 1 | Hardlink path alignment |
| Volumes (CA7xx) | 2 | Named volumes, undefined refs |
| Security (CA8xx) | 4 | Capabilities, privileged mode |
| Advanced (CA9xx) | 4 | Resource requests, tmpfs, namespaces |

```bash
composearr rules              # List all rules
composearr explain CA001      # Detailed rule documentation
```

---

## Commands

| Command | Description |
|---------|-------------|
| `composearr` | Launch interactive TUI |
| `composearr audit [PATH]` | Scan compose files for issues |
| `composearr fix [PATH]` | Apply auto-fixes to compose files |
| `composearr ports [PATH]` | Show port allocation table |
| `composearr topology [PATH]` | Show network topology |
| `composearr freshness [PATH]` | Check for newer image versions |
| `composearr runtime [PATH]` | Compare compose vs running containers |
| `composearr history [PATH]` | View audit history and score trends |
| `composearr watch [PATH]` | Monitor files and re-audit on changes |
| `composearr init [TEMPLATE]` | Generate compose from template |
| `composearr rules` | List all available rules |
| `composearr explain <RULE>` | Show detailed rule documentation |
| `composearr config [PATH]` | Validate and show configuration |
| `composearr batch [PATH]` | Batch operations for CI/CD |
| `composearr help [COMMAND]` | Show command reference |

### Audit Options

```
--severity, -s      Minimum severity: error, warning, info
--rule, -r          Only run specific rules (comma-separated)
--ignore, -i        Skip specific rules (comma-separated)
--group-by, -g      Group issues by: rule, file, severity
--format, -f        Output format: console, json, sarif, github
--output, -o        Output file path
--verbose           Show full file context
--no-network        Disable network features
--no-suppression    Ignore inline suppression comments
--recursive, -R     Scan subdirectories recursively
--max-depth         Maximum directory depth for recursive scan
--profile, -P       Rule profile: strict, balanced, relaxed
--explain, -e       Show detailed explanations for triggered rules
```

---

## Configuration

ComposeArr loads configuration from a hierarchy: **defaults -> user -> project**.

- User config: `~/.composearr.yml`
- Project config: `.composearr.yml` or `.composearr.yaml` in the scanned directory

### Example `.composearr.yml`

```yaml
# Rule profile (strict, balanced, relaxed)
profile: balanced

# Scan settings
scan:
  recursive: true
  max_depth: 5

# Override rule severities (error, warning, info, off)
rules:
  CA001: error
  CA403: off
  no-inline-secrets: error

# Ignore files or services
ignore:
  files:
    - "**/test-*"
    - "staging/**"
  services:
    - debug-helper
    - dev-tools
```

### .composearrignore

Exclude files from scanning with gitignore-style patterns:

```
# .composearrignore
backup/
*.bak
**/test-*.yaml
!important-test.yaml
```

### Inline Suppression

Suppress rules directly in your compose files with comments:

```yaml
# composearr-ignore-file           # Ignore the entire file

services:
  myapp:
    # composearr-ignore: CA001     # Suppress specific rule on next line
    image: myapp:latest

    # composearr: ignore CA201     # Alternate format
    # No healthcheck needed for this dev service
```

---

## Templates

Generate best-practice compose files for 20 popular apps:

```bash
composearr init --list            # List all templates
composearr init sonarr            # Generate Sonarr compose
composearr init nginx -o ~/docker/nginx
```

Available: Sonarr, Radarr, Prowlarr, qBittorrent, SABnzbd, Plex, Nginx, Postgres, Redis, Traefik, Jellyfin, Heimdall, Portainer, Uptime Kuma, Vaultwarden, Nextcloud, PhotoPrism, Calibre-Web, FreshRSS, Watchtower.

---

## Cross-File Intelligence

Unlike single-file linters, ComposeArr scans your **entire stack directory** and detects issues that span multiple compose files:

- **Port conflicts** (CA301) -- two services in different files binding the same host port
- **Unreachable dependencies** (CA302) -- service depends_on another it can't reach via network
- **PUID/PGID mismatches** (CA401) -- inconsistent user IDs across your *arr services
- **UMASK drift** (CA402) -- mismatched UMASK values breaking hardlinks
- **Hardlink path issues** (CA601) -- *arr services without a unified `/data` mount

---

## Output Example

```
  ◆ composearr  v0.1.0

  Scanned 12 files, 28 services in 0.34s

  ● 3 errors    ● 8 warnings    ● 2 info
  4 auto-fixable → composearr fix

  ━━ CA301 port-conflict (1 issue)

    ● CA301  Port 8080/tcp used by multiple services: traefik, nginx

  ━━ CA101 no-inline-secrets (2 issues)

    ● CA101  DB_PASSWORD contains secret value inline  sonarr
      → Move to .env and reference as ${DB_PASSWORD}

  ━━ CA001 no-latest-tag (5 issues)

    ● CA001  Image uses :latest  sonarr
      → Pin to lscr.io/linuxserver/sonarr:4.0.14

  ✓ 7 files passed all checks
```

---

## Contributing

Contributions are welcome. The project uses [Hatch](https://hatch.pypa.io/) as its build system.

```bash
git clone https://github.com/composearr/composearr.git
cd composearr
pip install -e ".[dev]"
pytest
```

To add a new rule, subclass `BaseRule` in the appropriate `CA*xx_*.py` module under `src/composearr/rules/`. Rules are auto-registered via `__init_subclass__`.

---

## License

[MIT](LICENSE)
