"""CA8xx — Security hardening rules."""

from __future__ import annotations

from typing import TYPE_CHECKING

from composearr.models import LintIssue, Scope, Severity
from composearr.rules.base import BaseRule
from composearr.scanner.parser import find_service_line

if TYPE_CHECKING:
    from composearr.models import ComposeFile


# ── Helpers ──────────────────────────────────────────────────────────

# Services that legitimately need elevated capabilities
_KNOWN_NEEDS_CAPS: dict[str, list[str]] = {
    "gluetun": ["NET_ADMIN"],
    "wireguard": ["NET_ADMIN", "SYS_MODULE"],
    "tailscale": ["NET_ADMIN", "NET_RAW"],
    "docker": ["SYS_ADMIN"],
    "dind": ["SYS_ADMIN"],
}

# Services known to legitimately need privileged mode
_PRIVILEGED_LEGITIMATE: dict[str, str] = {
    "docker": "Docker-in-Docker requires privileged mode",
    "dind": "Docker-in-Docker requires privileged mode",
    "kubernetes": "Kubernetes nodes may require privileged mode",
}

# Services that can safely run with read-only root filesystem
_READONLY_SAFE: dict[str, list[str]] = {
    "nginx": ["/var/cache/nginx", "/var/run"],
    "caddy": ["/data", "/config"],
    "traefik": ["/tmp"],
    "redis": ["/data"],
}

# Services that need a writable root filesystem
_NEEDS_WRITABLE: frozenset[str] = frozenset({
    "sonarr", "radarr", "lidarr", "readarr", "prowlarr",
    "bazarr", "whisparr",
    "plex", "jellyfin", "emby",
    "postgres", "mysql", "mariadb",
    "nextcloud",
    "sabnzbd", "qbittorrent", "transmission", "deluge",
})


def _detect_app(image: str, known_set: dict | frozenset | set) -> str:
    """Extract app name from an image string and match against a known set."""
    if not image:
        return ""
    app = image.split("/")[-1].split(":")[0].lower()
    for known in known_set:
        if known in app:
            return known
    return ""


# ── CA801: No Capability Restrictions ────────────────────────────────


class NoCapabilityRestrictions(BaseRule):
    """Flag services that don't restrict Linux capabilities."""

    id = "CA801"
    name = "no-capability-restrictions"
    severity = Severity.INFO
    scope = Scope.SERVICE
    description = "No capability restrictions defined (consider cap_drop: ALL)"
    category = "security"

    def check_service(
        self,
        service_name: str,
        service_config: dict,
        compose_file: ComposeFile,
    ) -> list[LintIssue]:
        # Skip if privileged — CA802 will catch it
        if service_config.get("privileged") is True:
            return []

        cap_drop = service_config.get("cap_drop", [])
        if cap_drop:
            return []

        image = service_config.get("image", "")
        app = _detect_app(image, _KNOWN_NEEDS_CAPS)
        line = find_service_line(compose_file.raw_content, service_name)

        if app and app in _KNOWN_NEEDS_CAPS:
            needed = _KNOWN_NEEDS_CAPS[app]
            caps_yaml = "\n".join(f"  - {c}" for c in needed)
            fix_text = (
                f"Add capability restrictions for {app}:\n\n"
                f"cap_drop:\n  - ALL\ncap_add:\n{caps_yaml}"
            )
        else:
            fix_text = (
                "Add capability restrictions:\n\n"
                "cap_drop:\n  - ALL\n\n"
                "Or add back only what's needed:\n"
                "cap_drop:\n  - ALL\n"
                "cap_add:\n  - NET_BIND_SERVICE  # ports < 1024"
            )

        return [self._make_issue(
            message="No capability restrictions defined (consider cap_drop: ALL)",
            file_path=str(compose_file.path),
            line=line,
            service=service_name,
            suggested_fix=fix_text,
            learn_more="Dropping capabilities follows the principle of least privilege",
        )]


# ── CA802: Privileged Mode ───────────────────────────────────────────


