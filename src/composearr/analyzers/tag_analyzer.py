"""Tag analyzer — fetch available tags from Docker registries."""

from __future__ import annotations

import re
from dataclasses import dataclass, field

try:
    import requests
    from packaging import version as pkg_version

    HAS_NETWORK = True
except ImportError:
    HAS_NETWORK = False


@dataclass
class TagSuggestion:
    """Result of analyzing an image's tags."""

    image: str
    current_tag: str
    recommended_tag: str
    reasoning: str


def _parse_image(image: str) -> tuple[str, str, str]:
    """Parse image string into (registry, repo, tag).

    Examples:
        nginx:latest → (docker.io, library/nginx, latest)
        lscr.io/linuxserver/plex:latest → (lscr.io, linuxserver/plex, latest)
        ghcr.io/hotio/sonarr:release → (ghcr.io, hotio/sonarr, release)
    """
    # Strip digest
    clean = image.split("@")[0]

    # Check for explicit registry
    if "/" in clean and ("." in clean.split("/")[0] or ":" in clean.split("/")[0]):
        parts = clean.split("/", 1)
        registry = parts[0]
        rest = parts[1]
    else:
        registry = "docker.io"
        rest = clean

    if ":" in rest:
        repo, tag = rest.rsplit(":", 1)
    else:
        repo, tag = rest, "latest"

    # Official images: nginx → library/nginx
    if registry == "docker.io" and "/" not in repo:
        repo = f"library/{repo}"

    return registry, repo, tag


def _fetch_dockerhub_tags(repo: str) -> list[str]:
    """Fetch tags from Docker Hub."""
    url = f"https://registry.hub.docker.com/v2/repositories/{repo}/tags"
    resp = requests.get(url, params={"page_size": 50, "ordering": "last_updated"}, timeout=5)
    resp.raise_for_status()
    return [t["name"] for t in resp.json().get("results", [])]


def _fetch_ghcr_tags(repo: str) -> list[str]:
    """Fetch tags from GHCR (public repos only)."""
    url = f"https://ghcr.io/v2/{repo}/tags/list"
    resp = requests.get(url, timeout=5, headers={"Accept": "application/json"})
    resp.raise_for_status()
    return resp.json().get("tags", [])


def _fetch_lscr_tags(repo: str) -> list[str]:
    """Fetch tags from LinuxServer Container Registry."""
    # LSCR proxies to GHCR
    return _fetch_ghcr_tags(f"linuxserver/{repo.split('/')[-1]}")


def _fetch_tags(registry: str, repo: str) -> list[str]:
    """Fetch tags for any supported registry."""
    if registry == "docker.io":
        return _fetch_dockerhub_tags(repo)
    elif registry == "ghcr.io":
        return _fetch_ghcr_tags(repo)
    elif registry == "lscr.io":
        return _fetch_lscr_tags(repo)
    return []


def _recommend_tag(tags: list[str], repo: str) -> tuple[str, str]:
    """Pick the best tag and explain why.

    Returns (recommended_tag, reasoning).
    """
    if not tags:
        return "", "No tags found"

    # LinuxServer: prefer version-X.Y.Z
    if "linuxserver" in repo.lower():
        version_tags = [t for t in tags if t.startswith("version-")]
        if version_tags:
            best = _latest_semver(version_tags, prefix="version-")
            if best:
                return best, "LinuxServer stable release"

    # Hotio: prefer release
    if "hotio" in repo.lower():
        if "release" in tags:
            return "release", "Hotio stable channel"

    # General: find latest semver
    best = _latest_semver(tags)
    if best:
        return best, "latest stable version"

    return "", "Could not determine best tag"


def _latest_semver(tags: list[str], prefix: str = "") -> str:
    """Find the latest semantic version tag."""
    versions = []
    for tag in tags:
        clean = tag[len(prefix):] if prefix and tag.startswith(prefix) else tag
        try:
            v = pkg_version.parse(clean)
            if not v.is_prerelease and not v.is_devrelease:
                versions.append((v, tag))
        except Exception:
            continue

    if versions:
        versions.sort(key=lambda x: x[0], reverse=True)
        return versions[0][1]
    return ""


def analyze_image(image: str) -> TagSuggestion | None:
    """Analyze an image and suggest the best tag.

    Returns None if network features aren't available or analysis fails.
    """
    if not HAS_NETWORK:
        return None

    try:
        registry, repo, current_tag = _parse_image(image)
        tags = _fetch_tags(registry, repo)
        if not tags:
            return None

        recommended, reasoning = _recommend_tag(tags, repo)
        if not recommended:
            return None

        return TagSuggestion(
            image=image,
            current_tag=current_tag,
            recommended_tag=recommended,
            reasoning=reasoning,
        )
    except Exception:
        # Never crash on network/parsing errors
        return None
