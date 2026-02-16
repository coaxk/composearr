"""Docker registry API client for tag lookups and freshness checking."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import List, Optional

try:
    import requests

    _HAS_REQUESTS = True
except ImportError:
    _HAS_REQUESTS = False


@dataclass
class ImageTag:
    """Image tag information from a registry."""

    name: str
    digest: str = ""
    created: Optional[datetime] = None
    size_bytes: Optional[int] = None


@dataclass
class ImageInfo:
    """Parsed image reference."""

    registry: str
    repo: str
    tag: str


@dataclass
class FreshnessResult:
    """Freshness check result for a single image."""

    service: str
    image: str
    current_tag: str
    latest_stable: Optional[str] = None
    latest_tag: Optional[str] = None
    available_tags: int = 0
    age_days: Optional[int] = None
    up_to_date: bool = False
    error: Optional[str] = None
    file_path: str = ""


# Semver-like pattern: major.minor.patch with optional pre-release
_SEMVER_RE = re.compile(
    r"^v?(\d+)(?:\.(\d+))?(?:\.(\d+))?(?:[-.]?\d+)?$"
)

# Tags to exclude from "latest stable"
_UNSTABLE_PATTERNS = frozenset({
    "latest", "dev", "develop", "nightly", "beta", "alpha", "rc",
    "canary", "edge", "master", "main", "test", "testing", "snapshot",
})


def parse_image(image: str) -> ImageInfo:
    """Parse a Docker image reference into registry, repo, tag.

    Handles:
        nginx:latest           -> docker.io / library/nginx / latest
        user/repo:1.0          -> docker.io / user/repo / 1.0
        ghcr.io/user/repo:tag  -> ghcr.io / user/repo / tag
        lscr.io/linuxserver/sonarr:4.0 -> lscr.io / linuxserver/sonarr / 4.0
    """
    # Split off tag
    if ":" in image.split("/")[-1]:
        image_part, tag = image.rsplit(":", 1)
    else:
        image_part = image
        tag = "latest"

    parts = image_part.split("/")

    if len(parts) == 1:
        # Simple image like "nginx"
        return ImageInfo(registry="docker.io", repo=f"library/{parts[0]}", tag=tag)

    # Check if first part is a registry (has a dot or is localhost)
    if "." in parts[0] or ":" in parts[0] or parts[0] == "localhost":
        registry = parts[0]
        repo = "/".join(parts[1:])
    else:
        # user/repo format on Docker Hub
        registry = "docker.io"
        repo = "/".join(parts)

    return ImageInfo(registry=registry, repo=repo, tag=tag)


def _parse_semver(tag: str) -> Optional[tuple[int, int, int]]:
    """Parse a tag as semver, returns (major, minor, patch) or None."""
    m = _SEMVER_RE.match(tag)
    if not m:
        return None
    major = int(m.group(1))
    minor = int(m.group(2) or 0)
    patch = int(m.group(3) or 0)
    return (major, minor, patch)


def _is_unstable(tag_name: str) -> bool:
    """Check if a tag looks unstable/non-release."""
    lower = tag_name.lower()
    for pattern in _UNSTABLE_PATTERNS:
        if pattern in lower:
            return True
    # Tags with hash-like suffixes (sha256, commit hashes)
    if re.match(r"^[0-9a-f]{7,40}$", lower):
        return True
    return False


class RegistryClient:
    """Client for querying Docker registries for available tags."""

    def __init__(self, timeout: int = 10) -> None:
        self.timeout = timeout
        self._session = None

    @property
    def session(self):
        if self._session is None:
            if not _HAS_REQUESTS:
                return None
            self._session = requests.Session()
            self._session.headers["Accept"] = "application/json"
        return self._session

    def get_tags(self, image: str) -> List[ImageTag]:
        """Get available tags for an image from its registry."""
        if not _HAS_REQUESTS:
            return []

        info = parse_image(image)

        try:
            if info.registry == "docker.io":
                return self._get_dockerhub_tags(info.repo)
            elif info.registry == "ghcr.io":
                return self._get_ghcr_tags(info.repo)
            elif info.registry == "lscr.io":
                # LSCR uses GHCR under the hood
                return self._get_ghcr_tags(f"linuxserver/{info.repo.split('/')[-1]}")
            else:
                return self._get_generic_tags(info.registry, info.repo)
        except Exception:
            return []

    def _get_dockerhub_tags(self, repo: str) -> List[ImageTag]:
        """Get tags from Docker Hub API v2."""
        url = f"https://hub.docker.com/v2/repositories/{repo}/tags"
        params = {"page_size": 50, "ordering": "last_updated"}

        try:
            resp = self.session.get(url, params=params, timeout=self.timeout)
            resp.raise_for_status()
            data = resp.json()

            tags: list[ImageTag] = []
            for item in data.get("results", []):
                created = None
                if "last_updated" in item and item["last_updated"]:
                    try:
                        ts = item["last_updated"].replace("Z", "+00:00")
                        created = datetime.fromisoformat(ts)
                    except (ValueError, TypeError):
                        pass

                tags.append(ImageTag(
                    name=item.get("name", ""),
                    digest=item.get("digest", ""),
                    created=created,
                    size_bytes=item.get("full_size"),
                ))

            return tags
        except Exception:
            return []

    def _get_ghcr_tags(self, repo: str) -> List[ImageTag]:
        """Get tags from GitHub Container Registry (public repos only)."""
        # GHCR uses OCI distribution spec; public images need a token
        token_url = f"https://ghcr.io/token?scope=repository:{repo}:pull"

        try:
            token_resp = self.session.get(token_url, timeout=self.timeout)
            token_resp.raise_for_status()
            token = token_resp.json().get("token", "")

            url = f"https://ghcr.io/v2/{repo}/tags/list"
            headers = {"Authorization": f"Bearer {token}"}
            resp = self.session.get(url, headers=headers, timeout=self.timeout)
            resp.raise_for_status()
            data = resp.json()

            return [
                ImageTag(name=tag_name)
                for tag_name in data.get("tags", [])
            ]
        except Exception:
            return []

    def _get_generic_tags(self, registry: str, repo: str) -> List[ImageTag]:
        """Get tags from a generic OCI-compatible registry."""
        url = f"https://{registry}/v2/{repo}/tags/list"

        try:
            resp = self.session.get(url, timeout=self.timeout)
            resp.raise_for_status()
            data = resp.json()

            return [
                ImageTag(name=tag_name)
                for tag_name in data.get("tags", [])
            ]
        except Exception:
            return []

    def get_latest_stable(self, tags: List[ImageTag]) -> Optional[ImageTag]:
        """Find the latest stable tag from a list.

        Strategy:
        1. Filter out unstable tags (latest, dev, nightly, alpha, beta, etc.)
        2. Try to find highest semver tag
        3. Fall back to most recently created tag
        """
        stable = [t for t in tags if t.name and not _is_unstable(t.name)]

        if not stable:
            return None

        # Try semver sorting
        semver_tags = []
        for tag in stable:
            sv = _parse_semver(tag.name)
            if sv:
                semver_tags.append((sv, tag))

        if semver_tags:
            semver_tags.sort(key=lambda x: x[0], reverse=True)
            return semver_tags[0][1]

        # Fall back to most recently created
        with_dates = [t for t in stable if t.created]
        if with_dates:
            with_dates.sort(key=lambda t: t.created, reverse=True)
            return with_dates[0]

        # Last resort: return last tag (often most recent)
        return stable[-1] if stable else None

    def check_freshness(
        self,
        services: dict[str, dict],
        file_path: str = "",
    ) -> List[FreshnessResult]:
        """Check freshness for all services in a compose file.

        Args:
            services: Dict of service_name -> service_config.
            file_path: Path to the compose file (for display).

        Returns:
            List of FreshnessResult for each service with an image.
        """
        results: list[FreshnessResult] = []

        for svc_name, svc_config in services.items():
            image = svc_config.get("image") if isinstance(svc_config, dict) else None
            if not image:
                continue

            info = parse_image(str(image))

            fr = FreshnessResult(
                service=svc_name,
                image=str(image),
                current_tag=info.tag,
                file_path=file_path,
            )

            try:
                tags = self.get_tags(str(image))
                fr.available_tags = len(tags)

                if not tags:
                    fr.error = "No tags found (private repo or network issue)"
                    results.append(fr)
                    continue

                latest = self.get_latest_stable(tags)
                if latest:
                    fr.latest_stable = latest.name
                    fr.up_to_date = (
                        info.tag == latest.name
                        or info.tag == "latest"  # Can't compare latest meaningfully
                    )
                    if latest.created:
                        now = datetime.now(timezone.utc)
                        if latest.created.tzinfo is None:
                            age = now - latest.created.replace(tzinfo=timezone.utc)
                        else:
                            age = now - latest.created
                        fr.age_days = age.days

                # Also record the actual "latest" tag if present
                latest_tag = next((t for t in tags if t.name == "latest"), None)
                if latest_tag:
                    fr.latest_tag = "latest"

            except Exception as e:
                fr.error = str(e)

            results.append(fr)

        return results
