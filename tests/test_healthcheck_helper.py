"""Tests for healthcheck suggestion engine."""

from __future__ import annotations

from composearr.analyzers.healthcheck_helper import suggest_healthcheck, suggest_healthcheck_text


class TestSuggestHealthcheck:
    def test_sonarr_suggestion(self):
        hc = suggest_healthcheck("sonarr", "linuxserver/sonarr:latest")
        assert hc is not None
        assert "curl" in hc["test"][1]
        assert "8989" in hc["test"][1]
        assert "/api/v3/health" in hc["test"][1]

    def test_postgres_suggestion(self):
        hc = suggest_healthcheck("db", "postgres:15")
        assert hc is not None
        assert "pg_isready" in hc["test"][1]

    def test_redis_suggestion(self):
        hc = suggest_healthcheck("cache", "redis:7")
        assert hc is not None
        assert "redis-cli" in hc["test"][1]

    def test_traefik_suggestion(self):
        hc = suggest_healthcheck("traefik", "traefik:v2.10")
        assert hc is not None
        assert "/ping" in hc["test"][1]

    def test_unknown_service_with_port(self):
        hc = suggest_healthcheck("myapp", "my-custom-app:1.0", ports=["8080:3000"])
        assert hc is not None
        assert "3000" in hc["test"][1]

    def test_unknown_service_no_port(self):
        hc = suggest_healthcheck("myapp", "my-custom-app:1.0")
        assert hc is None

    def test_gluetun_cmd_type(self):
        hc = suggest_healthcheck("gluetun", "qmcgaw/gluetun:latest")
        assert hc is not None
        assert "healthcheck" in hc["test"][1]

    def test_has_interval_and_retries(self):
        hc = suggest_healthcheck("sonarr", "linuxserver/sonarr:latest")
        assert hc is not None
        assert "interval" in hc
        assert "timeout" in hc
        assert "retries" in hc
        assert "start_period" in hc

    def test_tcp_fallback_for_deluge(self):
        hc = suggest_healthcheck("deluge", "linuxserver/deluge:latest")
        assert hc is not None
        assert "nc -z" in hc["test"][1]


class TestSuggestHealthcheckText:
    def test_sonarr_text(self):
        text = suggest_healthcheck_text("sonarr", "linuxserver/sonarr:latest")
        assert text is not None
        assert "curl" in text
        assert "8989" in text

    def test_unknown_returns_none(self):
        text = suggest_healthcheck_text("myapp", "my-custom-app:1.0")
        assert text is None

    def test_postgres_text(self):
        text = suggest_healthcheck_text("db", "postgres:15")
        assert text is not None
        assert "pg_isready" in text
