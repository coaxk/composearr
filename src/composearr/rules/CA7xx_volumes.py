"""CA7xx — Volume best practices rules."""

from __future__ import annotations

from typing import TYPE_CHECKING

from composearr.models import LintIssue, Scope, Severity
from composearr.rules.base import BaseRule
from composearr.scanner.parser import find_service_line

if TYPE_CHECKING:
    from composearr.models import ComposeFile


# Bind mount sources that should NOT be flagged by CA701
_BIND_MOUNT_EXCEPTIONS = frozenset({
    "/var/run/docker.sock",
    "/dev/",
    "/sys/",
    "/proc/",
    "/etc/localtime",
    "/etc/timezone",
})


def _parse_volume_entry(vol) -> tuple[str, str, str]:
    """Parse a volume entry into (source, target, mode).

    Handles both string and long-form dict syntax.
    Returns ("", "", "") if unparseable.
    """
    if isinstance(vol, str):
        parts = vol.split(":")
        if len(parts) == 1:
            # Named volume with no target specified, or just a target
            return ("", parts[0], "")
        elif len(parts) == 2:
            return (parts[0], parts[1], "")
        elif len(parts) >= 3:
            return (parts[0], parts[1], parts[2])
    elif isinstance(vol, dict):
        source = str(vol.get("source", ""))
        target = str(vol.get("target", ""))
        mode = str(vol.get("read_only", ""))
        return (source, target, "ro" if mode == "True" else "")

    return ("", "", "")


def _is_bind_mount(source: str) -> bool:
    """Check if a volume source is a bind mount (host path)."""
    return source.startswith("/") or source.startswith("./") or source.startswith("../")


def _is_exception_mount(source: str) -> bool:
    """Check if a bind mount is an exception (system mount, docker socket, etc.)."""
    for exc in _BIND_MOUNT_EXCEPTIONS:
        if source == exc or source.startswith(exc):
            return True
    return False


class PreferNamedVolumes(BaseRule):
    """Suggest named volumes over bind mounts for portability."""

    id = "CA701"
    name = "prefer-named-volumes"
    severity = Severity.INFO
    scope = Scope.SERVICE
    description = "Bind mount could be a named volume for better portability"
    category = "volumes"

    def check_service(
        self,
        service_name: str,
        service_config: dict,
        compose_file: ComposeFile,
    ) -> list[LintIssue]:
        issues: list[LintIssue] = []
        volumes = service_config.get("volumes", [])

        for vol in volumes:
            source, target, _ = _parse_volume_entry(vol)

            if not source or not target:
                continue

            if not _is_bind_mount(source):
                continue

            if _is_exception_mount(source):
                continue

            # Data-like targets that are good candidates for named volumes
            vol_str = str(vol) if isinstance(vol, str) else f"{source}:{target}"
            line = find_service_line(compose_file.raw_content, service_name)

            issues.append(self._make_issue(
                message=f"Bind mount '{source}' could be a named volume",
                file_path=str(compose_file.path),
                line=line,
                service=service_name,
                suggested_fix=(
                    f"Consider: {service_name}_data:{target} "
                    f"(with a top-level volumes: entry)"
                ),
                learn_more="Named volumes are more portable and easier to back up",
            ))

        return issues


class UndefinedVolumeRef(BaseRule):
    """Flag services that reference volumes not defined in the volumes section."""

    id = "CA702"
    name = "undefined-volume-ref"
    severity = Severity.ERROR
    scope = Scope.FILE
    description = "Service references a volume not defined in the volumes section"
    category = "volumes"

    def check_service(
        self,
        service_name: str,
        service_config: dict,
        compose_file: ComposeFile,
    ) -> list[LintIssue]:
        # FILE scope — handled in check_file
        return []

    def check_file(self, compose_file: ComposeFile) -> list[LintIssue]:
        issues: list[LintIssue] = []

        data = compose_file.data
        if not data or not isinstance(data, dict):
            return []

        # Get defined top-level volumes (may be None or empty)
        defined_volumes_raw = data.get("volumes")
        if defined_volumes_raw is None:
            defined_volumes: set[str] = set()
        elif isinstance(defined_volumes_raw, dict):
            defined_volumes = set(str(k) for k in defined_volumes_raw.keys())
        else:
            defined_volumes = set()

        services = compose_file.services
        for svc_name, svc_config in services.items():
            if not isinstance(svc_config, dict):
                continue

            volumes = svc_config.get("volumes", [])
            for vol in volumes:
                source, target, _ = _parse_volume_entry(vol)

                if not source:
                    continue

                # Skip bind mounts (they don't need a volumes: definition)
                if _is_bind_mount(source):
                    continue

                # This is a named volume reference — check if defined
                if source not in defined_volumes:
                    line = find_service_line(compose_file.raw_content, svc_name)
                    issues.append(self._make_issue(
                        message=f"Volume '{source}' referenced but not defined in volumes section",
                        file_path=str(compose_file.path),
                        line=line,
                        service=svc_name,
                        fix_available=True,
                        suggested_fix=f"Add '{source}:' to the top-level volumes section",
                    ))

        return issues
