"""Base rule class and rule registry."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

from composearr.models import LintIssue, Scope, Severity

if TYPE_CHECKING:
    from composearr.models import ComposeFile

# Global rule registry — populated by __init_subclass__
_rule_registry: dict[str, type[BaseRule]] = {}


class BaseRule(ABC):
    """Abstract base class for all lint rules."""

    id: str
    name: str
    severity: Severity
    scope: Scope
    description: str
    category: str

    def __init_subclass__(cls, **kwargs: object) -> None:
        super().__init_subclass__(**kwargs)
        if hasattr(cls, "id") and cls.id:
            _rule_registry[cls.id] = cls

    @abstractmethod
    def check_service(
        self,
        service_name: str,
        service_config: dict,
        compose_file: ComposeFile,
    ) -> list[LintIssue]:
        """Check a single service. Override for SERVICE-scope rules."""
        ...

    def check_file(self, compose_file: ComposeFile) -> list[LintIssue]:
        """Check a whole file. Override for FILE-scope rules."""
        return []

    def check_project(self, compose_files: list[ComposeFile]) -> list[LintIssue]:
        """Check across all files. Override for PROJECT-scope rules."""
        return []

    def _make_issue(
        self,
        message: str,
        file_path: str,
        *,
        line: int | None = None,
        service: str | None = None,
        fix_available: bool = False,
        suggested_fix: str | None = None,
        learn_more: str | None = None,
    ) -> LintIssue:
        return LintIssue(
            rule_id=self.id,
            rule_name=self.name,
            severity=self.severity,
            message=message,
            file_path=file_path,
            line=line,
            service=service,
            fix_available=fix_available,
            suggested_fix=suggested_fix,
            learn_more=learn_more,
        )


def get_all_rules() -> list[BaseRule]:
    """Return instances of all registered rules."""
    return [cls() for cls in _rule_registry.values()]


def get_rule(rule_id: str) -> BaseRule | None:
    """Return an instance of a specific rule by ID."""
    cls = _rule_registry.get(rule_id)
    return cls() if cls else None
