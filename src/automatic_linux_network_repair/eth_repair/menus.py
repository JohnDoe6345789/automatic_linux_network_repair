"""Interactive menus for Ethernet repair operations."""

from __future__ import annotations

from automatic_linux_network_repair.eth_repair.diagnostics import fuzzy_diagnose
from automatic_linux_network_repair.eth_repair.dns_config import (
    set_resolv_conf_manual_public,
    set_resolv_conf_symlink,
    set_systemd_resolved_enabled,
    show_systemd_dns_status,
)
from automatic_linux_network_repair.eth_repair.logging_utils import log
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


class EthernetRepairMenu:
    """Interactive menus for Ethernet repair operations."""

    def __init__(self, iface: str, dry_run: bool):
        self.current_iface = iface
        self.dry_run = dry_run

    def run(self) -> None:
        while True:
            print("")
            print("========== Ethernet repair menu ==========")
            print(f"Current interface: {self.current_iface}")
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
                log("[INFO] Exiting menu.")
                break
            else:
                print("Invalid choice, please select 1-10.")

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
        print("")
        print("Available interfaces:")
        names = list_candidate_interfaces()
        for idx, name in enumerate(names, start=1):
            print(f"  {idx}) {name}")
        new_name = input(
            "Enter interface name to use (or blank to keep current): ",
        ).strip()
        if new_name:
            self.current_iface = new_name
            log(f"[INFO] Switched to interface: {self.current_iface}")
            show_status(self.current_iface)

    def _advanced_systemd_dns_menu(self) -> None:
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
                log("[INFO] Leaving advanced systemd/DNS menu.")
                break
            else:
                print("Invalid choice, please select 1-7.")
