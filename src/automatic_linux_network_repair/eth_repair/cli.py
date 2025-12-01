"""CLI entry point for the Ethernet repair helper."""

from __future__ import annotations

import os
import sys

from automatic_linux_network_repair.eth_repair.diagnostics import fuzzy_diagnose
from automatic_linux_network_repair.eth_repair.logging_utils import log, setup_logging
from automatic_linux_network_repair.eth_repair.menus import EthernetRepairMenu
from automatic_linux_network_repair.eth_repair.probes import (
    interface_exists,
    list_candidate_interfaces,
)
from automatic_linux_network_repair.eth_repair.repairs import EthernetRepairCoordinator
from automatic_linux_network_repair.eth_repair.status import show_status


class EthernetRepairApp:
    """Object-oriented wrapper for running the Ethernet repair helper."""

    def __init__(self, interface: str, dry_run: bool, verbose: bool, auto: bool):
        self.interface = interface
        self.dry_run = dry_run
        self.verbose = verbose
        self.auto = auto

    def run(self) -> int:
        setup_logging(self.verbose)
        if not self._ensure_root():
            return 1

        iface = self._choose_interface()
        if iface is None:
            return 1

        self.interface = iface
        log(f"[INFO] Ethernet repair helper starting for interface: {self.interface}")
        if self.dry_run:
            log("[INFO] Dry-run mode enabled (no changes will be made).")
        log("[INFO] Log file (if writable): /tmp/eth_repair.log")

        if self.auto or not sys.stdin.isatty():
            self._run_auto_repair()
            return 0

        try:
            EthernetRepairMenu(iface=self.interface, dry_run=self.dry_run).run()
        except KeyboardInterrupt:
            log("[INFO] Exiting menu (Ctrl-C).")
        return 0

    def _ensure_root(self) -> bool:
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
            return False
        return True

    def _choose_interface(self) -> str | None:
        iface = self.interface
        if iface == "eth0" and not interface_exists(iface):
            candidates = list_candidate_interfaces()
            if candidates:
                new_iface = candidates[0]
                log(
                    f"[INFO] Interface '{iface}' not found; "
                    f"auto-selected '{new_iface}'.",
                )
                return new_iface

            log(
                f"[ERROR] Interface '{iface}' not found and no "
                "usable interfaces detected.",
            )
            return None

        if not interface_exists(iface):
            candidates = list_candidate_interfaces()
            log(
                f"[ERROR] Interface '{iface}' does not exist. "
                f"Detected interfaces: {candidates}",
            )
            return None

        return iface

    def _run_auto_repair(self) -> None:
        diag = fuzzy_diagnose(self.interface)
        EthernetRepairCoordinator(
            iface=self.interface,
            dry_run=self.dry_run,
            allow_resolv_conf_edit=False,
        ).perform_repairs(diagnosis=diag)
        show_status(self.interface)


def main(
    interface: str = "eth0",
    dry_run: bool = False,
    verbose: bool = False,
    auto: bool = False,
) -> int:
    app = EthernetRepairApp(
        interface=interface,
        dry_run=dry_run,
        verbose=verbose,
        auto=auto,
    )
    return app.run()


if __name__ == "__main__":
    raise SystemExit(main())
