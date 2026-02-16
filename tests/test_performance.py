"""Performance benchmarks — ensure audit scales reasonably."""

from __future__ import annotations

import time
from pathlib import Path

import pytest

from composearr.engine import run_audit
from composearr.formatters.console import ConsoleFormatter
from composearr.formatters.json_formatter import format_json
from composearr.formatters.sarif_formatter import format_sarif
from composearr.models import FormatOptions, Severity
from composearr.rules.CA0xx_images import set_network_enabled
from composearr.scanner.parser import parse_compose_file


# ── Helpers ───────────────────────────────────────────────────


def _make_realistic_service(idx: int) -> str:
    """Generate a realistic compose service definition."""
    images = [
        "lscr.io/linuxserver/sonarr:latest",
        "lscr.io/linuxserver/radarr:latest",
        "nginx:latest",
        "postgres:16",
        "redis:7.2",
        "ghcr.io/hotio/prowlarr:release",
        "portainer/portainer-ce:latest",
        "plexinc/pms-docker:latest",
    ]
    image = images[idx % len(images)]
    port = 8000 + idx
    return (
        f"  svc{idx}:\n"
        f"    image: {image}\n"
        f"    restart: unless-stopped\n"
        f"    ports:\n"
        f"      - \"{port}:80\"\n"
        f"    environment:\n"
        f"      PUID: '1000'\n"
        f"      PGID: '1000'\n"
        f"      TZ: Australia/Sydney\n"
    )


def _create_stack(tmp_path: Path, num_files: int, services_per_file: int = 1) -> None:
    """Create a stack of compose files."""
    for i in range(num_files):
        svc_dir = tmp_path / f"service{i:03d}"
        svc_dir.mkdir()
        lines = ["services:"]
        for j in range(services_per_file):
            lines.append(_make_realistic_service(i * services_per_file + j))
        (svc_dir / "compose.yaml").write_text(
            "\n".join(lines) + "\n", encoding="utf-8"
        )


# ── Benchmarks ────────────────────────────────────────────────


class TestParsePerformance:
    """YAML parsing speed benchmarks."""

    def test_parse_single_file(self, tmp_path: Path):
        """Single file parse should be under 50ms."""
        compose = tmp_path / "compose.yaml"
        compose.write_text(
            "services:\n  app:\n    image: nginx:1.25\n    restart: unless-stopped\n",
            encoding="utf-8",
        )

        start = time.perf_counter()
        for _ in range(100):
            parse_compose_file(compose)
        elapsed = time.perf_counter() - start

        avg_ms = (elapsed / 100) * 1000
        assert avg_ms < 50, f"Single file parse took {avg_ms:.1f}ms (target <50ms)"

    def test_parse_large_file(self, tmp_path: Path):
        """File with 50 services should parse under 200ms."""
        lines = ["services:"]
        for i in range(50):
            lines.append(_make_realistic_service(i))
        compose = tmp_path / "compose.yaml"
        compose.write_text("\n".join(lines) + "\n", encoding="utf-8")

        start = time.perf_counter()
        cf = parse_compose_file(compose)
        elapsed = time.perf_counter() - start

        assert cf.parse_error is None
        assert len(cf.services) == 50
        assert elapsed < 0.2, f"Large file parse took {elapsed:.3f}s (target <0.2s)"


class TestAuditPerformance:
    """Full audit pipeline benchmarks."""

    def setup_method(self):
        set_network_enabled(False)

    def teardown_method(self):
        set_network_enabled(True)

    def test_10_file_audit(self, tmp_path: Path):
        """10-file audit should complete under 2 seconds."""
        _create_stack(tmp_path, 10)

        start = time.perf_counter()
        result = run_audit(tmp_path)
        elapsed = time.perf_counter() - start

        assert len(result.compose_files) == 10
        assert elapsed < 2.0, f"10-file audit took {elapsed:.2f}s (target <2s)"

    def test_50_file_audit(self, tmp_path: Path):
        """50-file audit should complete under 10 seconds."""
        _create_stack(tmp_path, 50)

        start = time.perf_counter()
        result = run_audit(tmp_path)
        elapsed = time.perf_counter() - start

        assert len(result.compose_files) == 50
        assert elapsed < 10.0, f"50-file audit took {elapsed:.2f}s (target <10s)"

    def test_100_file_audit(self, tmp_path: Path):
        """100-file audit should complete under 20 seconds."""
        _create_stack(tmp_path, 100)

        start = time.perf_counter()
        result = run_audit(tmp_path)
        elapsed = time.perf_counter() - start

        assert len(result.compose_files) == 100
        assert elapsed < 20.0, f"100-file audit took {elapsed:.2f}s (target <20s)"
        assert len(result.all_issues) > 0

    def test_dense_file_audit(self, tmp_path: Path):
        """Single file with 50 services should audit under 5 seconds."""
        _create_stack(tmp_path, 1, services_per_file=50)

        start = time.perf_counter()
        result = run_audit(tmp_path)
        elapsed = time.perf_counter() - start

        assert len(result.compose_files) == 1
        assert elapsed < 5.0, f"Dense audit took {elapsed:.2f}s (target <5s)"


class TestFormatterPerformance:
    """Output formatting speed benchmarks."""

    def setup_method(self):
        set_network_enabled(False)

    def teardown_method(self):
        set_network_enabled(True)

    @pytest.fixture()
    def large_result(self, tmp_path: Path):
        """Pre-computed result with many issues for formatter testing."""
        _create_stack(tmp_path, 50)
        return run_audit(tmp_path), tmp_path

    def test_json_format_speed(self, large_result):
        """JSON formatting should be under 1 second."""
        result, root = large_result
        opts = FormatOptions(min_severity=Severity.INFO, verbose=True)

        start = time.perf_counter()
        output = format_json(result, str(root), opts)
        elapsed = time.perf_counter() - start

        assert len(output) > 0
        assert elapsed < 1.0, f"JSON format took {elapsed:.3f}s (target <1s)"

    def test_sarif_format_speed(self, large_result):
        """SARIF formatting should be under 1 second."""
        result, root = large_result
        opts = FormatOptions(min_severity=Severity.INFO, verbose=True)

        start = time.perf_counter()
        output = format_sarif(result, str(root), opts)
        elapsed = time.perf_counter() - start

        assert len(output) > 0
        assert elapsed < 1.0, f"SARIF format took {elapsed:.3f}s (target <1s)"


class TestScalingCharacteristics:
    """Verify audit scales linearly, not exponentially."""

    def setup_method(self):
        set_network_enabled(False)

    def teardown_method(self):
        set_network_enabled(True)

    def test_linear_scaling(self, tmp_path: Path):
        """Doubling input should roughly double runtime (not quadruple)."""
        # Measure 25 files
        dir_a = tmp_path / "small"
        dir_a.mkdir()
        _create_stack(dir_a, 25)

        start = time.perf_counter()
        run_audit(dir_a)
        time_25 = time.perf_counter() - start

        # Measure 50 files
        dir_b = tmp_path / "large"
        dir_b.mkdir()
        _create_stack(dir_b, 50)

        start = time.perf_counter()
        run_audit(dir_b)
        time_50 = time.perf_counter() - start

        # Allow 3x ratio (generous margin for O(n) with overhead)
        if time_25 > 0.01:  # Only check if measurable
            ratio = time_50 / time_25
            assert ratio < 3.0, (
                f"Scaling ratio {ratio:.1f}x for 2x input "
                f"({time_25:.3f}s -> {time_50:.3f}s) suggests non-linear scaling"
            )
