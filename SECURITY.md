# Security Policy

## Supported Versions

| Version | Supported          |
|---------|--------------------|
| 0.1.x   | :white_check_mark: |

## Reporting a Vulnerability

**Please do not open public issues for security vulnerabilities.**

Instead, report vulnerabilities through [GitHub Security Advisories](https://github.com/coaxk/composearr/security/advisories/new). You will receive a response within 48 hours acknowledging the report, and we aim to provide a fix or mitigation plan within 7 days.

When reporting, please include:
- Description of the vulnerability
- Steps to reproduce
- Potential impact
- Suggested fix (if any)

## Security Measures in ComposeArr

ComposeArr processes user-provided Docker Compose files and applies the following safeguards:

- **Safe YAML loading**: All YAML parsing uses `ruamel.yaml` in safe mode — no arbitrary code execution through YAML deserialization
- **ReDoS prevention**: Regular expressions used in rule matching are bounded to prevent catastrophic backtracking
- **Input validation**: File paths and user inputs are validated before processing
- **No network access by default**: Core linting is entirely offline; network features (registry checks) are opt-in via the `[network]` extra
- **No shell execution**: ComposeArr never passes user input to shell commands
- **Pinned dependencies**: All dependencies use version ranges with upper bounds to prevent supply chain drift

## Dependency Security

- Dependabot is enabled for automated dependency updates
- All PRs run Bandit security linting against the source code
- CodeQL analysis runs on every push and weekly
