#!/usr/bin/env python3
"""
Interactive Ethernet repair helper for Debian / OMV style systems.

Key features:
- Numbered menu for checks and repairs.
- Fuzzy diagnosis (no IPv4, no route, DNS broken, etc).
- Tries systemd-networkd first if active, then falls back to ifup/dhclient.
- Uses Python logging module:
  * Logs to console
  * Also logs to /tmp/eth_repair.log for later debugging
- After each repair, re-checks and prints interface / connectivity status.
- /etc/resolv.conf editing is ONLY done from explicit menu options
  or from fuzzy DNS repair AFTER confirmation.
- Advanced systemd / DNS menu to toggle systemd-resolved and resolv.conf modes.
"""

from __future__ import annotations

import argparse
import dataclasses
import enum
import logging
import os
import shlex
import shutil
import subprocess
import sys
from typing import Dict, List, Optional, Tuple


# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

LOGGER = logging.getLogger("eth_repair")


def setup_logging(verbose: bool) -> None:
    """
    Configure logging to console and /tmp/eth_repair.log.
    """
    level = logging.DEBUG if verbose else logging.INFO

    handlers: List[logging.Handler] = []
    console = logging.StreamHandler()
    handlers.append(console)

    try:
        file_handler = logging.FileHandler(
            "/tmp/eth_repair.log",
            mode="a",
            encoding="utf-8",
        )
        handlers.append(file_handler)
    except Exception:
        # If we cannot open the log file, continue with console-only logging.
        pass

    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(message)s",
        handlers=handlers,
    )


def log(msg: str) -> None:
    LOGGER.info(msg)


def debug(msg: str) -> None:
    LOGGER.debug(msg)


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

@dataclasses.dataclass
class CommandResult:
    cmd: List[str]
    returncode: int
    stdout: str
    stderr: str


class Suspicion(enum.Enum):
    INTERFACE_MISSING = "interface_missing"
    LINK_DOWN = "link_down"
    NO_IPV4 = "no_ipv4"
    NO_ROUTE = "no_route"
    NO_INTERNET = "no_internet"
    DNS_BROKEN = "dns_broken"


SUSPICION_LABELS: Dict[Suspicion, str] = {
    Suspicion.INTERFACE_MISSING: "Interface missing",
    Suspicion.LINK_DOWN: "Link down",
    Suspicion.NO_IPV4: "No IPv4 address",
    Suspicion.NO_ROUTE: "No default route",
    Suspicion.NO_INTERNET: "No internet (ICMP)",
    Suspicion.DNS_BROKEN: "DNS resolution failing",
}


@dataclasses.dataclass
class Diagnosis:
    suspicion_scores: Dict[Suspicion, float]

    def sorted_scores(self) -> List[Tuple[Suspicion, float]]:
        return sorted(
            self.suspicion_scores.items(),
            key=lambda item: item[1],
            reverse=True,
        )


class ResolvConfMode(enum.Enum):
    SYSTEMD_STUB = "systemd_stub"
    SYSTEMD_FULL = "systemd_full"
    MANUAL = "manual"
    OTHER = "other"


# ---------------------------------------------------------------------------
# Shell helpers
# ---------------------------------------------------------------------------

def cmd_str(cmd: List[str]) -> str:
    return " ".join(shlex.quote(part) for part in cmd)


def run_cmd(
    cmd: List[str],
    timeout: int = 5,
) -> CommandResult:
    """
    Run command and capture stdout/stderr.
    """
    debug(f"Running: {cmd_str(cmd)}")
    try:
        proc = subprocess.run(
            cmd,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=timeout,
            text=True,
        )
    except Exception as exc:  # noqa: BLE001 - broad to log spawn issues
        debug(f"Command failed to start: {exc}")
        return CommandResult(
            cmd=cmd,
            returncode=255,
            stdout="",
            stderr=str(exc),
        )

    debug(
        f"Command rc={proc.returncode} stdout={proc.stdout!r} "
        f"stderr={proc.stderr!r}",
    )
    return CommandResult(
        cmd=cmd,
        returncode=proc.returncode,
        stdout=proc.stdout,
        stderr=proc.stderr,
    )


