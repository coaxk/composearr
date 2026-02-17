"""Rule severity profiles for different environments."""

from __future__ import annotations

from composearr.config import DEFAULT_RULES


# Profile definitions: profile_name -> {rule_id: severity}
# Only overrides are listed — unlisted rules keep their defaults.

PROFILES: dict[str, dict[str, str]] = {
    "strict": {
        # Upgrade info rules to warnings
        "CA003": "warning",   # untrusted-registry
        "CA503": "warning",   # resource-limits-unusual
        "CA701": "warning",   # prefer-named-volumes
        "CA801": "warning",   # no-capability-restrictions
        "CA803": "warning",   # no-read-only-root
        "CA804": "warning",   # no-new-privileges
        "CA901": "warning",   # resource-requests-mismatch
        "CA902": "warning",   # restart-policy-unlimited
        "CA904": "warning",   # no-user-namespace
        # Upgrade warnings to errors
        "CA001": "error",     # no-latest-tag
        "CA201": "error",     # require-healthcheck
        "CA202": "error",     # no-fake-healthcheck
        "CA203": "error",     # require-restart-policy
        "CA303": "error",     # isolated-service-ports
        "CA402": "error",     # umask-inconsistent
        "CA403": "error",     # missing-timezone
        "CA501": "error",     # missing-memory-limit
        "CA502": "error",     # missing-cpu-limit
        "CA504": "error",     # no-logging-config
        "CA505": "error",     # no-log-rotation
        "CA601": "error",     # hardlink-path-mismatch
        "CA903": "error",     # tmpfs-no-size-limit
    },
    "balanced": {
        # This IS the default — no overrides needed
    },
    "relaxed": {
        # Downgrade errors to warnings
        "CA101": "warning",   # no-inline-secrets
        "CA301": "warning",   # port-conflict
        "CA302": "warning",   # unreachable-dependency
        "CA401": "warning",   # puid-pgid-mismatch
        "CA404": "warning",   # duplicate-env-vars
        "CA702": "warning",   # undefined-volume-ref
        "CA802": "warning",   # privileged-mode
        # Downgrade warnings to info
        "CA001": "info",      # no-latest-tag
        "CA201": "info",      # require-healthcheck
        "CA202": "info",      # no-fake-healthcheck
        "CA203": "info",      # require-restart-policy
        "CA303": "info",      # isolated-service-ports
        "CA304": "info",      # dns-configuration
        "CA402": "info",      # umask-inconsistent
        "CA403": "info",      # missing-timezone
        "CA501": "info",      # missing-memory-limit
        "CA502": "info",      # missing-cpu-limit
        "CA504": "info",      # no-logging-config
        "CA505": "info",      # no-log-rotation
        "CA601": "info",      # hardlink-path-mismatch
        "CA903": "info",      # tmpfs-no-size-limit
    },
}

PROFILE_DESCRIPTIONS: dict[str, str] = {
    "strict": "All rules at maximum severity — ideal for production environments",
    "balanced": "Default severity levels — recommended for most users",
    "relaxed": "Lenient severity levels — for development or learning environments",
}


def get_profile_names() -> list[str]:
    """Return available profile names."""
    return list(PROFILES.keys())


def get_profile_overrides(name: str) -> dict[str, str]:
    """Get severity overrides for a named profile.

    Args:
        name: Profile name (strict, balanced, relaxed).

    Returns:
        Dict of rule_id -> severity overrides.

    Raises:
        ValueError: If profile name is unknown.
    """
    name = name.lower()
    if name not in PROFILES:
        available = ", ".join(sorted(PROFILES.keys()))
        raise ValueError(f"Unknown profile '{name}'. Available: {available}")
    return dict(PROFILES[name])


def apply_profile(rules: dict[str, str], profile_name: str) -> dict[str, str]:
    """Apply a profile's overrides to a rules dict.

    Args:
        rules: Current rule severity mapping.
        profile_name: Profile to apply.

    Returns:
        Updated rules dict with profile overrides applied.
    """
    overrides = get_profile_overrides(profile_name)
    updated = dict(rules)
    updated.update(overrides)
    return updated
