"""CA9xx — Advanced resource and operational rules."""

from __future__ import annotations

from typing import TYPE_CHECKING

from composearr.models import LintIssue, Scope, Severity
from composearr.rules.base import BaseRule
from composearr.scanner.parser import find_line_number

if TYPE_CHECKING:
    from composearr.models import ComposeFile


def _get_deploy_resources(service_config: dict) -> tuple[dict, dict]:
    """Extract deploy.resources.(limits, reservations) from a service config."""
    deploy = service_config.get("deploy", {})
    if not isinstance(deploy, dict):
        return {}, {}
    resources = deploy.get("resources", {})
    if not isinstance(resources, dict):
        return {}, {}
    limits = resources.get("limits", {})
    reservations = resources.get("reservations", {})
    if not isinstance(limits, dict):
        limits = {}
    if not isinstance(reservations, dict):
        reservations = {}
    return limits, reservations


class ResourceRequestsMismatch(BaseRule):
    """CA901: Resource reservations defined without limits (or vice versa)."""

    id = "CA901"
    name = "resource-requests-mismatch"
    severity = Severity.INFO
    scope = Scope.SERVICE
    description = "Resource reservations/limits mismatch — define both for predictable behavior"
    category = "resources"

    def check_service(
        self,
        service_name: str,
        service_config: dict,
        compose_file: ComposeFile,
    ) -> list[LintIssue]:
        limits, reservations = _get_deploy_resources(service_config)

        # Nothing defined — CA501/CA502 handle that
        if not limits and not reservations:
            return []

        line = find_line_number(compose_file.raw_content, f"{service_name}:")

        # Has reservations but no limits
        if reservations and not limits:
            return [
                self._make_issue(
                    "Resource reservations defined without limits — container has guaranteed "
                    "minimum but no maximum, can consume unlimited resources",
                    str(compose_file.path),
                    line=line,
                    service=service_name,
                    suggested_fix=(
                        "Add resource limits alongside reservations:\n"
                        "  deploy:\n"
                        "    resources:\n"
                        "      reservations:\n"
                        "        memory: 256M\n"
                        "      limits:\n"
                        "        memory: 512M  # Add upper bound\n"
                        "\n"
                        "Reservations guarantee a minimum, limits cap the maximum.\n"
                        "Define both for predictable resource management."
                    ),
                )
            ]

        # Has limits but no reservations (less critical, just informational)
        if limits and not reservations:
            return [
                self._make_issue(
                    "Resource limits without reservations — container may be starved "
                    "under memory pressure since no minimum is guaranteed",
                    str(compose_file.path),
                    line=line,
                    service=service_name,
                    suggested_fix=(
                        "Consider adding resource reservations:\n"
                        "  deploy:\n"
                        "    resources:\n"
                        "      reservations:\n"
                        "        memory: 128M  # Minimum guaranteed\n"
                        "      limits:\n"
                        "        memory: 512M  # Maximum allowed\n"
                        "\n"
                        "Reservations ensure your container always gets its minimum."
                    ),
                )
            ]

        return []


class RestartPolicyUnlimited(BaseRule):
    """CA902: Restart policy 'always' restarts indefinitely, even after crashes."""

    id = "CA902"
    name = "restart-policy-unlimited"
    severity = Severity.INFO
    scope = Scope.SERVICE
    description = "Restart policy 'always' may cause infinite restart loops on failures"
    category = "reliability"

    def check_service(
        self,
        service_name: str,
        service_config: dict,
        compose_file: ComposeFile,
    ) -> list[LintIssue]:
        restart = service_config.get("restart", "")
        if restart != "always":
            return []

        line = find_line_number(compose_file.raw_content, f"{service_name}:")

        return [
            self._make_issue(
                "Restart policy 'always' restarts on any failure indefinitely — "
                "a misconfigured service will crash-loop forever",
                str(compose_file.path),
                line=line,
                service=service_name,
                fix_available=True,
                suggested_fix=(
                    "Consider 'unless-stopped' instead:\n"
                    "  restart: unless-stopped\n"
                    "\n"
                    "Difference:\n"
                    "  'always'         — Restarts even if you manually stopped it\n"
                    "  'unless-stopped' — Only restarts on crashes, not manual stops\n"
                    "  'on-failure'     — Only restarts on non-zero exit codes\n"
                    "\n"
                    "For crash-loop protection, use deploy restart_policy:\n"
                    "  deploy:\n"
                    "    restart_policy:\n"
                    "      condition: on-failure\n"
                    "      max_attempts: 5\n"
                    "      delay: 10s"
                ),
            )
        ]


