"""CLI entry point for the Ethernet repair helper."""

from __future__ import annotations

import os
import sys
from typing import TextIO

from automatic_linux_network_repair.eth_repair.diagnostics import fuzzy_diagnose
from automatic_linux_network_repair.eth_repair.logging_utils import (
    DEFAULT_LOGGER,
    LoggingManager,
)
from automatic_linux_network_repair.eth_repair.menus import EthernetRepairMenu
from automatic_linux_network_repair.eth_repair.probes import (
    interface_exists,
    list_candidate_interfaces,
)
from automatic_linux_network_repair.eth_repair.repairs import EthernetRepairCoordinator
from automatic_linux_network_repair.eth_repair.status import show_status


class EthernetRepairSideEffects:
    """Handle logging and other side effects for the repair app."""

    def __init__(
        self,
        logger: LoggingManager = DEFAULT_LOGGER,
        stdout: TextIO | None = None,
        stderr: TextIO | None = None,
    ) -> None:
        self.logger = logger
        self.stdout = stdout or sys.stdout
        self.stderr = stderr or sys.stderr

    def setup_logging(self, verbose: bool) -> None:
        self.logger.setup(verbose)

    def warn_not_root(self) -> None:
        print(
            "ERROR: This script must be run as root.\n"
            "       Try: sudo python3 eth_repair_menu.py",
            file=self.stderr,
        )
        self.logger.log(
            "[ERROR] Not running as root. Re-run with: sudo python3 eth_repair_menu.py",
        )

    def log_start(self, interface: str) -> None:
        self.logger.log(
            f"[INFO] Ethernet repair helper starting for interface: {interface}"
        )

    def log_dry_run(self) -> None:
        self.logger.log("[INFO] Dry-run mode enabled (no changes will be made).")

    def log_logfile_hint(self) -> None:
        self.logger.log("[INFO] Log file (if writable): /tmp/eth_repair.log")

    def log_auto_selected_interface(self, original: str, new_iface: str) -> None:
        self.logger.log(
            f"[INFO] Interface '{original}' not found; auto-selected '{new_iface}'.",
        )

    def log_missing_default_interface(self, iface: str) -> None:
        self.logger.log(
            f"[ERROR] Interface '{iface}' not found and no usable interfaces detected.",
        )

    def log_invalid_interface(self, iface: str, candidates: list[str]) -> None:
        self.logger.log(
            f"[ERROR] Interface '{iface}' does not exist. Detected interfaces: {candidates}",
        )

    def log_menu_exit(self) -> None:
        self.logger.log("[INFO] Exiting menu (Ctrl-C).")


class EthernetRepairApp:
    """Object-oriented wrapper for running the Ethernet repair helper."""

    def __init__(
        self,
        interface: str,
        dry_run: bool,
        verbose: bool,
        auto: bool,
        side_effects: EthernetRepairSideEffects | None = None,
    ):
        self.interface = interface
        self.dry_run = dry_run
        self.verbose = verbose
        self.auto = auto
        self.side_effects = side_effects or EthernetRepairSideEffects()

    def run(self) -> int:
        self.side_effects.setup_logging(self.verbose)
        if not self._ensure_root():
            return 1

        iface = self._choose_interface()
        if iface is None:
            return 1

        self.interface = iface
        self._log_startup()

        if self.auto or not sys.stdin.isatty():
            self._run_auto_repair()
            return 0

        try:
            EthernetRepairMenu(iface=self.interface, dry_run=self.dry_run).run()
        except KeyboardInterrupt:
            self.side_effects.log_menu_exit()
        return 0

    def _ensure_root(self) -> bool:
        if hasattr(os, "geteuid") and os.geteuid() != 0:
            self.side_effects.warn_not_root()
            return False
        return True

    def _choose_interface(self) -> str | None:
        iface = self.interface
        if iface == "eth0" and not interface_exists(iface):
            candidates = list_candidate_interfaces()
            if candidates:
                new_iface = candidates[0]
                self.side_effects.log_auto_selected_interface(iface, new_iface)
                return new_iface

            self.side_effects.log_missing_default_interface(iface)
            return None

        if not interface_exists(iface):
            candidates = list_candidate_interfaces()
            self.side_effects.log_invalid_interface(iface, candidates)
            return None

        return iface

    def _log_startup(self) -> None:
        self.side_effects.log_start(self.interface)
        if self.dry_run:
            self.side_effects.log_dry_run()
        self.side_effects.log_logfile_hint()

    def _run_auto_repair(self) -> None:
        diag = fuzzy_diagnose(self.interface)
        EthernetRepairCoordinator(
            iface=self.interface,
            dry_run=self.dry_run,
            allow_resolv_conf_edit=False,
        ).perform_repairs(diagnosis=diag)
        show_status(self.interface)


class EthernetRepairRunner:
    """Facade for constructing and executing the repair application."""

    def __init__(self) -> None:
        self._app_class = EthernetRepairApp

    def run(
        self,
        interface: str = "eth0",
        dry_run: bool = False,
        verbose: bool = False,
        auto: bool = False,
    ) -> int:
        app = self._app_class(
            interface=interface,
            dry_run=dry_run,
            verbose=verbose,
            auto=auto,
        )
        return app.run()


DEFAULT_RUNNER = EthernetRepairRunner()


if __name__ == "__main__":
    raise SystemExit(DEFAULT_RUNNER.run())