# ---------------------------------------------------------------------------
# Probes
# ---------------------------------------------------------------------------

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
    """
    Return a list of IP address strings for iface.
    family: 4 or 6.
    """
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
        # Format: "3: eth0p@if2: <BROADCAST,MULTICAST,UP,...>"
        parts = line.split(":")
        if len(parts) < 2:
            continue

        raw = parts[1].strip()
        # Remove @physdev suffix (eth0p@if2 → eth0p)
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
    """
    Return lines from `ip -br addr show` for full adapter dump.
    """
    res = run_cmd(["ip", "-br", "addr", "show"])
    if res.returncode != 0:
        return [f"[ip -br addr show failed rc={res.returncode}]"]
    return [line.rstrip("\n") for line in res.stdout.splitlines()]


def read_resolv_conf_summary(max_lines: int = 8) -> List[str]:
    """
    Return the first few lines of /etc/resolv.conf for debugging.
    """
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


# ---------------------------------------------------------------------------
# systemd-resolved / resolv.conf helpers
# ---------------------------------------------------------------------------

def systemd_resolved_status() -> Dict[str, Optional[bool]]:
    """
    Return dict with keys: active (bool), enabled (bool or None if unknown).
    """
    active_res = run_cmd(["systemctl", "is-active", "systemd-resolved"])
    enabled_res = run_cmd(["systemctl", "is-enabled", "systemd-resolved"])

    active = active_res.returncode == 0
    enabled: Optional[bool]
    if enabled_res.returncode == 0:
        enabled = True
    elif enabled_res.returncode == 1:
        enabled = False
    else:
        enabled = None

    return {"active": active, "enabled": enabled}


def detect_resolv_conf_mode() -> Tuple[ResolvConfMode, str]:
    """
    Detect how /etc/resolv.conf is wired.
    Returns (mode, detail), where detail is target path or explanation.
    """
    path = "/etc/resolv.conf"

    if not os.path.exists(path):
        return (ResolvConfMode.OTHER, "[missing]")

    if os.path.islink(path):
        target = os.path.realpath(path)
        if target == "/run/systemd/resolve/stub-resolv.conf":
            return (ResolvConfMode.SYSTEMD_STUB, target)
        if target == "/run/systemd/resolve/resolv.conf":
            return (ResolvConfMode.SYSTEMD_FULL, target)
        return (ResolvConfMode.OTHER, f"[symlink → {target}]")

    # Regular file
    return (ResolvConfMode.MANUAL, "[regular file]")


def backup_resolv_conf(dry_run: bool) -> None:
    if not os.path.exists("/etc/resolv.conf"):
        return
    apply_action(
        "Backup /etc/resolv.conf to /etc/resolv.conf.bak",
        ["cp", "/etc/resolv.conf", "/etc/resolv.conf.bak"],
        dry_run,
    )


def set_resolv_conf_symlink(target: str, dry_run: bool) -> None:
    backup_resolv_conf(dry_run)
    apply_action(
        f"Point /etc/resolv.conf symlink to {target}",
        ["ln", "-sf", target, "/etc/resolv.conf"],
        dry_run,
    )


def set_resolv_conf_manual_public(dry_run: bool) -> None:
    backup_resolv_conf(dry_run)
    apply_action(
        "Write manual resolv.conf (1.1.1.1 / 8.8.8.8)",
        [
            "bash",
            "-c",
            (
                "printf '%s\n' "
                "'nameserver 1.1.1.1' "
                "'nameserver 8.8.8.8' "
                "> /etc/resolv.conf"
            ),
        ],
        dry_run,
    )


def set_systemd_resolved_enabled(enabled: bool, dry_run: bool) -> None:
    if enabled:
        apply_action(
            "Enable and start systemd-resolved",
            ["systemctl", "enable", "--now", "systemd-resolved"],
            dry_run,
        )
    else:
        apply_action(
            "Disable and stop systemd-resolved",
            ["systemctl", "disable", "--now", "systemd-resolved"],
            dry_run,
        )


def show_systemd_dns_status() -> None:
    status = systemd_resolved_status()
    mode, detail = detect_resolv_conf_mode()

    log("")
    log("=== systemd / DNS status ===")
    log(f"systemd-resolved active : {status['active']}")
    log(f"systemd-resolved enabled: {status['enabled']}")
    log(f"/etc/resolv.conf mode   : {mode.value} ({detail})")
    log("")
    log("/etc/resolv.conf (first lines):")
    for line in read_resolv_conf_summary():
        log(f"  {line}")
    log("=======================================")


