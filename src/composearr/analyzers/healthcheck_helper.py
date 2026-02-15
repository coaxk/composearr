"""Healthcheck suggestion engine using known service profiles."""

from __future__ import annotations

from composearr.data.known_services import ServiceProfile, detect_service


def suggest_healthcheck(
    service_name: str,
    image: str,
    ports: list[str] | None = None,
) -> dict | None:
    """Suggest a healthcheck for a service based on its image.

    Returns a YAML-ready healthcheck dict, or None if no suggestion available.
    """
    profile = detect_service(image)
    if not profile:
        return _generic_suggestion(ports)

    return _profile_suggestion(profile, ports)


def suggest_healthcheck_text(
    service_name: str,
    image: str,
    ports: list[str] | None = None,
) -> str | None:
    """Return a human-readable healthcheck suggestion string."""
    profile = detect_service(image)
    if not profile:
        return None

    hc = _profile_suggestion(profile, ports)
    if not hc:
        return None

    test = hc["test"]
    if isinstance(test, list):
        return " ".join(test[1:])  # Skip CMD-SHELL prefix
    return test


def _profile_suggestion(
    profile: ServiceProfile,
    ports: list[str] | None = None,
) -> dict | None:
    """Build healthcheck from a known service profile."""
    port = profile.default_port

    if profile.healthcheck_type == "cmd":
        if profile.healthcheck_command:
            return {
                "test": ["CMD-SHELL", profile.healthcheck_command],
                "interval": "30s",
                "timeout": "10s",
                "retries": 3,
                "start_period": "30s",
            }
        return None

    if profile.healthcheck_type == "http" and profile.healthcheck_endpoint and port:
        return {
            "test": [
                "CMD-SHELL",
                f"curl -sf http://localhost:{port}{profile.healthcheck_endpoint} || exit 1",
            ],
            "interval": "30s",
            "timeout": "10s",
            "retries": 3,
            "start_period": "30s",
        }

    if profile.healthcheck_type == "tcp" and port:
        return {
            "test": ["CMD-SHELL", f"nc -z localhost {port} || exit 1"],
            "interval": "30s",
            "timeout": "10s",
            "retries": 3,
            "start_period": "30s",
        }

    return None


def _generic_suggestion(ports: list[str] | None = None) -> dict | None:
    """Fallback: suggest a TCP check if we know a port."""
    if not ports:
        return None

    # Parse the first mapped port
    first_port = ports[0]
    # Handle "8080:80", "8080:80/tcp", "127.0.0.1:8080:80"
    parts = str(first_port).split(":")
    container_port = parts[-1].split("/")[0]

    if container_port.isdigit():
        return {
            "test": ["CMD-SHELL", f"nc -z localhost {container_port} || exit 1"],
            "interval": "30s",
            "timeout": "10s",
            "retries": 3,
            "start_period": "30s",
        }

    return None
