"""Tests for known services database."""

from __future__ import annotations

from composearr.data.known_services import KNOWN_SERVICES, ServiceProfile, detect_service


class TestDetectService:
    def test_detects_sonarr(self):
        profile = detect_service("linuxserver/sonarr:latest")
        assert profile is not None
        assert profile.name == "Sonarr"
        assert profile.arr_service

    def test_detects_with_lscr_prefix(self):
        profile = detect_service("lscr.io/linuxserver/radarr:4.0.0")
        assert profile is not None
        assert profile.name == "Radarr"

    def test_detects_with_ghcr_prefix(self):
        profile = detect_service("ghcr.io/flaresolverr/flaresolverr:latest")
        assert profile is not None
        assert profile.name == "FlareSolverr"

    def test_detects_hotio(self):
        profile = detect_service("cr.hotio.dev/hotio/prowlarr:release")
        assert profile is not None
        assert profile.name == "Prowlarr"

    def test_detects_plain_image(self):
        profile = detect_service("postgres:15")
        assert profile is not None
        assert profile.name == "PostgreSQL"

    def test_returns_none_for_unknown(self):
        assert detect_service("my-custom-app:1.0") is None

    def test_returns_none_for_empty(self):
        assert detect_service("") is None

    def test_detects_sha_digest(self):
        profile = detect_service("redis@sha256:abc123")
        assert profile is not None
        assert profile.name == "Redis"

    def test_database_services_have_cmd_healthcheck(self):
        for key in ("postgres", "mariadb", "mysql", "redis", "mongodb"):
            profile = KNOWN_SERVICES[key]
            assert profile.healthcheck_type == "cmd"
            assert profile.healthcheck_command is not None

    def test_arr_services_have_http_healthcheck(self):
        for key in ("sonarr", "radarr", "lidarr", "readarr", "prowlarr"):
            profile = KNOWN_SERVICES[key]
            assert profile.healthcheck_type == "http"
            assert profile.healthcheck_endpoint is not None
            assert profile.arr_service

    def test_arr_services_need_puid_pgid(self):
        for key, profile in KNOWN_SERVICES.items():
            if profile.arr_service:
                assert profile.needs_puid_pgid, f"{key} is arr but doesn't need PUID/PGID"

    def test_known_services_count(self):
        assert len(KNOWN_SERVICES) >= 30