# ---------------------------------------------------------------------------
# Diagnosis (with smarter DNS logic)
# ---------------------------------------------------------------------------

def fuzzy_diagnose(iface: str) -> Diagnosis:
    scores: Dict[Suspicion, float] = {
        Suspicion.INTERFACE_MISSING: 0.0,
        Suspicion.LINK_DOWN: 0.0,
        Suspicion.NO_IPV4: 0.0,
        Suspicion.NO_ROUTE: 0.0,
        Suspicion.NO_INTERNET: 0.0,
        Suspicion.DNS_BROKEN: 0.0,
    }

    exists = interface_exists(iface)
    link_up = interface_link_up(iface) if exists else False
    has_ip = interface_has_ipv4(iface) if exists else False
    default_route = has_default_route()
    can_ping_ip = ping_host("8.8.8.8")
    can_resolve = dns_resolves()

    # systemd / resolv.conf info for smarter DNS suspicion
    sd_status = systemd_resolved_status()
    rc_mode, rc_detail = detect_resolv_conf_mode()

    debug(
        "Diag raw: exists=%s link_up=%s has_ip=%s default_route=%s "
        "ping_ip=%s dns=%s sd_active=%s sd_enabled=%s rc_mode=%s rc_detail=%s",
        exists,
        link_up,
        has_ip,
        default_route,
        can_ping_ip,
        can_resolve,
        sd_status["active"],
        sd_status["enabled"],
        rc_mode.value,
        rc_detail,
    )

    if not exists:
        scores[Suspicion.INTERFACE_MISSING] = 1.0
        return Diagnosis(scores)

    if not link_up:
        scores[Suspicion.LINK_DOWN] = 0.8

    if not has_ip:
        scores[Suspicion.NO_IPV4] = 0.7

    if not default_route:
        scores[Suspicion.NO_ROUTE] = 0.6

    if not can_ping_ip:
        scores[Suspicion.NO_INTERNET] = 0.6

    # Base DNS suspicion from getent/ping
    if can_ping_ip and not can_resolve:
        scores[Suspicion.DNS_BROKEN] = 0.9
    elif not can_resolve:
        scores[Suspicion.DNS_BROKEN] = 0.4

    # Smarter DNS suspicion using systemd / resolv.conf wiring
    dns_score = scores[Suspicion.DNS_BROKEN]
    if dns_score > 0.0:
        # systemd stub but resolved is inactive: classic miswire
        if rc_mode == ResolvConfMode.SYSTEMD_STUB and not sd_status["active"]:
            dns_score = max(dns_score, 1.0)
        # Manual resolv.conf while resolved is running: likely fighting
        elif rc_mode == ResolvConfMode.MANUAL and sd_status["active"]:
            dns_score = max(dns_score, 0.95)
        # systemd modes but still broken: strongly DNS-oriented issue
        elif rc_mode in (ResolvConfMode.SYSTEMD_STUB, ResolvConfMode.SYSTEMD_FULL):
            dns_score = max(dns_score, 0.8)

        scores[Suspicion.DNS_BROKEN] = dns_score

    return Diagnosis(scores)


# ---------------------------------------------------------------------------
# Repair actions
# ---------------------------------------------------------------------------

def apply_action(desc: str, cmd: List[str], dry_run: bool) -> bool:
    log(f"[ACTION] {desc}")
    log(f"         {cmd_str(cmd)}")
    if dry_run:
        return True
    res = run_cmd(cmd, timeout=20)
    if res.returncode != 0:
        log(
            f"[WARN] Action failed (rc={res.returncode}): {cmd_str(cmd)} "
            f"stderr={res.stderr.strip()}",
        )
        return False
    return True


def repair_interface_missing(iface: str) -> None:
    log(
        "[INFO] Interface does not exist. This is usually a driver, "
        "hardware or VM configuration issue.",
    )
    log("[HINT] Check dmesg, lspci/lsusb, or hypervisor NIC settings.")


def repair_link_down(iface: str, dry_run: bool) -> None:
    apply_action(
        f"Bring {iface} link UP via ip",
        ["ip", "link", "set", iface, "up"],
        dry_run,
    )


