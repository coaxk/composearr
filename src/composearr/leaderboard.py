"""Local leaderboard for ENTERPRISE+ tier users."""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path


@dataclass
class LeaderboardEntry:
    """Anonymous leaderboard entry."""

    user_id: str
    tier: str
    weighted_score: int
    service_count: int
    is_legendary: bool
    timestamp: str


class Leaderboard:
    """Manages the local leaderboard (~/.composearr/leaderboard.json)."""

    ELIGIBLE_TIERS = {"ENTERPRISE", "DATACENTER", "INFRASTRUCTURE"}

    def __init__(self, path: Path | None = None) -> None:
        self.leaderboard_file = path or (Path.home() / ".composearr" / "leaderboard.json")
        self.leaderboard_file.parent.mkdir(parents=True, exist_ok=True)

    def submit_score(self, score: object) -> bool:
        """Submit score if eligible (ENTERPRISE+ tier).

        Args:
            score: StackScore object with tier, weighted_score, service_count, is_legendary().

        Returns:
            True if submitted, False if not eligible.
        """
        tier_value = getattr(score, "tier", None)
        if tier_value is None:
            return False

        tier_name = tier_value.value if hasattr(tier_value, "value") else str(tier_value)
        if tier_name not in self.ELIGIBLE_TIERS:
            return False

        user_id = self._get_user_id()
        entries = self._load()

        entry = {
            "user_id": user_id,
            "tier": tier_name,
            "weighted_score": getattr(score, "weighted_score", 0),
            "service_count": getattr(score, "total_services", 0),
            "is_legendary": score.is_legendary() if hasattr(score, "is_legendary") else False,
            "timestamp": datetime.now().isoformat(),
        }

        existing_idx = next(
            (i for i, e in enumerate(entries) if e.get("user_id") == user_id), None
        )

        if existing_idx is not None:
            if entry["weighted_score"] > entries[existing_idx].get("weighted_score", 0):
                entries[existing_idx] = entry
        else:
            entries.append(entry)

        self._save(entries)
        return True

    def get_top_legends(self, limit: int = 10) -> list[dict]:
        """Get top legendary entries, sorted by weighted score."""
        entries = self._load()
        legendaries = [e for e in entries if e.get("is_legendary")]
        legendaries.sort(key=lambda x: x.get("weighted_score", 0), reverse=True)
        return legendaries[:limit]

    def get_infrastructure(self) -> list[dict]:
        """Get all INFRASTRUCTURE tier entries."""
        entries = self._load()
        return [e for e in entries if e.get("tier") == "INFRASTRUCTURE"]

    # Backward compat alias
    get_titans = get_infrastructure

    def get_all(self) -> list[dict]:
        """Get all entries sorted by weighted score."""
        entries = self._load()
        entries.sort(key=lambda x: x.get("weighted_score", 0), reverse=True)
        return entries

    def _get_user_id(self) -> str:
        """Generate anonymous user ID (hash of hostname + username)."""
        import getpass
        import socket

        identifier = f"{socket.gethostname()}:{getpass.getuser()}"
        return hashlib.sha256(identifier.encode()).hexdigest()[:12]

    def _load(self) -> list[dict]:
        """Load leaderboard from JSON file."""
        if not self.leaderboard_file.exists():
            return []
        try:
            with open(self.leaderboard_file, encoding="utf-8") as f:
                data = json.load(f)
                if not isinstance(data, list):
                    return []
                # Migrate old tier names
                for entry in data:
                    if entry.get("tier") in ("MECHA_NECKBEARD", "TITAN"):
                        entry["tier"] = "INFRASTRUCTURE"
                    if entry.get("tier") == "POWER_USER":
                        entry["tier"] = "PROFESSIONAL"
                return data
        except (json.JSONDecodeError, OSError):
            return []

    def _save(self, entries: list[dict]) -> None:
        """Save leaderboard to JSON file."""
        with open(self.leaderboard_file, "w", encoding="utf-8") as f:
            json.dump(entries, f, indent=2)
