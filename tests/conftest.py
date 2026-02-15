"""Shared fixtures for ComposeArr tests."""

from __future__ import annotations

from pathlib import Path

import pytest


@pytest.fixture()
def make_compose(tmp_path: Path):
    """Factory fixture: create a compose file with given services dict."""

    def _make(
        services: dict,
        *,
        subdir: str | None = None,
        filename: str = "compose.yaml",
        extra_content: str = "",
    ) -> Path:
        base = tmp_path / subdir if subdir else tmp_path
        base.mkdir(parents=True, exist_ok=True)
        compose_path = base / filename

        lines = []
        if extra_content:
            lines.append(extra_content)
        lines.append("services:")

        for svc_name, svc_cfg in services.items():
            lines.append(f"  {svc_name}:")
            for key, value in svc_cfg.items():
                if isinstance(value, dict):
                    lines.append(f"    {key}:")
                    for k, v in value.items():
                        if isinstance(v, list):
                            lines.append(f"      {k}:")
                            for item in v:
                                lines.append(f"        - {item}")
                        else:
                            lines.append(f"      {k}: {_yaml_value(v)}")
                elif isinstance(value, list):
                    lines.append(f"    {key}:")
                    for item in value:
                        lines.append(f"      - {_yaml_value(item)}")
                else:
                    lines.append(f"    {key}: {_yaml_value(value)}")

        compose_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        return compose_path

    return _make


def _yaml_value(val: object) -> str:
    """Format a value for YAML output."""
    if isinstance(val, bool):
        return "true" if val else "false"
    if isinstance(val, str):
        if any(c in val for c in ":{}[]#&*!|>'\"%@`"):
            return f'"{val}"'
        return val
    return str(val)


# ── Fixture data ──────────────────────────────────────────────


VALID_SERVICE = {
    "image": "nginx:1.21",
    "restart": "unless-stopped",
    "environment": {"TZ": "Australia/Sydney"},
    "healthcheck": {
        "test": '["CMD", "curl", "-f", "http://localhost"]',
        "interval": "30s",
    },
}

ARR_SERVICE_SONARR = {
    "image": "lscr.io/linuxserver/sonarr:latest",
    "environment": {"PUID": "1000", "PGID": "1000", "TZ": "Australia/Sydney", "UMASK": "022"},
    "volumes": ["/mnt/data:/data"],
    "ports": ['"8989:8989"'],
    "restart": "unless-stopped",
}

ARR_SERVICE_RADARR = {
    "image": "lscr.io/linuxserver/radarr:latest",
    "environment": {"PUID": "1000", "PGID": "1000", "TZ": "Australia/Sydney", "UMASK": "022"},
    "volumes": ["/mnt/data:/data"],
    "ports": ['"7878:7878"'],
    "restart": "unless-stopped",
}
