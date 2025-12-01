"""Repair routines used by the interactive Ethernet helper."""

from __future__ import annotations

from typing import Dict

from automatic_linux_network_repair.eth_repair.actions import apply_action
from automatic_linux_network_repair.eth_repair.dns_config import (
    backup_resolv_conf,
    detect_resolv_conf_mode,
    set_resolv_conf_manual_public,
    systemd_resolved_status,
)
from automatic_linux_network_repair.eth_repair.logging_utils import log
from automatic_linux_network_repair.eth_repair.probes import (
    detect_network_managers,
    dns_resolves,
    interface_has_ipv4,
)
from automatic_linux_network_repair.eth_repair.types import (
    Diagnosis,
    SUSPICION_LABELS,
    Suspicion,
)


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

    import sys

    if not sys.stdin.isatty():
        log(
            "[INFO] Not running on a TTY; skipping interactive "
            "resolv.conf rewrite.",
        )
        return

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
    """Run repairs according to diagnosis."""
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
            repair_dns_fuzzy_with_confirm(dry_run)
        else:
            repair_dns_core(
                allow_resolv_conf_edit=False,
                dry_run=dry_run,
            )