def repair_no_ipv4(
    iface: str,
    managers: Dict[str, bool],
    dry_run: bool,
) -> None:
    """
    Try everything reasonable to obtain IPv4:
    1) systemd-networkd restart (if active)
    2) ifdown/ifup (if available)
    3) dhclient as final fallback
    """
    if managers.get("systemd-networkd", False):
        apply_action(
            "Restart systemd-networkd",
            ["systemctl", "restart", "systemd-networkd"],
            dry_run,
        )
        if not dry_run and interface_has_ipv4(iface):
            log("[OK] IPv4 obtained after systemd-networkd restart.")
            return
        if not dry_run:
            log(
                "[INFO] No IPv4 after systemd-networkd restart; "
                "falling back to ifup / dhclient.",
            )

    if managers.get("ifupdown", False):
        apply_action(
            f"ifdown {iface}",
            ["ifdown", iface],
            dry_run,
        )
        apply_action(
            f"ifup {iface}",
            ["ifup", iface],
            dry_run,
        )
        if not dry_run and interface_has_ipv4(iface):
            log("[OK] IPv4 obtained after ifup.")
            return

    apply_action(
        f"Run dhclient on {iface}",
        ["dhclient", "-v", iface],
        dry_run,
    )
    if not dry_run and interface_has_ipv4(iface):
        log("[OK] IPv4 obtained after dhclient.")
    elif not dry_run:
        log(
            "[WARN] Still no IPv4 after systemd-networkd/ifup/dhclient. "
            "Check your DHCP server or static config.",
        )


def repair_no_route(dry_run: bool) -> None:
    managers = detect_network_managers()

    if managers.get("NetworkManager", False):
        apply_action(
            "Restart NetworkManager",
            ["systemctl", "restart", "NetworkManager"],
            dry_run,
        )
        return

    if managers.get("systemd-networkd", False):
        apply_action(
            "Restart systemd-networkd",
            ["systemctl", "restart", "systemd-networkd"],
            dry_run,
        )
        return

    if managers.get("ifupdown", False):
        apply_action(
            "Restart networking (ifupdown)",
            ["systemctl", "restart", "networking"],
            dry_run,
        )
        return

    log(
        "[INFO] No known network manager to fix default route; "
        "you may need to add it manually.",
    )


def repair_dns_core(allow_resolv_conf_edit: bool, dry_run: bool) -> None:
    """
    Core DNS repair logic.
    If allow_resolv_conf_edit is False, we only restart systemd-resolved.
    """
    status = systemd_resolved_status()
    if status["active"]:
        apply_action(
            "Restart systemd-resolved",
            ["systemctl", "restart", "systemd-resolved"],
            dry_run,
        )
        if not dry_run and dns_resolves():
            log("[OK] DNS fixed after systemd-resolved restart.")
            return

    if not allow_resolv_conf_edit:
        log(
            "[INFO] DNS appears broken; resolv.conf editing is disabled in "
            "this mode. Use menu option 6 or the advanced systemd/DNS menu.",
        )
        return

    backup_resolv_conf(dry_run)
    set_resolv_conf_manual_public(dry_run)

    if not dry_run and dns_resolves():
        log("[OK] DNS working after resolv.conf rewrite.")
    elif not dry_run:
        log(
            "[WARN] DNS still failing after resolv.conf rewrite. "
            "Check firewall / router.",
        )


def repair_dns_fuzzy_with_confirm(dry_run: bool) -> None:
    """
    Fuzzy DNS repair used from FULL auto-diagnose in interactive mode.

    Behaviour:
    - Always try systemd-resolved restart / limited repair first.
    - If DNS still broken, inspect systemd / resolv.conf mode.
    - If stdin is a TTY, STOP and ask user whether to overwrite resolv.conf
      with public DNS. If user says yes, do so; otherwise just log and exit.
    - In non-interactive contexts, never overwrite resolv.conf here.
    """
    log("[INFO] Fuzzy DNS repair...")
    # Step 1: limited repair (no resolv.conf editing)
    repair_dns_core(allow_resolv_conf_edit=False, dry_run=dry_run)
    if dns_resolves():
        log("[INFO] DNS OK after limited DNS repair.")
        return

    mode, detail = detect_resolv_conf_mode()
    status = systemd_resolved_status()

    log("")
    log("DNS still appears broken after limited repair.")
    log(f"systemd-resolved active : {status['active']}")
    log(f"systemd-resolved enabled: {status['enabled']}")
    log(f"/etc/resolv.conf mode   : {mode.value} ({detail})")

    # Non-interactive: do not attempt resolv.conf rewrite here
    if not sys.stdin.isatty():
        log(
            "[INFO] Not running on a TTY; skipping interactive "
            "resolv.conf rewrite.",
        )
        return

    # Interactive: ask the user explicitly
    prompt_lines = [
        "",
        "I can overwrite /etc/resolv.conf with public DNS servers",
        "(1.1.1.1 and 8.8.8.8). This will back up the existing file to",
        "/etc/resolv.conf.bak first.",
        "",
        "Proceed with resolv.conf rewrite? [y/N]: ",
    ]
    answer = input("\n".join(prompt_lines)).strip().lower()
    if answer == "y":
        repair_dns_core(allow_resolv_conf_edit=True, dry_run=dry_run)
    else:
        log("[INFO] User declined fuzzy DNS resolv.conf rewrite.")


