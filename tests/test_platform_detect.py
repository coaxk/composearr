"""Tests for management platform detection."""

from __future__ import annotations

from pathlib import Path

import pytest

from composearr.scanner.platform_detect import classify_paths


class TestPlatformDetect:
    def test_komodo_detection(self, tmp_path: Path):
        """Should detect Komodo periphery repos as managed."""
        komodo_path = tmp_path / "komodo" / "periphery" / "repos" / "myapp"
        komodo_path.mkdir(parents=True)
        managed_file = komodo_path / "compose.yaml"
        managed_file.write_text("services: {}", encoding="utf-8")

        canonical_path = tmp_path / "myapp"
        canonical_path.mkdir()
        canonical_file = canonical_path / "compose.yaml"
        canonical_file.write_text("services: {}", encoding="utf-8")

        all_paths = [canonical_file, managed_file]
        canonical, managed = classify_paths(all_paths, tmp_path)

        assert len(canonical) == 1
        assert len(managed) == 1
        assert "Komodo" in managed

    def test_dockge_detection(self, tmp_path: Path):
        """Should detect Dockge stacks as managed."""
        dockge_path = tmp_path / "dockge" / "stacks" / "myapp"
        dockge_path.mkdir(parents=True)
        managed_file = dockge_path / "compose.yaml"
        managed_file.write_text("services: {}", encoding="utf-8")

        all_paths = [managed_file]
        canonical, managed = classify_paths(all_paths, tmp_path)

        assert len(canonical) == 0
        assert "Dockge" in managed

    def test_no_platform_detected(self, tmp_path: Path):
        """Should return all files as canonical when no platform detected."""
        svc = tmp_path / "myservice"
        svc.mkdir()
        f = svc / "compose.yaml"
        f.write_text("services: {}", encoding="utf-8")

        canonical, managed = classify_paths([f], tmp_path)

        assert len(canonical) == 1
        assert len(managed) == 0

    def test_portainer_detection(self, tmp_path: Path):
        """Should detect Portainer data as managed."""
        portainer_path = tmp_path / "portainer" / "compose" / "myapp"
        portainer_path.mkdir(parents=True)
        managed_file = portainer_path / "compose.yaml"
        managed_file.write_text("services: {}", encoding="utf-8")

        all_paths = [managed_file]
        canonical, managed = classify_paths(all_paths, tmp_path)

        assert "Portainer" in managed

    def test_empty_input(self, tmp_path: Path):
        canonical, managed = classify_paths([], tmp_path)
        assert canonical == []
        assert managed == {}
