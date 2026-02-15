# ComposeArr

**Docker Compose hygiene linter with cross-file intelligence.**

Catch port conflicts, leaked secrets, missing healthchecks, and *arr stack misconfigurations -- before they bite you at 3 AM.

[![Version](https://img.shields.io/badge/version-0.1.0-teal)](https://github.com/coaxk/composearr)
[![Python](https://img.shields.io/badge/python-%3E%3D3.11-blue)](https://www.python.org/)
[![License](https://img.shields.io/badge/license-MIT-green)](LICENSE)
[![Tests](https://img.shields.io/badge/tests-passing-brightgreen)](https://github.com/coaxk/composearr/actions)

---

## Quick Start

```bash
pip install composearr
```

**Run an audit** (CLI mode):

```bash
composearr audit
```

**Launch the interactive TUI** (no arguments):

```bash
composearr
```

ComposeArr auto-detects your Docker stack directory. Point it somewhere specific with:

```bash
composearr audit /path/to/stacks
```

---

## Features

### 13 Lint Rules

ComposeArr ships with 13 rules across 5 categories, each with actionable fix suggestions:

| ID | Name | Severity | Description |
|----|------|----------|-------------|
| CA001 | no-latest-tag | warning | Image uses `:latest` or has no tag |
| CA003 | untrusted-registry | info | Image pulled from non-default registry |
| CA101 | no-inline-secrets | error | Secret value hardcoded in environment block |
| CA201 | require-healthcheck | warning | Service has no healthcheck defined |
| CA202 | no-fake-healthcheck | warning | Healthcheck always passes (`exit 0`, `true`, etc.) |
| CA203 | require-restart-policy | warning | No restart policy set |
| CA301 | port-conflict | error | Same host port used by multiple services (cross-file) |
| CA302 | unreachable-dependency | error | Service depends_on a service it cannot reach via network |
| CA303 | isolated-service-ports | warning | Service with `network_mode: none` exposes unreachable ports |
| CA401 | puid-pgid-mismatch | error | PUID/PGID values differ across services (cross-file) |
| CA402 | umask-inconsistent | warning | UMASK values differ across *arr services |
| CA403 | missing-timezone | warning | TZ environment variable not set |
| CA601 | hardlink-path-mismatch | warning | Arr services don't share a common `/data` root mount (TRaSH Guides) |

### Interactive TUI

Run `composearr` with no arguments to launch a full interactive menu powered by [InquirerPy](https://github.com/kazhala/InquirerPy). Configure audit settings, browse rules, fix issues, and export reports -- all without memorizing CLI flags.

### Auto-Fix Engine

Many rules offer automatic fixes. Review proposed changes, then apply them in one step:

```bash
composearr fix                    # Interactive fix with backup files
composearr fix --dry-run          # Preview without modifying anything
composearr fix --no-backup        # Apply without creating .bak files
```

### Port Allocation Table

See every port mapping across your entire stack at a glance, with conflict highlighting:

```bash
composearr ports                  # Full table
composearr ports --conflicts      # Only show conflicting ports
composearr ports --format json    # Machine-readable output
```

### Explain Mode

Get detailed documentation for any rule, including why it matters, real-world failure scenarios, and fix examples:

```bash
composearr explain CA001
```

### Config Validation

Validate your `.composearr.yml` configuration and see the effective merged config:

```bash
composearr config                 # Show effective config
composearr config --validate      # Validate config files only
```

### Multiple Output Formats

- **Console** -- Rich terminal output with color-coded severity, grouping, and progress bars
- **JSON** -- Machine-readable audit results
- **SARIF** -- GitHub Advanced Security compatible format
- **GitHub** -- GitHub Actions annotation format (`::error`, `::warning`)

```bash
composearr audit --format json
composearr audit --format sarif --output report.sarif
composearr audit --format github
```

### Privacy-First Telemetry

Telemetry is **opt-in only**. When enabled, it collects only anonymous aggregate data (rule hit counts, scan duration, file counts). It never collects service names, image names, paths, secrets, or anything personally identifiable. You can review all pending events before they are sent.

### 63 Known Service Profiles

ComposeArr recognizes 63 Docker services out of the box -- including the entire *arr stack (Sonarr, Radarr, Prowlarr, etc.), download clients, databases, reverse proxies, and monitoring tools. Known services get smarter healthcheck suggestions, accurate port defaults, and resource recommendations.

---

## Commands

| Command | Description |
|---------|-------------|
| `composearr` | Launch interactive TUI |
| `composearr audit [PATH]` | Scan compose files for issues |
| `composearr fix [PATH]` | Apply auto-fixes to compose files |
| `composearr ports [PATH]` | Show port allocation table |
| `composearr topology [PATH]` | Show network topology and dependency reachability |
| `composearr rules` | List all available rules |
| `composearr explain <RULE>` | Show detailed rule documentation |
| `composearr config [PATH]` | Validate and show configuration |
| `composearr whale` | :) |

### Audit Options

```
--severity, -s    Minimum severity: error, warning, info (default: error)
--rule, -r        Only run specific rules (comma-separated, e.g. CA001,CA301)
--ignore, -i      Skip specific rules (comma-separated)
--group-by, -g    Group issues by: rule, file, severity (default: rule)
--format, -f      Output format: console, json, sarif, github (default: console)
--output, -o      Output file path
--verbose         Show full file context for each issue
--no-network      Disable network features (tag version lookups)
```

---

## Configuration

ComposeArr loads configuration from a hierarchy: **defaults -> user -> project**.

- User config: `~/.composearr.yml`
- Project config: `.composearr.yml` or `.composearr.yaml` in the scanned directory

### Example `.composearr.yml`

```yaml
# Override rule severities (error, warning, info, off)
rules:
  CA001: error          # Promote no-latest-tag to error
  CA403: off            # Disable missing-timezone check
  no-inline-secrets: error  # Rules accept both IDs and names

# Ignore files or services
ignore:
  files:
    - "**/test-*"
    - "staging/**"
  services:
    - debug-helper
    - dev-tools
```

### Inline Suppression

Suppress rules directly in your compose files with comments:

```yaml
# composearr-ignore-file           # Ignore the entire file

services:
  myapp:
    # composearr-ignore: CA001     # Suppress specific rule on next line
    image: myapp:latest
```

---

## Output Example

```
  ◆ composearr  v0.1.0

  Scanned 12 files, 28 services in 0.34s

  ● 3 errors    ● 8 warnings    ● 2 info
  4 auto-fixable → composearr audit --fix

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

## Cross-File Intelligence

Unlike single-file linters, ComposeArr scans your **entire stack directory** and detects issues that span multiple compose files:

- **Port conflicts** (CA301) -- two services in different files binding the same host port
- **Unreachable dependencies** (CA302) -- service depends_on another it can't reach via network
- **PUID/PGID mismatches** (CA401) -- inconsistent user IDs across your *arr services
- **UMASK drift** (CA402) -- mismatched UMASK values breaking hardlinks
- **Hardlink path issues** (CA601) -- *arr services without a unified `/data` mount

---

## Contributing

Contributions are welcome. The project uses [Hatch](https://hatch.pypa.io/) as its build system.

```bash
git clone https://github.com/coaxk/composearr.git
cd composearr
pip install -e ".[dev]"
pytest
```

To add a new rule, subclass `BaseRule` in the appropriate `CA*xx_*.py` module under `src/composearr/rules/`. Rules are auto-registered via `__init_subclass__`.

---

## License

[MIT](LICENSE)
