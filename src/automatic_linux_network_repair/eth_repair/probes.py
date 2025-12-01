"""Probing helpers for interface state, routes, and DNS."""

from __future__ import annotations

import os
import shutil
from typing import Dict, List

from automatic_linux_network_repair.eth_repair.logging_utils import debug
from automatic_linux_network_repair.eth_repair.shell import run_cmd


def interface_exists(iface: str) -> bool:
    res = run_cmd(["ip", "link", "show", "dev", iface])
    return res.returncode == 0


def interface_link_up(iface: str) -> bool:
    res = run_cmd(["ip", "link", "show", "dev", iface])
    if res.returncode != 0:
        return False
    for line in res.stdout.splitlines():
        if "state UP" in line:
            return True
    return False


def interface_ip_addrs(iface: str, family: int) -> List[str]:
    """Return a list of IP address strings for iface."""
    if family == 4:
        res = run_cmd(["ip", "-4", "addr", "show", "dev", iface])
    else:
        res = run_cmd(["ip", "-6", "addr", "show", "dev", iface])

    if res.returncode != 0:
        return []

    addrs: List[str] = []
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
    res = run_cmd(["ip", "route", "show", "default"])
    if res.returncode != 0:
        return False
    for line in res.stdout.splitlines():
        if line.startswith("default "):
            return True
    return False


def ping_host(host: str, count: int = 1, timeout: int = 3) -> bool:
    res = run_cmd(
        ["ping", "-c", str(count), "-w", str(timeout), host],
        timeout=timeout + 1,
    )
    return res.returncode == 0


def dns_resolves(name: str = "deb.debian.org") -> bool:
    res = run_cmd(["getent", "hosts", name])
    if res.returncode != 0:
        return False
    return bool(res.stdout.strip())


def detect_network_managers() -> Dict[str, bool]:
    managers = {
        "NetworkManager": False,
        "systemd-networkd": False,
        "ifupdown": False,
    }

    nm = run_cmd(["systemctl", "is-active", "NetworkManager"])
    managers["NetworkManager"] = nm.returncode == 0

    sn = run_cmd(["systemctl", "is-active", "systemd-networkd"])
    managers["systemd-networkd"] = sn.returncode == 0

    managers["ifupdown"] = shutil.which("ifup") is not None

    debug(f"Network managers detected: {managers}")
    return managers


def list_candidate_interfaces() -> List[str]:
    """
    Return real physical interface names, stripping @physdev suffixes
    and excluding common virtual/tunnel/docker links.
    """
    res = run_cmd(["ip", "-o", "link", "show"])
    if res.returncode != 0:
        return []

    names: List[str] = []
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


def list_all_interfaces_detailed() -> List[str]:
    """Return lines from `ip -br addr show` for full adapter dump."""
    res = run_cmd(["ip", "-br", "addr", "show"])
    if res.returncode != 0:
        return [f"[ip -br addr show failed rc={res.returncode}]"]
    return [line.rstrip("\n") for line in res.stdout.splitlines()]


def read_resolv_conf_summary(max_lines: int = 8) -> List[str]:
    """Return the first few lines of /etc/resolv.conf for debugging."""
    path = "/etc/resolv.conf"
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as fh:
            lines = fh.readlines()
    except Exception as exc:  # noqa: BLE001 - log unexpected access failures
        return [f"[cannot read {path}: {exc}]"]

    summary = [line.rstrip("\n") for line in lines[:max_lines]]
    if len(lines) > max_lines:
        summary.append("... (truncated)")
    return summary