def repair_dns_interactive(dry_run: bool) -> None:
    """
    Menu-driven DNS repair (option 6):
    - Always try systemd-resolved restart first.
    - If DNS still broken, ask user for permission before editing resolv.conf.
    """
    log("[INFO] Attempting DNS repair...")
    repair_dns_core(allow_resolv_conf_edit=False, dry_run=dry_run)
    if dns_resolves():
        log("[INFO] DNS looks OK after service restart.")
        return

    answer = input(
        "DNS still appears broken. Overwrite /etc/resolv.conf with "
        "public DNS (1.1.1.1 / 8.8.8.8)? [y/N]: ",
    ).strip().lower()
    if answer == "y":
        repair_dns_core(allow_resolv_conf_edit=True, dry_run=dry_run)
    else:
        log("[INFO] Skipping resolv.conf rewrite at user request.")


def repair_no_internet(dry_run: bool) -> None:
    """
    No ICMP to 8.8.8.8: try restarting the main manager.
    """
    managers = detect_network_managers()

    if managers.get("NetworkManager", False):
        apply_action(
            "Restart NetworkManager",
            ["systemctl", "restart", "NetworkManager"],
            dry_run,
        )
        return

    if managers.get("systemd-networkd", False):
        apply_action(
            "Restart systemd-networkd",
            ["systemctl", "restart", "systemd-networkd"],
            dry_run,
        )
        return

    if managers.get("ifupdown", False):
        apply_action(
            "Restart networking (ifupdown)",
            ["systemctl", "restart", "networking"],
            dry_run,
        )
        return

    log(
        "[INFO] No manager to restart for internet reachability; "
        "check router / ISP / cabling.",
    )


def perform_repairs(
    iface: str,
    diagnosis: Diagnosis,
    dry_run: bool,
    allow_resolv_conf_edit: bool,
) -> None:
    """
    Run repairs according to diagnosis.

    allow_resolv_conf_edit:
        - False in auto mode (never touches resolv.conf).
        - True in FULL interactive mode, where DNS repair is allowed
          but will stop and prompt before rewriting resolv.conf.
    """
    log("")
    log("=== Fuzzy diagnosis ===")
    for susp, score in diagnosis.sorted_scores():
        if score <= 0.0:
            continue
        label = SUSPICION_LABELS[susp]
        log(f"{label:20s}: {score:.2f}")

    log("")
    log("=== Repair phase ===")

    if diagnosis.suspicion_scores.get(Suspicion.INTERFACE_MISSING, 0.0) > 0.5:
        repair_interface_missing(iface)
        return

    managers = detect_network_managers()

    if diagnosis.suspicion_scores.get(Suspicion.LINK_DOWN, 0.0) > 0.4:
        repair_link_down(iface, dry_run)

    if diagnosis.suspicion_scores.get(Suspicion.NO_IPV4, 0.0) > 0.4:
        repair_no_ipv4(iface, managers, dry_run)

    if diagnosis.suspicion_scores.get(Suspicion.NO_ROUTE, 0.0) > 0.4:
        repair_no_route(dry_run)

    if diagnosis.suspicion_scores.get(Suspicion.NO_INTERNET, 0.0) > 0.4:
        repair_no_internet(dry_run)

    if diagnosis.suspicion_scores.get(Suspicion.DNS_BROKEN, 0.0) > 0.4:
        if allow_resolv_conf_edit:
            # Interactive fuzzy DNS repair with confirmation
            repair_dns_fuzzy_with_confirm(dry_run)
        else:
            # Auto / non-interactive: limited DNS repair only
            repair_dns_core(
                allow_resolv_conf_edit=False,
                dry_run=dry_run,
            )


