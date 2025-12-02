"""Tests for network probe helpers."""

from automatic_linux_network_repair.eth_repair import probes
from automatic_linux_network_repair.eth_repair.types import CommandResult


class _StubLogger:
    def __init__(self) -> None:
        self.debug_calls: list[str] = []

    def debug(self, msg: str) -> None:
        self.debug_calls.append(msg)


class _StubShell:
    def __init__(self, stdout: str, returncode: int = 0):
        self._stdout = stdout
        self._returncode = returncode
        self.calls: list[list[str]] = []

    def run_cmd(self, cmd: list[str], timeout: int = 5):  # pragma: no cover - trivial
        self.calls.append(cmd)
        return CommandResult(cmd=cmd, returncode=self._returncode, stdout=self._stdout, stderr="")


def test_detect_active_vpn_services_filters_services(monkeypatch):
    """VPN detection should surface only running VPN-like systemd units."""

    stdout = """
openvpn.service                  loaded active running   OpenVPN service
network-manager.service          loaded active running   Network Manager
wg-quick@wg0.service             loaded active running   WireGuard via wg-quick(8) for wg0
zerotier-one.service             loaded active running   ZeroTier One
ssh.service                      loaded active running   OpenBSD Secure Shell server
"""

    logger = _StubLogger()
    shell = _StubShell(stdout)
    monkeypatch.setattr(probes, "DEFAULT_LOGGER", logger)
    monkeypatch.setattr(probes, "DEFAULT_SHELL", shell)

    services = probes.detect_active_vpn_services()

    assert services == [
        "openvpn.service",
        "wg-quick@wg0.service",
        "zerotier-one.service",
    ]
    assert any("Active VPN services" in call for call in logger.debug_calls)


def test_list_candidate_interfaces_prioritizes_wired(monkeypatch):
    """Interface discovery should sort physical Ethernet before wireless."""

    stdout = """
1: lo: <LOOPBACK> mtu 65536 qdisc noop state DOWN mode DEFAULT group default qlen 1000
2: wlan0: <BROADCAST,MULTICAST> mtu 1500 qdisc noop state DOWN mode DEFAULT group default qlen 1000
3: enp3s0: <BROADCAST,MULTICAST> mtu 1500 qdisc noop state UP mode DEFAULT group default qlen 1000
4: eth1: <BROADCAST,MULTICAST> mtu 1500 qdisc noop state DOWN mode DEFAULT group default qlen 1000
5: wwan0: <BROADCAST,MULTICAST> mtu 1500 qdisc noop state DOWN mode DEFAULT group default qlen 1000
"""

    shell = _StubShell(stdout)
    monkeypatch.setattr(probes, "DEFAULT_SHELL", shell)

    assert probes.list_candidate_interfaces() == ["enp3s0", "eth1", "wlan0", "wwan0"]
