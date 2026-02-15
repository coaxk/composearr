"""CA1xx — Security rules."""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

from composearr.analyzers.entropy import is_likely_secret
from composearr.models import LintIssue, Scope, Severity
from composearr.rules.base import BaseRule
from composearr.scanner.parser import find_line_number

if TYPE_CHECKING:
    from composearr.models import ComposeFile

# Variable names that commonly hold secrets
_SECRET_KEY_PATTERNS = re.compile(
    r"(password|secret|token|private.?key|api.?key|credential)"
    r"(?!.*file)",  # Exclude _FILE suffix (Docker secrets pattern)
    re.IGNORECASE,
)

# Values that are clearly not secrets (booleans, short numbers, common config)
_SAFE_VALUE_PATTERNS = re.compile(
    r"^("
    r"true|false|yes|no|on|off|"
    r"[0-9]{1,5}|"  # Short numbers (ports, UIDs, etc.)
    r"none|null|auto|enabled?|disabled?|"
    r"localhost|0\.0\.0\.0|127\.0\.0\.1|"
    r"[a-z]{1,15}"  # Very short lowercase words
    r")$",
    re.IGNORECASE,
)

# Known secret format patterns (high confidence)
_SECRET_VALUE_PATTERNS = [
    # WireGuard private keys (base64, 44 chars ending in =)
    re.compile(r"^[A-Za-z0-9+/]{42,44}={0,2}$"),
    # GitHub tokens
    re.compile(r"^gh[pousr]_[A-Za-z0-9]{36,}$"),
    # AWS access keys
    re.compile(r"^AKIA[0-9A-Z]{16}$"),
    # Generic long hex strings (API keys)
    re.compile(r"^[a-fA-F0-9]{32,}$"),
]

# Values that are clearly placeholders, not real secrets
_PLACEHOLDER_PATTERNS = re.compile(
    r"^("
    r"changeme|password|example|placeholder|"
    r"<.*>|\$\{.*\}|TODO|xxx+|CHANGE.?ME|"
    r"your.*(here|key|token|password)|"
    r"test|default|dummy"
    r")$",
    re.IGNORECASE,
)


def _is_variable_reference(value: str) -> bool:
    """Check if value is a variable reference like ${VAR} or $VAR."""
    return value.startswith("${") or (value.startswith("$") and not value.startswith("$$"))


def _looks_like_secret_value(value: str) -> bool:
    """Check if a value looks like it contains an actual secret."""
    if not value or len(value) < 8:
        return False

    if _is_variable_reference(value):
        return False

    if _PLACEHOLDER_PATTERNS.match(value):
        return False

    for pattern in _SECRET_VALUE_PATTERNS:
        if pattern.match(value):
            return True

    return False


def _parse_env_entry(entry: str) -> tuple[str, str] | None:
    """Parse 'KEY=VALUE' into (key, value), or None if no =."""
    if "=" not in entry:
        return None
    key, _, value = entry.partition("=")
    return key.strip(), value.strip()


class NoInlineSecrets(BaseRule):
    id = "CA101"
    name = "no-inline-secrets"
    severity = Severity.ERROR
    scope = Scope.SERVICE
    description = "Secret value hardcoded in environment block"
    category = "security"

    def check_service(
        self,
        service_name: str,
        service_config: dict,
        compose_file: ComposeFile,
    ) -> list[LintIssue]:
        issues: list[LintIssue] = []
        env = service_config.get("environment")
        if not env:
            return issues

        entries: list[tuple[str, str]] = []

        if isinstance(env, list):
            for item in env:
                parsed = _parse_env_entry(str(item))
                if parsed:
                    entries.append(parsed)
        elif isinstance(env, dict):
            for key, value in env.items():
                entries.append((str(key), str(value) if value is not None else ""))

        for key, value in entries:
            if _is_variable_reference(value):
                continue

            is_secret_name = bool(_SECRET_KEY_PATTERNS.search(key))
            is_secret_value = _looks_like_secret_value(value)

            if is_secret_name and value and not _PLACEHOLDER_PATTERNS.match(value) and not _SAFE_VALUE_PATTERNS.match(value) and len(value) >= 8:
                # Secret-named variable with a non-placeholder, non-trivial value
                line = find_line_number(compose_file.raw_content, key, value[:20] if len(value) > 20 else value)
                issues.append(
                    self._make_issue(
                        f"{key} contains secret value inline",
                        str(compose_file.path),
                        line=line,
                        service=service_name,
                        fix_available=True,
                        suggested_fix=f"Move to .env and reference as ${{{key}}}",
                    )
                )
            elif is_secret_value and not is_secret_name:
                # Value looks like a secret even though the name doesn't suggest it
                line = find_line_number(compose_file.raw_content, key)
                issues.append(
                    self._make_issue(
                        f"{key} appears to contain a secret value",
                        str(compose_file.path),
                        line=line,
                        service=service_name,
                        fix_available=True,
                        suggested_fix=f"Move to .env and reference as ${{{key}}}",
                    )
                )
            elif not is_secret_name and not is_secret_value:
                # Entropy-based detection: catch secrets that pattern matching misses
                high_entropy, score = is_likely_secret(value)
                if high_entropy:
                    line = find_line_number(compose_file.raw_content, key)
                    issues.append(
                        self._make_issue(
                            f"{key} has high-entropy value (potential secret)",
                            str(compose_file.path),
                            line=line,
                            service=service_name,
                            suggested_fix=f"If this is a secret, move to .env and reference as ${{{key}}}",
                        )
                    )

        return issues
