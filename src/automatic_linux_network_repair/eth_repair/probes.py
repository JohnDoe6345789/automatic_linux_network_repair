"""Probe helpers for inspecting network interfaces and connectivity."""

from __future__ import annotations

import shutil

from automatic_linux_network_repair.eth_repair.logging_utils import DEFAULT_LOGGER
from automatic_linux_network_repair.eth_repair.shell import DEFAULT_SHELL


def interface_exists(iface: str) -> bool:
    res = DEFAULT_SHELL.run_cmd(["ip", "link", "show", "dev", iface])
    return res.returncode == 0


def interface_link_up(iface: str) -> bool:
    res = DEFAULT_SHELL.run_cmd(["ip", "link", "show", "dev", iface])
    if res.returncode != 0:
        return False
    for line in res.stdout.splitlines():
        if "state UP" in line:
            return True
    return False


def interface_ip_addrs(iface: str, family: int) -> list[str]:
    """Return a list of IP address strings for iface."""
    if family == 4:
        res = DEFAULT_SHELL.run_cmd(["ip", "-4", "addr", "show", "dev", iface])
    else:
        res = DEFAULT_SHELL.run_cmd(["ip", "-6", "addr", "show", "dev", iface])

    if res.returncode != 0:
        return []

    addrs: list[str] = []
    for line in res.stdout.splitlines():
        line = line.strip()
        if line.startswith("inet ") or line.startswith("inet6 "):
            parts = line.split()
            if len(parts) >= 2:
                addrs.append(parts[1])
    return addrs


def interface_has_ipv4(iface: str) -> bool:
    return bool(interface_ip_addrs(iface, family=4))


def has_default_route() -> bool:
    res = DEFAULT_SHELL.run_cmd(["ip", "route", "show", "default"])
    if res.returncode != 0:
        return False
    for line in res.stdout.splitlines():
        if line.startswith("default "):
            return True
    return False


def ping_host(host: str, count: int = 1, timeout: int = 3) -> bool:
    res = DEFAULT_SHELL.run_cmd(
        ["ping", "-c", str(count), "-w", str(timeout), host],
        timeout=timeout + 1,
    )
    return res.returncode == 0


def dns_resolves(name: str = "deb.debian.org") -> bool:
    res = DEFAULT_SHELL.run_cmd(["getent", "hosts", name])
    if res.returncode != 0:
        return False
    return bool(res.stdout.strip())


def detect_network_managers() -> dict[str, bool]:
    managers = {
        "NetworkManager": False,
        "systemd-networkd": False,
        "ifupdown": False,
    }

    nm = DEFAULT_SHELL.run_cmd(["systemctl", "is-active", "NetworkManager"])
    managers["NetworkManager"] = nm.returncode == 0

    sn = DEFAULT_SHELL.run_cmd(["systemctl", "is-active", "systemd-networkd"])
    managers["systemd-networkd"] = sn.returncode == 0

    managers["ifupdown"] = shutil.which("ifup") is not None

    DEFAULT_LOGGER.debug(f"Network managers detected: {managers}")
    return managers


def tailscale_status() -> dict[str, bool]:
    """Return whether Tailscale is installed and whether tailscaled is active."""

    installed = shutil.which("tailscale") is not None
    active = False

    if installed:
        ts = DEFAULT_SHELL.run_cmd(["systemctl", "is-active", "tailscaled"])
        active = ts.returncode == 0

    status = {"installed": installed, "active": active}
    DEFAULT_LOGGER.debug(f"Tailscale status detected: {status}")
    return status


def detect_active_vpn_services() -> list[str]:
    """Return a sorted list of running VPN-related systemd services."""

    res = DEFAULT_SHELL.run_cmd(
        ["systemctl", "list-units", "--type=service", "--state=running"]
    )
    if res.returncode != 0 or not res.stdout:
        DEFAULT_LOGGER.debug(
            f"VPN service detection failed rc={res.returncode}: {res.stderr!r}"
        )
        return []

    keywords = ("vpn", "wireguard", "wg-quick", "zerotier")
    matches: set[str] = set()

    for line in res.stdout.splitlines():
        parts = line.split()
        if not parts:
            continue

        unit = parts[0]
        if not unit.endswith(".service"):
            continue

        lower_unit = unit.lower()
        if any(keyword in lower_unit for keyword in keywords):
            matches.add(unit)

    detected = sorted(matches)
    DEFAULT_LOGGER.debug(f"Active VPN services detected: {detected}")
    return detected


def list_candidate_interfaces() -> list[str]:
    """
    Return real physical interface names, stripping @physdev suffixes
    and excluding common virtual/tunnel/docker links.
    """
    res = DEFAULT_SHELL.run_cmd(["ip", "-o", "link", "show"])
    if res.returncode != 0:
        return []

    names: list[str] = []
    for line in res.stdout.splitlines():
        parts = line.split(":")
        if len(parts) < 2:
            continue

        raw = parts[1].strip()
        name = raw.split("@")[0]

        if name == "lo":
            continue

        skip_prefixes = (
            "veth",
            "docker",
            "br-",
            "virbr",
            "wg",
            "tun",
            "tap",
        )
        if any(name.startswith(prefix) for prefix in skip_prefixes):
            continue

        names.append(name)

    return names


def list_all_interfaces_detailed() -> list[str]:
    """Return lines from `ip -br addr show` for full adapter dump."""
    res = DEFAULT_SHELL.run_cmd(["ip", "-br", "addr", "show"])
    if res.returncode != 0:
        return [f"[ip -br addr show failed rc={res.returncode}]"]
    return [line.rstrip("\n") for line in res.stdout.splitlines()]


def read_resolv_conf_summary(max_lines: int = 8) -> list[str]:
    """Return the first few lines of /etc/resolv.conf for debugging."""
    path = "/etc/resolv.conf"
    try:
        with open(path, encoding="utf-8", errors="replace") as fh:
            lines = fh.readlines()
    except Exception as exc:  # noqa: BLE001 - log unexpected access failures
        return [f"[cannot read {path}: {exc}]"]

    summary = [line.rstrip("\n") for line in lines[:max_lines]]
    if len(lines) > max_lines:
        summary.append("... (truncated)")
    return summary
