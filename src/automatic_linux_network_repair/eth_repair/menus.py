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
    perform_repairs,
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