# ---------------------------------------------------------------------------
# Status and menus
# ---------------------------------------------------------------------------

def show_status(iface: str) -> None:
    log("")
    log("=== Interface & connectivity status ===")
    exists = interface_exists(iface)
    link_up = interface_link_up(iface) if exists else False
    ipv4_addrs = interface_ip_addrs(iface, family=4) if exists else []
    ipv6_addrs = interface_ip_addrs(iface, family=6) if exists else []
    has_ip = bool(ipv4_addrs)
    default_route = has_default_route()
    ping_ip_ok = ping_host("8.8.8.8")
    dns_ok = dns_resolves()
    managers = detect_network_managers()

    log(f"Interface:           {iface}")
    log(f"Exists:              {exists}")
    log(f"Link up:             {link_up}")
    log(f"IPv4 addresses:      {', '.join(ipv4_addrs) or 'None'}")
    log(f"IPv6 addresses:      {', '.join(ipv6_addrs) or 'None'}")
    log(f"Has IPv4:            {has_ip}")
    log(f"Default route:       {default_route}")
    log(f"Ping 8.8.8.8:        {ping_ip_ok}")
    log(f"DNS deb.debian.org:  {dns_ok}")
    log("")
    log("Network managers:")
    for name, active in managers.items():
        log(f"  {name:17s}: {'active' if active else 'inactive'}")
    log("")
    log("/etc/resolv.conf (first lines):")
    for line in read_resolv_conf_summary():
        log(f"  {line}")
    log("=======================================")


def show_all_adapters() -> None:
    log("")
    log("=== All adapters & addresses (ip -br addr show) ===")
    for line in list_all_interfaces_detailed():
        log(f"  {line}")
    log("==================================================")


def advanced_systemd_dns_menu(dry_run: bool) -> None:
    while True:
        print("")
        print("------ Advanced systemd / DNS menu ------")
        print("1) Show systemd-resolved & resolv.conf status")
        print("2) Enable & start systemd-resolved")
        print("3) Disable & stop systemd-resolved")
        print("4) Point /etc/resolv.conf → systemd stub")
        print("5) Point /etc/resolv.conf → systemd full resolv.conf")
        print("6) Write manual /etc/resolv.conf (1.1.1.1 / 8.8.8.8)")
        print("7) Back to main menu")
        print("-----------------------------------------")
        choice = input("Select an option [1-7]: ").strip()

        if choice == "1":
            show_systemd_dns_status()
        elif choice == "2":
            set_systemd_resolved_enabled(True, dry_run)
            show_systemd_dns_status()
        elif choice == "3":
            set_systemd_resolved_enabled(False, dry_run)
            show_systemd_dns_status()
        elif choice == "4":
            set_resolv_conf_symlink(
                "/run/systemd/resolve/stub-resolv.conf",
                dry_run,
            )
            show_systemd_dns_status()
        elif choice == "5":
            set_resolv_conf_symlink(
                "/run/systemd/resolve/resolv.conf",
                dry_run,
            )
            show_systemd_dns_status()
        elif choice == "6":
            set_resolv_conf_manual_public(dry_run)
            show_systemd_dns_status()
        elif choice == "7":
            log("[INFO] Leaving advanced systemd/DNS menu.")
            break
        else:
            print("Invalid choice, please select 1-7.")


