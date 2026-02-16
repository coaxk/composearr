"""CA2xx — Reliability rules."""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

from composearr.analyzers.healthcheck_helper import suggest_healthcheck_text
from composearr.models import LintIssue, Scope, Severity
from composearr.rules.base import BaseRule
from composearr.scanner.parser import find_line_number

if TYPE_CHECKING:
    from composearr.models import ComposeFile


class RequireHealthcheck(BaseRule):
    id = "CA201"
    name = "require-healthcheck"
    severity = Severity.WARNING
    scope = Scope.SERVICE
    description = "Service has no healthcheck defined"
    category = "reliability"

    def check_service(
        self,
        service_name: str,
        service_config: dict,
        compose_file: ComposeFile,
    ) -> list[LintIssue]:
        if "healthcheck" not in service_config:
            line = find_line_number(compose_file.raw_content, f"{service_name}:")
            image = service_config.get("image", "")
            ports = service_config.get("ports", [])

            suggestion = suggest_healthcheck_text(service_name, image, ports)
            if suggestion:
                fix = f"test: {suggestion}"
            else:
                fix = "Add a healthcheck to monitor service health"

            return [
                self._make_issue(
                    "No healthcheck defined",
                    str(compose_file.path),
                    line=line,
                    service=service_name,
                    suggested_fix=fix,
                )
            ]
        return []


class NoFakeHealthcheck(BaseRule):
    id = "CA202"
    name = "no-fake-healthcheck"
    severity = Severity.WARNING
    scope = Scope.SERVICE
    description = "Healthcheck always passes (exit 0, true, etc)"
    category = "reliability"

    _FAKE_PATTERNS = {"exit 0", "true", "echo", "sleep"}

    def check_service(
        self,
        service_name: str,
        service_config: dict,
        compose_file: ComposeFile,
    ) -> list[LintIssue]:
        hc = service_config.get("healthcheck")
        if not hc:
            return []

        test = hc.get("test")
        if not test:
            return []

        # Normalize test to a string
        if isinstance(test, list):
            # ["CMD-SHELL", "exit 0"] or ["CMD", "true"]
            test_str = " ".join(str(t) for t in test[1:]).strip().lower()
        else:
            test_str = str(test).strip().lower()

        for pattern in self._FAKE_PATTERNS:
            if test_str == pattern or test_str.startswith(f"{pattern} "):
                line = find_line_number(compose_file.raw_content, "test:")

                # Build a replacement suggestion based on service context
                image = service_config.get("image", "")
                ports = service_config.get("ports", [])
                replacement = suggest_healthcheck_text(service_name, image, ports)
                if replacement:
                    fix = f"Replace '{test_str}' with a real check:\n    test: {replacement}"
                else:
                    fix = f"Replace '{test_str}' with a real check (curl, wget, pgrep, or nc)"

                return [
                    self._make_issue(
                        f"Healthcheck uses '{test_str}' which always passes — it will never detect failures",
                        str(compose_file.path),
                        line=line,
                        service=service_name,
                        suggested_fix=fix,
                    )
                ]

        return []


class RequireRestartPolicy(BaseRule):
    id = "CA203"
    name = "require-restart-policy"
    severity = Severity.WARNING
    scope = Scope.SERVICE
    description = "No restart policy set"
    category = "reliability"

    def check_service(
        self,
        service_name: str,
        service_config: dict,
        compose_file: ComposeFile,
    ) -> list[LintIssue]:
        if "restart" not in service_config:
            line = find_line_number(compose_file.raw_content, f"{service_name}:")
            return [
                self._make_issue(
                    "Missing restart policy",
                    str(compose_file.path),
                    line=line,
                    service=service_name,
                    fix_available=True,
                    suggested_fix=(
                        f"Add to your '{service_name}' service definition:\n"
                        f"  {service_name}:\n"
                        f"    restart: unless-stopped"
                    ),
                )
            ]
        return []
