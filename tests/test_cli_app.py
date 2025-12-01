"""Tests for the EthernetRepairApp control flow helpers."""

import io

from automatic_linux_network_repair.eth_repair import cli
from tests.helpers import RecordingLogger


class _DummyApp(cli.EthernetRepairApp):
    """EthernetRepairApp subclass exposing protected helpers for testing."""

    def __init__(self, interface: str = "eth0"):
        super().__init__(interface=interface, dry_run=False, verbose=False, auto=False)


class _RecordingEffects(cli.EthernetRepairSideEffects):
    def __init__(self):
        super().__init__(
            logger=RecordingLogger(),
            stdout=io.StringIO(),
            stderr=io.StringIO(),
        )


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


def test_side_effects_warn_not_root_logs_and_prints():
    """warn_not_root should emit stderr output and a log entry."""

    effects = _RecordingEffects()

    effects.warn_not_root()

    assert "must be run as root" in effects.stderr.getvalue()
    assert any("Not running as root" in msg for msg in effects.logger.messages)


def test_run_auto_mode_uses_side_effects():
    """Auto mode should setup logging, log startup, and trigger repairs."""

    class _AutoApp(cli.EthernetRepairApp):
        def __init__(self, effects: cli.EthernetRepairSideEffects):
            super().__init__(
                interface="eth0",
                dry_run=True,
                verbose=True,
                auto=True,
                side_effects=effects,
            )
            self.auto_runs: int = 0

        def _ensure_root(self) -> bool:
            return True

        def _choose_interface(self) -> str | None:
            return "eth1"

        def _run_auto_repair(self) -> None:
            self.auto_runs += 1

    effects = _RecordingEffects()
    app = _AutoApp(effects)

    exit_code = app.run()

    assert exit_code == 0
    assert effects.logger.setup_calls == [True]
    assert any("starting for interface: eth1" in msg for msg in effects.logger.messages)
    assert any("Dry-run mode enabled" in msg for msg in effects.logger.messages)
    assert any("Log file" in msg for msg in effects.logger.messages)
    assert app.auto_runs == 1