def interactive_menu(
    iface: str,
    dry_run: bool,
) -> None:
    current_iface = iface

    while True:
        print("")
        print("========== Ethernet repair menu ==========")
        print(f"Current interface: {current_iface}")
        print("")
        print("1) Show interface & connectivity status")
        print("2) Run FULL fuzzy auto-diagnose & repair")
        print("3) Bring link UP on current interface")
        print("4) Obtain IPv4 / renew DHCP on interface")
        print("5) Restart network stack (routing / services)")
        print("6) Attempt DNS repair (may edit resolv.conf)")
        print("7) Change interface")
        print("8) Show ALL adapters & addresses")
        print("9) Advanced systemd / DNS controls")
        print("10) Quit")
        print("==========================================")
        choice = input("Select an option [1-10]: ").strip()

        if choice == "1":
            show_status(current_iface)
        elif choice == "2":
            diag = fuzzy_diagnose(current_iface)
            # In interactive mode, FULL fuzzy repair is allowed to fix DNS,
            # but will stop and ask before rewriting resolv.conf.
            perform_repairs(
                iface=current_iface,
                diagnosis=diag,
                dry_run=dry_run,
                allow_resolv_conf_edit=True,
            )
            show_status(current_iface)
        elif choice == "3":
            repair_link_down(current_iface, dry_run)
            show_status(current_iface)
        elif choice == "4":
            managers = detect_network_managers()
            repair_no_ipv4(current_iface, managers, dry_run)
            show_status(current_iface)
        elif choice == "5":
            repair_no_route(dry_run)
            repair_no_internet(dry_run)
            show_status(current_iface)
        elif choice == "6":
            repair_dns_interactive(dry_run)
            show_status(current_iface)
        elif choice == "7":
            print("")
            print("Available interfaces:")
            names = list_candidate_interfaces()
            for idx, name in enumerate(names, start=1):
                print(f"  {idx}) {name}")
            new_name = input(
                "Enter interface name to use (or blank to keep current): ",
            ).strip()
            if new_name:
                current_iface = new_name
                log(f"[INFO] Switched to interface: {current_iface}")
                show_status(current_iface)
        elif choice == "8":
            show_all_adapters()
        elif choice == "9":
            advanced_systemd_dns_menu(dry_run)
        elif choice == "10" or choice.lower() in {"q", "quit", "exit"}:
            log("[INFO] Exiting menu.")
            break
        else:
            print("Invalid choice, please select 1-10.")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def parse_args(argv: Optional[List[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Interactive Ethernet repair helper.",
    )
    parser.add_argument(
        "-i",
        "--interface",
        default="eth0",
        help="Interface to repair (default: eth0).",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Log actions but do not make changes.",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Verbose debug logging.",
    )
    parser.add_argument(
        "--auto",
        action="store_true",
        help="Non-interactive: one-shot fuzzy diagnose + repair.",
    )
    return parser.parse_args(argv)


def main(argv: Optional[List[str]] = None) -> int:
    args = parse_args(argv)
    setup_logging(args.verbose)

    # Enforce running as root, since commands assume root privileges.
    if hasattr(os, "geteuid") and os.geteuid() != 0:
        print(
            "ERROR: This script must be run as root.\n"
            "       Try: sudo python3 eth_repair_menu.py",
            file=sys.stderr,
        )
        log(
            "[ERROR] Not running as root. "
            "Re-run with: sudo python3 eth_repair_menu.py",
        )
        return 1

    iface = args.interface

    # If default eth0 is missing, try to auto-select a real interface.
    if iface == "eth0" and not interface_exists(iface):
        candidates = list_candidate_interfaces()
        if candidates:
            new_iface = candidates[0]
            log(
                f"[INFO] Interface '{iface}' not found; "
                f"auto-selected '{new_iface}'.",
            )
            iface = new_iface
        else:
            log(
                f"[ERROR] Interface '{iface}' not found and no "
                "usable interfaces detected.",
            )
            return 1
    # If user explicitly chose an interface that does not exist, fail loudly.
    elif not interface_exists(iface):
        candidates = list_candidate_interfaces()
        log(
            f"[ERROR] Interface '{iface}' does not exist. "
            f"Detected interfaces: {candidates}",
        )
        return 1

    log(f"[INFO] Ethernet repair helper starting for interface: {iface}")
    if args.dry_run:
        log("[INFO] Dry-run mode enabled (no changes will be made).")
    log("[INFO] Log file (if writable): /tmp/eth_repair.log")

    if args.auto or not sys.stdin.isatty():
        diag = fuzzy_diagnose(iface)
        # Auto mode never edits resolv.conf without you explicitly asking.
        perform_repairs(
            iface=iface,
            diagnosis=diag,
            dry_run=args.dry_run,
            allow_resolv_conf_edit=False,
        )
        show_status(iface)
        return 0

    try:
        interactive_menu(
            iface=iface,
            dry_run=args.dry_run,
        )
    except KeyboardInterrupt:
        log("[INFO] Exiting menu (Ctrl-C).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
