"""Tests for advanced port parser."""

from __future__ import annotations

from composearr.scanner.port_parser import parse_port_mapping


class TestPortParser:
    def test_simple_mapping(self):
        result = parse_port_mapping("8080:80")
        assert len(result) == 1
        assert result[0].host_port == 8080
        assert result[0].container_port == 80

    def test_with_protocol(self):
        result = parse_port_mapping("8080:80/udp")
        assert len(result) == 1
        assert result[0].protocol == "udp"

    def test_with_host_ip(self):
        result = parse_port_mapping("127.0.0.1:8080:80")
        assert len(result) == 1
        assert result[0].host_ip == "127.0.0.1"

    def test_ipv6(self):
        result = parse_port_mapping("[::1]:8080:80")
        assert len(result) == 1
        assert result[0].host_ip == "::1"
        assert result[0].host_port == 8080

    def test_range(self):
        result = parse_port_mapping("8080-8082:80-82")
        assert len(result) == 3
        assert result[0].host_port == 8080
        assert result[2].host_port == 8082

    def test_long_syntax(self):
        result = parse_port_mapping(
            {"target": 80, "published": 8080, "protocol": "tcp", "host_ip": "0.0.0.0"}
        )
        assert len(result) == 1
        assert result[0].host_port == 8080

    def test_container_only(self):
        result = parse_port_mapping("80")
        assert len(result) == 0  # No host mapping

    def test_integer_port(self):
        result = parse_port_mapping(80)
        assert len(result) == 0

    def test_sctp_protocol(self):
        result = parse_port_mapping("8080:80/sctp")
        assert len(result) == 1
        assert result[0].protocol == "sctp"

    def test_empty_string(self):
        result = parse_port_mapping("")
        assert len(result) == 0

    def test_long_syntax_missing_published(self):
        result = parse_port_mapping({"target": 80})
        assert len(result) == 0
