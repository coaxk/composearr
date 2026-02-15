"""Tests for volume parser."""

from __future__ import annotations

from composearr.scanner.volume_parser import parse_volume


class TestVolumeParser:
    def test_bind_mount(self):
        vol = parse_volume("/host/path:/container/path")
        assert vol is not None
        assert vol.source == "/host/path"
        assert vol.target == "/container/path"
        assert vol.volume_type == "bind"
        assert not vol.read_only

    def test_read_only(self):
        vol = parse_volume("/host:/container:ro")
        assert vol is not None
        assert vol.read_only

    def test_named_volume(self):
        vol = parse_volume("mydata:/data")
        assert vol is not None
        assert vol.volume_type == "volume"
        assert vol.source == "mydata"

    def test_selinux_label(self):
        vol = parse_volume("/host:/container:z")
        assert vol is not None
        assert not vol.read_only

    def test_ro_with_selinux(self):
        vol = parse_volume("/host:/container:ro,Z")
        assert vol is not None
        assert vol.read_only

    def test_long_syntax(self):
        vol = parse_volume({
            "type": "bind",
            "source": "/host",
            "target": "/container",
            "read_only": True,
        })
        assert vol is not None
        assert vol.source == "/host"
        assert vol.read_only
        assert vol.volume_type == "bind"

    def test_tmpfs_long_syntax(self):
        vol = parse_volume({"type": "tmpfs", "target": "/tmp"})
        assert vol is not None
        assert vol.volume_type == "tmpfs"

    def test_anonymous_volume(self):
        vol = parse_volume("/data")
        assert vol is not None
        assert vol.target == "/data"

    def test_empty_string(self):
        vol = parse_volume("")
        assert vol is None

    def test_relative_path(self):
        vol = parse_volume("./config:/config")
        assert vol is not None
        assert vol.volume_type == "bind"
