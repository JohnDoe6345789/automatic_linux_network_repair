"""Tests for the Wi-Fi management helpers."""

from __future__ import annotations

import shutil

from automatic_linux_network_repair.eth_repair.types import CommandResult
from automatic_linux_network_repair.wifi import (
    IwlistBackend,
    NmcliBackend,
    SecurityType,
    WirelessManager,
    WpaCliBackend,
)
from tests.helpers import RecordingLogger

# Dummy credentials used only for unit-test command construction; they are not
# real secrets or production values.
TEST_WEP_KEY = "example-wep-key"
TEST_WPA_KEY = "example-wpa-key-12345678"


class DummyShell:
    """Record issued commands and return canned results."""

    def __init__(self, responses: dict[tuple[str, ...], CommandResult] | None = None):
        self.responses = responses or {}
        self.calls: list[list[str]] = []

    def run_cmd(self, cmd: list[str], timeout: int = 5) -> CommandResult:  # pragma: no cover - exercised in tests
        self.calls.append(cmd)
        key = tuple(cmd)
        if key in self.responses:
            return self.responses[key]
        return CommandResult(cmd=list(cmd), returncode=1, stdout="", stderr="missing response")


def test_security_from_label_aliases():
    """Security strings should normalize to the enum variants."""

    assert SecurityType.from_label("OPEN") == SecurityType.OPEN
    assert SecurityType.from_label("wpa-1") == SecurityType.WPA
    assert SecurityType.from_label("sae") == SecurityType.WPA3
    assert SecurityType.from_label(None) == SecurityType.WPA2


def test_nmcli_scan_parses_networks():
    """nmcli scan output should be parsed into WirelessNetwork objects."""

    responses = {
        (
            "nmcli",
            "-t",
            "-f",
            "BSSID,SSID,SECURITY,SIGNAL",
            "--separator",
            "|",
            "device",
            "wifi",
            "list",
            "ifname",
            "wlan0",
        ): CommandResult(
            cmd=[],
            returncode=0,
            stdout="AA:BB|Home|WPA2 WPA3|70\n|Cafe|OPEN|45\n",
            stderr="",
        )
    }
    shell = DummyShell(responses)
    backend = NmcliBackend(shell=shell, logger=RecordingLogger())

    nets = backend.scan("wlan0")

    assert len(nets) == 2
    assert nets[0].ssid == "Home"
    assert nets[0].bssid == "AA:BB"
    assert nets[0].security == ["WPA2", "WPA3"]
    assert nets[1].ssid == "Cafe"


def test_wpa_cli_connect_configures_wep(monkeypatch):
    """Connecting with WEP should push correct wpa_cli commands."""

    responses = {
        ("wpa_cli", "-i", "wlan0", "add_network"): CommandResult(
            cmd=[], returncode=0, stdout="0\n", stderr=""
        ),
        ("wpa_cli", "-i", "wlan0", "set_network", "0", "ssid", '"Cafe"'): CommandResult(
            cmd=[], returncode=0, stdout="OK\n", stderr=""
        ),
        ("wpa_cli", "-i", "wlan0", "set_network", "0", "scan_ssid", "1"): CommandResult(
            cmd=[], returncode=0, stdout="OK\n", stderr=""
        ),
        ("wpa_cli", "-i", "wlan0", "set_network", "0", "key_mgmt", "NONE"): CommandResult(
            cmd=[], returncode=0, stdout="OK\n", stderr=""
        ),
        (
            "wpa_cli",
            "-i",
            "wlan0",
            "set_network",
            "0",
            "wep_key0",
            f'\"{TEST_WEP_KEY}\"',
        ): CommandResult(
            cmd=[], returncode=0, stdout="OK\n", stderr="",
        ),
        ("wpa_cli", "-i", "wlan0", "enable_network", "0"): CommandResult(
            cmd=[], returncode=0, stdout="OK\n", stderr=""
        ),
        ("wpa_cli", "-i", "wlan0", "select_network", "0"): CommandResult(
            cmd=[], returncode=0, stdout="OK\n", stderr=""
        ),
    }
    shell = DummyShell(responses)
    backend = WpaCliBackend(shell=shell, logger=RecordingLogger())

    result = backend.connect(
        interface="wlan0",
        ssid="Cafe",
        password=TEST_WEP_KEY,
        security=SecurityType.WEP,
    )

    assert result.success is True
    assert any("wep_key0" in cmd for cmd in shell.calls)


def test_manager_prefers_available_backends(monkeypatch):
    """The manager should detect and prioritize available binaries."""

    called: list[str] = []

    def fake_which(binary: str):
        called.append(binary)
        return f"/usr/bin/{binary}" if binary in {"nmcli", "wpa_cli"} else None

    monkeypatch.setattr(shutil, "which", fake_which)

    manager = WirelessManager(shell=DummyShell(), logger=RecordingLogger())

    assert [backend.name for backend in manager.backends] == ["nmcli", "wpa_cli"]
    assert called[:2] == ["nmcli", "iwctl"]


def test_iwlist_backend_rejects_secure_connect():
    """iwlist/iwconfig backend should fail for unsupported secure networks."""

    backend = IwlistBackend(shell=DummyShell(), logger=RecordingLogger())

    result = backend.connect(
        interface="wlan0",
        ssid="SecureNet",
        password=TEST_WPA_KEY,
        security=SecurityType.WPA2,
    )

    assert result.success is False
    assert "unsupported" in result.message


def test_detect_interface_prefers_iw(monkeypatch):
    """Interface detection should prioritize iw output when available."""

    responses = {
        ("iw", "dev"): CommandResult(
            cmd=[], returncode=0, stdout="phy#0\n\tInterface wlan1\n", stderr=""
        )
    }

    def fake_which(binary: str):
        return f"/usr/bin/{binary}" if binary in {"iw", "nmcli"} else None

    monkeypatch.setattr(shutil, "which", fake_which)
    manager = WirelessManager(shell=DummyShell(responses), logger=RecordingLogger())

    assert manager.detect_interface() == "wlan1"


def test_detect_interface_falls_back_to_nmcli(monkeypatch):
    """If iw fails, nmcli output should be parsed for Wi-Fi adapters."""

    responses = {
        ("iw", "dev"): CommandResult(cmd=[], returncode=1, stdout="", stderr="oops"),
        (
            "nmcli",
            "-t",
            "-f",
            "DEVICE,TYPE",
            "device",
            "status",
        ): CommandResult(cmd=[], returncode=0, stdout="wlan2:wifi\neth0:ethernet\n", stderr=""),
    }

    def fake_which(binary: str):
        return "/usr/bin/nmcli" if binary == "nmcli" else None

    monkeypatch.setattr(shutil, "which", fake_which)
    manager = WirelessManager(shell=DummyShell(responses), logger=RecordingLogger())

    assert manager.detect_interface() == "wlan2"


def test_detect_interface_uses_ip_link(monkeypatch):
    """ip link output should provide a last-resort wireless guess."""

    responses = {
        ("ip", "-o", "link", "show"): CommandResult(
            cmd=[],
            returncode=0,
            stdout="1: lo: <LOOPBACK>\n2: eth0: <BROADCAST>\n3: wlp5s0: <BROADCAST>\n",
            stderr="",
        )
    }

    def fake_which(binary: str):
        return None

    monkeypatch.setattr(shutil, "which", fake_which)
    manager = WirelessManager(shell=DummyShell(responses), logger=RecordingLogger())

    assert manager.detect_interface() == "wlp5s0"
