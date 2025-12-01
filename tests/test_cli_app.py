"""Tests for the EthernetRepairApp control flow helpers."""

from automatic_linux_network_repair.eth_repair import cli


class _DummyApp(cli.EthernetRepairApp):
    """EthernetRepairApp subclass exposing protected helpers for testing."""

    def __init__(self, interface: str = "eth0"):
        super().__init__(interface=interface, dry_run=False, verbose=False, auto=False)


def test_choose_interface_auto_selects_candidate(monkeypatch):
    """When eth0 is missing, the first candidate should be chosen."""

    app = _DummyApp(interface="eth0")

    monkeypatch.setattr(cli, "interface_exists", lambda iface: False)
    monkeypatch.setattr(cli, "list_candidate_interfaces", lambda: ["enp0s3", "wlan0"])

    assert app._choose_interface() == "enp0s3"


def test_choose_interface_rejects_invalid_target(monkeypatch):
    """Non-default interfaces that do not exist should be rejected."""

    app = _DummyApp(interface="eno1")

    monkeypatch.setattr(cli, "interface_exists", lambda iface: False)
    monkeypatch.setattr(cli, "list_candidate_interfaces", lambda: ["enp0s3", "wlan0"])

    assert app._choose_interface() is None


def test_ensure_root_blocks_non_root(monkeypatch, capsys):
    """_ensure_root should warn and return False when not running as root."""

    app = _DummyApp(interface="eth0")

    monkeypatch.setattr(cli.os, "geteuid", lambda: 1000)

    assert app._ensure_root() is False

    captured = capsys.readouterr()
    assert "must be run as root" in captured.err
