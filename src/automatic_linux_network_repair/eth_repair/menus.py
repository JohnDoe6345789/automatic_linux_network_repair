"""Interactive menus for Ethernet repair operations."""

from __future__ import annotations

import sys
from typing import Callable, TextIO

from automatic_linux_network_repair.eth_repair.diagnostics import fuzzy_diagnose
from automatic_linux_network_repair.eth_repair.dns_config import (
    set_resolv_conf_manual_public,
    set_resolv_conf_symlink,
    set_systemd_resolved_enabled,
    show_systemd_dns_status,
)
from automatic_linux_network_repair.eth_repair.logging_utils import DEFAULT_LOGGER
from automatic_linux_network_repair.eth_repair.probes import (
    detect_network_managers,
    list_candidate_interfaces,
)
from automatic_linux_network_repair.eth_repair.repairs import (
    EthernetRepairCoordinator,
    repair_dns_interactive,
    repair_link_down,
    repair_no_internet,
    repair_no_ipv4,
    repair_no_route,
)
from automatic_linux_network_repair.eth_repair.status import (
    show_all_adapters,
    show_status,
)


class EthernetMenuSideEffects:
    '''Handle all printing, prompting, and logging for menu interactions.'''

    def __init__(
        self,
        logger=DEFAULT_LOGGER,
        stdout: TextIO | None = None,
        input_func: Callable[[str], str] | None = None,
    ) -> None:
        self.logger = logger
        self.stdout = stdout or sys.stdout
        self._input = input_func or input

    def show_main_menu(self, current_iface: str) -> str:
        print('', file=self.stdout)
        print('========== Ethernet repair menu ==========', file=self.stdout)
        print(f'Current interface: {current_iface}', file=self.stdout)
        print('', file=self.stdout)
        print('1) Show interface & connectivity status', file=self.stdout)
        print('2) Run FULL fuzzy auto-diagnose & repair', file=self.stdout)
        print('3) Bring link UP on current interface', file=self.stdout)
        print('4) Obtain IPv4 / renew DHCP on interface', file=self.stdout)
        print('5) Restart network stack (routing / services)', file=self.stdout)
        print('6) Attempt DNS repair (may edit resolv.conf)', file=self.stdout)
        print('7) Change interface', file=self.stdout)
        print('8) Show ALL adapters & addresses', file=self.stdout)
        print('9) Advanced systemd / DNS controls', file=self.stdout)
        print('10) Quit', file=self.stdout)
        print('==========================================', file=self.stdout)
        return self._input('Select an option [1-10]: ').strip()

    def show_invalid_main_choice(self) -> None:
        print('Invalid choice, please select 1-10.', file=self.stdout)

    def show_interfaces(self, names: list[str]) -> None:
        print('', file=self.stdout)
        print('Available interfaces:', file=self.stdout)
        for idx, name in enumerate(names, start=1):
            print(f'  {idx}) {name}', file=self.stdout)

    def prompt_new_interface(self) -> str:
        return self._input(
            'Enter interface name to use (or blank to keep current): ',
        ).strip()

    def log_switched_interface(self, iface: str) -> None:
        self.logger.log(f'[INFO] Switched to interface: {iface}')

    def log_main_menu_exit(self) -> None:
        self.logger.log('[INFO] Exiting menu.')

    def show_advanced_menu(self) -> str:
        print('', file=self.stdout)
        print('------ Advanced systemd / DNS menu ------', file=self.stdout)
        print('1) Show systemd-resolved & resolv.conf status', file=self.stdout)
        print('2) Enable & start systemd-resolved', file=self.stdout)
        print('3) Disable & stop systemd-resolved', file=self.stdout)
        print('4) Point /etc/resolv.conf → systemd stub', file=self.stdout)
        print('5) Point /etc/resolv.conf → systemd full resolv.conf', file=self.stdout)
        print('6) Write manual /etc/resolv.conf (1.1.1.1 / 8.8.8.8)', file=self.stdout)
        print('7) Back to main menu', file=self.stdout)
        print('-----------------------------------------', file=self.stdout)
        return self._input('Select an option [1-7]: ').strip()

    def show_invalid_advanced_choice(self) -> None:
        print('Invalid choice, please select 1-7.', file=self.stdout)

    def log_exit_advanced(self) -> None:
        self.logger.log('[INFO] Leaving advanced systemd/DNS menu.')


class EthernetRepairMenu:
    """Interactive menus for Ethernet repair operations."""

    def __init__(
        self,
        iface: str,
        dry_run: bool,
        side_effects: EthernetMenuSideEffects | None = None,
    ):
        self.current_iface = iface
        self.dry_run = dry_run
        self.side_effects = side_effects or EthernetMenuSideEffects()

    def run(self) -> None:
        while True:
            choice = self.side_effects.show_main_menu(self.current_iface)

            if choice == "1":
                show_status(self.current_iface)
            elif choice == "2":
                self._run_full_repair()
            elif choice == "3":
                repair_link_down(self.current_iface, self.dry_run)
                show_status(self.current_iface)
            elif choice == "4":
                managers = detect_network_managers()
                repair_no_ipv4(self.current_iface, managers, self.dry_run)
                show_status(self.current_iface)
            elif choice == "5":
                repair_no_route(self.dry_run)
                repair_no_internet(self.dry_run)
                show_status(self.current_iface)
            elif choice == "6":
                repair_dns_interactive(self.dry_run)
                show_status(self.current_iface)
            elif choice == "7":
                self._choose_interface()
            elif choice == "8":
                show_all_adapters()
            elif choice == "9":
                self._advanced_systemd_dns_menu()
            elif choice == "10" or choice.lower() in {"q", "quit", "exit"}:
                self.side_effects.log_main_menu_exit()
                break
            else:
                self.side_effects.show_invalid_main_choice()

    def _run_full_repair(self) -> None:
        diag = fuzzy_diagnose(self.current_iface)
        coordinator = EthernetRepairCoordinator(
            iface=self.current_iface,
            dry_run=self.dry_run,
            allow_resolv_conf_edit=True,
        )
        coordinator.perform_repairs(diagnosis=diag)
        show_status(self.current_iface)

    def _choose_interface(self) -> None:
        names = list_candidate_interfaces()
        self.side_effects.show_interfaces(names)
        new_name = self.side_effects.prompt_new_interface()
        if new_name:
            self.current_iface = new_name
            self.side_effects.log_switched_interface(self.current_iface)
            show_status(self.current_iface)

    def _advanced_systemd_dns_menu(self) -> None:
        while True:
            choice = self.side_effects.show_advanced_menu()

            if choice == "1":
                show_systemd_dns_status()
            elif choice == "2":
                set_systemd_resolved_enabled(True, self.dry_run)
                show_systemd_dns_status()
            elif choice == "3":
                set_systemd_resolved_enabled(False, self.dry_run)
                show_systemd_dns_status()
            elif choice == "4":
                set_resolv_conf_symlink(
                    "/run/systemd/resolve/stub-resolv.conf",
                    self.dry_run,
                )
                show_systemd_dns_status()
            elif choice == "5":
                set_resolv_conf_symlink(
                    "/run/systemd/resolve/resolv.conf",
                    self.dry_run,
                )
                show_systemd_dns_status()
            elif choice == "6":
                set_resolv_conf_manual_public(self.dry_run)
                show_systemd_dns_status()
            elif choice == "7":
                self.side_effects.log_exit_advanced()
                break
            else:
                self.side_effects.show_invalid_advanced_choice()