class TmpfsNoSizeLimit(BaseRule):
    """CA903: Tmpfs mount without size limit can consume unlimited memory."""

    id = "CA903"
    name = "tmpfs-no-size-limit"
    severity = Severity.WARNING
    scope = Scope.SERVICE
    description = "Tmpfs mount without size limit (can fill container memory)"
    category = "resources"

    def check_service(
        self,
        service_name: str,
        service_config: dict,
        compose_file: ComposeFile,
    ) -> list[LintIssue]:
        tmpfs = service_config.get("tmpfs", [])
        if not tmpfs:
            return []

        line = find_line_number(compose_file.raw_content, f"{service_name}:")
        issues: list[LintIssue] = []

        # tmpfs can be a single string or list
        if isinstance(tmpfs, str):
            tmpfs = [tmpfs]

        for mount in tmpfs:
            if isinstance(mount, str):
                # String form has no size option — always flag
                # Check if it has :size= suffix (docker format)
                if ":size=" in mount.lower():
                    continue  # Has inline size limit
                issues.append(
                    self._make_issue(
                        f"Tmpfs mount '{mount}' has no size limit — unbounded tmpfs "
                        f"can consume all available memory",
                        str(compose_file.path),
                        line=line,
                        service=service_name,
                        suggested_fix=(
                            f"Add a size limit to the tmpfs mount:\n"
                            f"  tmpfs:\n"
                            f"    - {mount}:size=100M\n"
                            f"\n"
                            f"Or use the long-form syntax:\n"
                            f"  volumes:\n"
                            f"    - type: tmpfs\n"
                            f"      target: {mount}\n"
                            f"      tmpfs:\n"
                            f"        size: 100000000  # 100MB in bytes\n"
                            f"\n"
                            f"Tmpfs lives in RAM — without a limit, a runaway process\n"
                            f"writing to tmpfs can cause an OOM kill."
                        ),
                    )
                )
            elif isinstance(mount, dict):
                # Long-form volume mount with type: tmpfs
                if mount.get("type") == "tmpfs":
                    tmpfs_opts = mount.get("tmpfs", {})
                    if not isinstance(tmpfs_opts, dict) or not tmpfs_opts.get("size"):
                        target = mount.get("target", "/tmp")
                        issues.append(
                            self._make_issue(
                                f"Tmpfs mount '{target}' has no size limit",
                                str(compose_file.path),
                                line=line,
                                service=service_name,
                                suggested_fix=(
                                    f"Add a size limit to the tmpfs mount:\n"
                                    f"  volumes:\n"
                                    f"    - type: tmpfs\n"
                                    f"      target: {target}\n"
                                    f"      tmpfs:\n"
                                    f"        size: 100000000  # 100MB in bytes"
                                ),
                            )
                        )

        return issues


class NoUserNamespace(BaseRule):
    """CA904: User namespace remapping not configured (advanced security)."""

    id = "CA904"
    name = "no-user-namespace"
    severity = Severity.INFO
    scope = Scope.SERVICE
    description = "No user namespace remapping (advanced security hardening)"
    category = "security"

    # Services that are known to be incompatible with user namespaces
    _INCOMPATIBLE = frozenset({
        "privileged", "network_mode",  # config keys that indicate incompatibility
    })

    # Known services that need host user namespace
    _NEEDS_HOST_NS = frozenset({
        "dind", "docker", "portainer", "watchtower", "traefik",
    })

    def check_service(
        self,
        service_name: str,
        service_config: dict,
        compose_file: ComposeFile,
    ) -> list[LintIssue]:
        # Skip if already configured
        if service_config.get("userns_mode"):
            return []

        # Skip privileged containers (incompatible)
        if service_config.get("privileged"):
            return []

        # Skip containers with network_mode: host (often incompatible)
        if service_config.get("network_mode") == "host":
            return []

        # Skip known incompatible services
        image = str(service_config.get("image", "")).lower()
        for name in self._NEEDS_HOST_NS:
            if name in image:
                return []

        line = find_line_number(compose_file.raw_content, f"{service_name}:")

        return [
            self._make_issue(
                "User namespace remapping not configured — container processes "
                "run as the same UIDs on the host (root in container = root on host)",
                str(compose_file.path),
                line=line,
                service=service_name,
                suggested_fix=(
                    "User namespace remapping adds an extra layer of isolation:\n"
                    "  userns_mode: host\n"
                    "\n"
                    "What this does:\n"
                    "  Maps container UIDs to unprivileged host UIDs so even\n"
                    "  root inside the container has no host privileges.\n"
                    "\n"
                    "This is an ADVANCED feature — not all services work with it.\n"
                    "Test thoroughly before enabling in production. Services that\n"
                    "need host filesystem access (volume mounts) may need adjusted\n"
                    "file ownership.\n"
                    "\n"
                    "Most homelabs can safely skip this — it's aspirational hardening."
                ),
            )
        ]
