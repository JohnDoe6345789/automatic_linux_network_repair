"""CLI entry point for the Ethernet repair helper."""

from __future__ import annotations

import os
import sys

from automatic_linux_network_repair.eth_repair.diagnostics import fuzzy_diagnose
from automatic_linux_network_repair.eth_repair.logging_utils import log, setup_logging
from automatic_linux_network_repair.eth_repair.menus import interactive_menu
from automatic_linux_network_repair.eth_repair.probes import (
    interface_exists,
    list_candidate_interfaces,
)
from automatic_linux_network_repair.eth_repair.repairs import perform_repairs
from automatic_linux_network_repair.eth_repair.status import show_status


def main(
    interface: str = "eth0",
    dry_run: bool = False,
    verbose: bool = False,
    auto: bool = False,
) -> int:
    setup_logging(verbose)

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

    iface = interface

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
    elif not interface_exists(iface):
        candidates = list_candidate_interfaces()
        log(
            f"[ERROR] Interface '{iface}' does not exist. "
            f"Detected interfaces: {candidates}",
        )
        return 1

    log(f"[INFO] Ethernet repair helper starting for interface: {iface}")
    if dry_run:
        log("[INFO] Dry-run mode enabled (no changes will be made).")
    log("[INFO] Log file (if writable): /tmp/eth_repair.log")

    if auto or not sys.stdin.isatty():
        diag = fuzzy_diagnose(iface)
        perform_repairs(
            iface=iface,
            diagnosis=diag,
            dry_run=dry_run,
            allow_resolv_conf_edit=False,
        )
        show_status(iface)
        return 0

    try:
        interactive_menu(
            iface=iface,
            dry_run=dry_run,
        )
    except KeyboardInterrupt:
        log("[INFO] Exiting menu (Ctrl-C).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