class PrivilegedMode(BaseRule):
    """Flag containers running in privileged mode."""

    id = "CA802"
    name = "privileged-mode"
    severity = Severity.ERROR
    scope = Scope.SERVICE
    description = "Container running in privileged mode"
    category = "security"

    def check_service(
        self,
        service_name: str,
        service_config: dict,
        compose_file: ComposeFile,
    ) -> list[LintIssue]:
        if service_config.get("privileged") is not True:
            return []

        image = service_config.get("image", "")
        app = _detect_app(image, _PRIVILEGED_LEGITIMATE)
        line = find_service_line(compose_file.raw_content, service_name)

        if app and app in _PRIVILEGED_LEGITIMATE:
            # Downgrade to WARNING for known legitimate use
            return [self._make_issue(
                message=f"Running in privileged mode ({_PRIVILEGED_LEGITIMATE[app]})",
                file_path=str(compose_file.path),
                line=line,
                service=service_name,
                fix_available=True,
                suggested_fix=(
                    f"Privileged mode is known to be needed for {app}.\n"
                    "If possible, replace with specific capabilities:\n\n"
                    "cap_add:\n  - SYS_ADMIN"
                ),
                learn_more="Privileged mode grants ALL host capabilities to the container",
            )]

        return [self._make_issue(
            message="Running in privileged mode (major security risk)",
            file_path=str(compose_file.path),
            line=line,
            service=service_name,
            fix_available=True,
            suggested_fix=(
                "Remove privileged mode:\n\n"
                "Remove: privileged: true\n\n"
                "If specific capabilities are needed, use cap_add instead:\n"
                "cap_add:\n  - NET_ADMIN"
            ),
            learn_more="Privileged containers have full host access — avoid unless absolutely required",
        )]

    def _make_issue(self, *, message, file_path, line, service,
                    fix_available=False, suggested_fix=None, learn_more=None):
        """Override to adjust severity for legitimate use cases."""
        # Detect severity from message content
        if "known to be needed" in (suggested_fix or ""):
            severity = Severity.WARNING
        else:
            severity = self.severity

        return LintIssue(
            rule_id=self.id,
            rule_name=self.name,
            severity=severity,
            message=message,
            file_path=file_path,
            line=line,
            service=service,
            fix_available=fix_available,
            suggested_fix=suggested_fix,
            learn_more=learn_more,
        )


# ── CA803: No Read-Only Root Filesystem ──────────────────────────────


class NoReadOnlyRoot(BaseRule):
    """Suggest read-only root filesystem for compatible services."""

    id = "CA803"
    name = "no-read-only-root"
    severity = Severity.INFO
    scope = Scope.SERVICE
    description = "Container could run with read-only root filesystem"
    category = "security"

    def check_service(
        self,
        service_name: str,
        service_config: dict,
        compose_file: ComposeFile,
    ) -> list[LintIssue]:
        if service_config.get("read_only") is True:
            return []

        image = service_config.get("image", "")

        # Check if this is a known writable-required app
        writable_app = _detect_app(image, _NEEDS_WRITABLE)
        if writable_app:
            return []

        # Check if this is a known read-only-safe app
        safe_app = _detect_app(image, _READONLY_SAFE)
        if not safe_app:
            return []

        tmpfs_paths = _READONLY_SAFE[safe_app]
        tmpfs_yaml = "\n".join(f"  - {p}" for p in tmpfs_paths)
        line = find_service_line(compose_file.raw_content, service_name)

        return [self._make_issue(
            message=f"Container could run with read-only root ({safe_app} supports it)",
            file_path=str(compose_file.path),
            line=line,
            service=service_name,
            suggested_fix=(
                f"Add read-only root with tmpfs for write paths:\n\n"
                f"read_only: true\ntmpfs:\n{tmpfs_yaml}"
            ),
            learn_more="Read-only root prevents runtime filesystem tampering",
        )]


# ── CA804: No New Privileges ─────────────────────────────────────────


class NoNewPrivileges(BaseRule):
    """Flag services missing the no-new-privileges security option."""

    id = "CA804"
    name = "no-new-privileges"
    severity = Severity.INFO
    scope = Scope.SERVICE
    description = "Missing no-new-privileges security option"
    category = "security"

    def check_service(
        self,
        service_name: str,
        service_config: dict,
        compose_file: ComposeFile,
    ) -> list[LintIssue]:
        security_opt = service_config.get("security_opt", [])
        if not isinstance(security_opt, list):
            security_opt = []

        has_nnp = any("no-new-privileges:true" in str(opt) for opt in security_opt)
        if has_nnp:
            return []

        line = find_service_line(compose_file.raw_content, service_name)
        return [self._make_issue(
            message="Missing 'no-new-privileges' security option",
            file_path=str(compose_file.path),
            line=line,
            service=service_name,
            fix_available=True,
            suggested_fix=(
                'Add no-new-privileges:\n\n'
                'security_opt:\n  - "no-new-privileges:true"'
            ),
            learn_more="Prevents privilege escalation inside the container",
        )]
