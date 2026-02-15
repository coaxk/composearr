"""Tests for tag analyzer (mocked HTTP — no real network calls)."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from composearr.analyzers.tag_analyzer import (
    _parse_image,
    _recommend_tag,
    analyze_image,
)


class TestParseImage:
    def test_simple_image(self):
        reg, repo, tag = _parse_image("nginx:latest")
        assert reg == "docker.io"
        assert repo == "library/nginx"
        assert tag == "latest"

    def test_no_tag(self):
        reg, repo, tag = _parse_image("nginx")
        assert tag == "latest"

    def test_lscr_image(self):
        reg, repo, tag = _parse_image("lscr.io/linuxserver/plex:latest")
        assert reg == "lscr.io"
        assert repo == "linuxserver/plex"
        assert tag == "latest"

    def test_ghcr_image(self):
        reg, repo, tag = _parse_image("ghcr.io/hotio/sonarr:release")
        assert reg == "ghcr.io"
        assert repo == "hotio/sonarr"
        assert tag == "release"

    def test_dockerhub_org_image(self):
        reg, repo, tag = _parse_image("linuxserver/sonarr:latest")
        assert reg == "docker.io"
        assert repo == "linuxserver/sonarr"
        assert tag == "latest"

    def test_sha_digest(self):
        reg, repo, tag = _parse_image("nginx@sha256:abc123")
        assert tag == "latest"  # No tag in digest-only ref


class TestRecommendTag:
    def test_linuxserver_convention(self):
        tags = ["latest", "version-1.0.0", "version-1.1.0", "version-1.2.0"]
        tag, reason = _recommend_tag(tags, "linuxserver/sonarr")
        assert tag == "version-1.2.0"
        assert "LinuxServer" in reason

    def test_hotio_convention(self):
        tags = ["latest", "release", "nightly", "testing"]
        tag, reason = _recommend_tag(tags, "hotio/radarr")
        assert tag == "release"
        assert "Hotio" in reason

    def test_semver_general(self):
        tags = ["latest", "1.0.0", "1.1.0", "2.0.0", "beta"]
        tag, reason = _recommend_tag(tags, "myapp/service")
        assert tag == "2.0.0"
        assert "semantic" in reason.lower()

    def test_empty_tags(self):
        tag, reason = _recommend_tag([], "myapp/service")
        assert tag == ""

    def test_skips_prerelease(self):
        tags = ["1.0.0", "2.0.0-rc1", "2.0.0-beta", "1.5.0"]
        tag, _ = _recommend_tag(tags, "myapp/service")
        assert tag == "1.5.0"


class TestAnalyzeImage:
    @patch("composearr.analyzers.tag_analyzer._fetch_tags")
    def test_successful_analysis(self, mock_fetch):
        mock_fetch.return_value = ["latest", "1.0.0", "1.1.0", "2.0.0"]
        result = analyze_image("nginx:latest")
        assert result is not None
        assert result.recommended_tag == "2.0.0"

    @patch("composearr.analyzers.tag_analyzer._fetch_tags")
    def test_no_tags_returns_none(self, mock_fetch):
        mock_fetch.return_value = []
        result = analyze_image("nginx:latest")
        assert result is None

    @patch("composearr.analyzers.tag_analyzer._fetch_tags")
    def test_network_error_returns_none(self, mock_fetch):
        mock_fetch.side_effect = Exception("Network error")
        result = analyze_image("nginx:latest")
        assert result is None

    @patch("composearr.analyzers.tag_analyzer._fetch_tags")
    def test_linuxserver_suggestion(self, mock_fetch):
        mock_fetch.return_value = ["latest", "version-3.0.0", "version-4.0.0"]
        result = analyze_image("lscr.io/linuxserver/sonarr:latest")
        assert result is not None
        assert result.recommended_tag == "version-4.0.0"

    @patch("composearr.analyzers.tag_analyzer.HAS_NETWORK", False)
    def test_no_network_deps_returns_none(self):
        result = analyze_image("nginx:latest")
        assert result is None
