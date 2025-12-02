"""Repair routines used by the interactive Ethernet helper."""

from __future__ import annotations

import sys

from automatic_linux_network_repair.eth_repair.actions import apply_action
from automatic_linux_network_repair.eth_repair.dns_config import (
    backup_resolv_conf,
    detect_resolv_conf_mode,
    set_resolv_conf_manual_public,
    systemd_resolved_status,
)
from automatic_linux_network_repair.eth_repair.logging_utils import DEFAULT_LOGGER
from automatic_linux_network_repair.eth_repair.probes import (
    detect_active_vpn_services,
    detect_network_managers,
    dns_resolves,
    interface_has_ipv4,
    tailscale_status,
)
from automatic_linux_network_repair.eth_repair.types import (
    SUSPICION_LABELS,
    Diagnosis,
    Suspicion,
)


class DnsRepairSideEffects:
    """Encapsulate DNS repair prompting and logging side effects."""

    def __init__(
        self,
        logger=DEFAULT_LOGGER,
        stdin=None,
        input_func=None,
    ) -> None:
        self.logger = logger
        self.stdin = stdin or sys.stdin
        self._input = input_func or input

    def log_fuzzy_intro(self) -> None:
        self.logger.log("[INFO] Fuzzy DNS repair...")

    def log_dns_ok_after_limited(self) -> None:
        self.logger.log("[INFO] DNS OK after limited DNS repair.")

    def log_dns_broken_details(self, status: dict, mode, detail: str) -> None:
        self.logger.log("")
        self.logger.log("DNS still appears broken after limited repair.")
        self.logger.log(f"systemd-resolved active : {status['active']}")
        self.logger.log(f"systemd-resolved enabled: {status['enabled']}")
        self.logger.log(f"/etc/resolv.conf mode   : {mode.value} ({detail})")

    def is_tty(self) -> bool:
        return self.stdin.isatty()

    def confirm_public_dns_overwrite(self, prompt_lines: list[str] | str) -> bool:
        prompt = "\n".join(prompt_lines) if isinstance(prompt_lines, list) else prompt_lines
        answer = self._input(prompt).strip().lower()
        return answer == "y"

    def log_user_declined_fuzzy(self) -> None:
        self.logger.log("[INFO] User declined fuzzy DNS resolv.conf rewrite.")

    def log_non_tty_skip(self, context: str) -> None:
        self.logger.log(f"[INFO] Not running on a TTY; skipping {context}")

    def log_menu_intro(self, status: dict) -> None:
        self.logger.log("[INFO] DNS repair menu...")
        self.logger.log(f"systemd-resolved active : {status['active']}")
        self.logger.log(f"systemd-resolved enabled: {status['enabled']}")

    def log_resolv_conf_mode(self, mode, detail: str) -> None:
        self.logger.log(f"/etc/resolv.conf mode: {mode.value} ({detail})")

    def log_user_declined_manual(self) -> None:
        self.logger.log("[INFO] User declined manual resolv.conf rewrite.")


def repair_interface_missing(iface: str) -> None:
    DEFAULT_LOGGER.log(
        "[INFO] Interface does not exist. This is usually a driver, "
        "hardware or VM configuration issue.",
    )
    DEFAULT_LOGGER.log("[HINT] Check dmesg, lspci/lsusb, or hypervisor NIC settings.")


def repair_link_down(iface: str, dry_run: bool) -> None:
    apply_action(
        f"Bring {iface} link UP via ip",
        ["ip", "link", "set", iface, "up"],
        dry_run,
    )


def repair_no_ipv4(
    iface: str,
    managers: dict[str, bool],
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
            DEFAULT_LOGGER.log("[OK] IPv4 obtained after systemd-networkd restart.")
            return
        if not dry_run:
            DEFAULT_LOGGER.log(
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
            DEFAULT_LOGGER.log("[OK] IPv4 obtained after ifup.")
            return

    apply_action(
        f"Run dhclient on {iface}",
        ["dhclient", "-v", iface],
        dry_run,
    )
    if not dry_run and interface_has_ipv4(iface):
        DEFAULT_LOGGER.log("[OK] IPv4 obtained after dhclient.")
    elif not dry_run:
        DEFAULT_LOGGER.log(
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

    DEFAULT_LOGGER.log(
        "[INFO] No known network manager to fix default route; "
        "you may need to add it manually.",
    )


def repair_no_internet(dry_run: bool) -> None:
    """Attempt general connectivity recovery when ICMP fails."""

    DEFAULT_LOGGER.log("[INFO] Attempting general internet connectivity repair.")
    managers = detect_network_managers()
    tailscale = tailscale_status()
    active_vpn_services = detect_active_vpn_services()

    if managers.get("NetworkManager", False):
        apply_action(
            "Restart NetworkManager", ["systemctl", "restart", "NetworkManager"], dry_run
        )
        return

    if managers.get("systemd-networkd", False):
        apply_action(
            "Restart systemd-networkd", ["systemctl", "restart", "systemd-networkd"], dry_run
        )
        return

    if managers.get("ifupdown", False):
        apply_action(
            "Restart networking (ifupdown)", ["systemctl", "restart", "networking"], dry_run
        )
        return

    if tailscale["installed"]:
        if tailscale["active"]:
            DEFAULT_LOGGER.log(
                "[INFO] Tailscale detected; check `tailscale status` or restart "
                "tailscaled if overlay connectivity should be available."
            )
        else:
            DEFAULT_LOGGER.log(
                "[INFO] Tailscale installed but inactive; run `sudo tailscale up` "
                "if VPN access is expected."
            )

    if active_vpn_services:
        DEFAULT_LOGGER.log(
            "[INFO] Active VPN services detected; disconnect or stop them "
            "if they might be blocking internet connectivity:"
        )
        for unit in active_vpn_services:
            DEFAULT_LOGGER.log(f"  - {unit}")

    DEFAULT_LOGGER.log(
        "[INFO] No known network manager detected; perform manual investigation (ping, firewall, modem)."
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
            DEFAULT_LOGGER.log("[OK] DNS fixed after systemd-resolved restart.")
            return

    if not allow_resolv_conf_edit:
        DEFAULT_LOGGER.log(
            "[INFO] DNS appears broken; resolv.conf editing is disabled in "
            "this mode. Use menu option 6 or the advanced systemd/DNS menu.",
        )
        return

    backup_resolv_conf(dry_run)
    set_resolv_conf_manual_public(dry_run)

    if not dry_run and dns_resolves():
        DEFAULT_LOGGER.log("[OK] DNS working after resolv.conf rewrite.")
    elif not dry_run:
        DEFAULT_LOGGER.log(
            "[WARN] DNS still failing after resolv.conf rewrite. "
            "Check firewall / router.",
        )


def repair_dns_fuzzy_with_confirm(
    dry_run: bool, side_effects: DnsRepairSideEffects | None = None
) -> None:
    """
    Fuzzy DNS repair used from FULL auto-diagnose in interactive mode.

    Behaviour:
    - Always try systemd-resolved restart / limited repair first.
    - If DNS still broken, inspect systemd / resolv.conf mode.
    - If stdin is a TTY, STOP and ask user whether to overwrite resolv.conf
      with public DNS. If user says yes, do so; otherwise just log and exit.
    - In non-interactive contexts, never overwrite resolv.conf here.
    """
    side_effects = side_effects or DnsRepairSideEffects()

    side_effects.log_fuzzy_intro()
    repair_dns_core(allow_resolv_conf_edit=False, dry_run=dry_run)
    if dns_resolves():
        side_effects.log_dns_ok_after_limited()
        return

    mode, detail = detect_resolv_conf_mode()
    status = systemd_resolved_status()

    side_effects.log_dns_broken_details(status, mode, detail)

    if not side_effects.is_tty():
        side_effects.log_non_tty_skip("interactive resolv.conf rewrite.")
        return

    prompt_lines = [
        "",
        "I can overwrite /etc/resolv.conf with public DNS servers",
        "(1.1.1.1 and 8.8.8.8). This will back up the existing file to",
        "/etc/resolv.conf.bak first.",
        "",
        "Proceed with resolv.conf rewrite? [y/N]: ",
    ]
    if side_effects.confirm_public_dns_overwrite(prompt_lines):
        repair_dns_core(allow_resolv_conf_edit=True, dry_run=dry_run)
    else:
        side_effects.log_user_declined_fuzzy()


def repair_dns_interactive(
    dry_run: bool, side_effects: DnsRepairSideEffects | None = None
) -> None:
    """
    Menu-driven DNS repair (option 6):
    - Always try systemd-resolved restart first.
    - If DNS still broken, ask user for permission before editing resolv.conf.
    - If user agrees, create manual resolv.conf with public DNS.
    """
    side_effects = side_effects or DnsRepairSideEffects()

    status = systemd_resolved_status()
    side_effects.log_menu_intro(status)

    apply_action(
        "Restart systemd-resolved",
        ["systemctl", "restart", "systemd-resolved"],
        dry_run,
    )
    if not dry_run and dns_resolves():
        DEFAULT_LOGGER.log("[OK] DNS fixed after systemd-resolved restart.")
        return

    mode, detail = detect_resolv_conf_mode()
    side_effects.log_resolv_conf_mode(mode, detail)

    if not side_effects.is_tty():
        side_effects.log_non_tty_skip("manual resolv.conf rewrite.")
        return

    prompt = "Overwrite /etc/resolv.conf with public DNS (1.1.1.1 / 8.8.8.8)? [y/N]: "
    if not side_effects.confirm_public_dns_overwrite(prompt):
        side_effects.log_user_declined_manual()
        return

    set_resolv_conf_manual_public(dry_run)
    if not dry_run and dns_resolves():
        DEFAULT_LOGGER.log("[OK] DNS working after resolv.conf rewrite.")
    elif not dry_run:
        DEFAULT_LOGGER.log(
            "[WARN] DNS still failing after resolv.conf rewrite. "
            "Check firewall / router.",
        )


class EthernetRepairCoordinator:
    """Coordinate repair strategies for a given interface and mode."""

    def __init__(self, iface: str, dry_run: bool, allow_resolv_conf_edit: bool):
        self.iface = iface
        self.dry_run = dry_run
        self.allow_resolv_conf_edit = allow_resolv_conf_edit

    def perform_repairs(self, diagnosis: Diagnosis) -> None:
        """Apply the most appropriate fix for a diagnosis."""
        DEFAULT_LOGGER.log("[INFO] Performing auto-repair...")

        ordered = diagnosis.sorted_scores()
        DEFAULT_LOGGER.log("Suspicion scores:")
        for suspicion, score in ordered:
            label = SUSPICION_LABELS[suspicion]
            DEFAULT_LOGGER.log(f"  {label}: {score:.2f}")

        suspicion = diagnosis.top_suspicion
        if suspicion == Suspicion.INTERFACE_MISSING:
            repair_interface_missing(self.iface)
        elif suspicion == Suspicion.LINK_DOWN:
            repair_link_down(self.iface, dry_run=self.dry_run)
        elif suspicion == Suspicion.NO_IPV4:
            managers = detect_network_managers()
            repair_no_ipv4(self.iface, managers=managers, dry_run=self.dry_run)
        elif suspicion == Suspicion.NO_ROUTE:
            repair_no_route(dry_run=self.dry_run)
        elif suspicion == Suspicion.NO_INTERNET:
            DEFAULT_LOGGER.log(
                "[INFO] Unable to ping internet; if DHCP is OK, check "
                "upstream gateway / firewall.",
            )
        elif suspicion == Suspicion.DNS_BROKEN:
            self._repair_dns()

        DEFAULT_LOGGER.log("[INFO] Auto-repair complete.")

    def _repair_dns(self) -> None:
        if self.allow_resolv_conf_edit:
            repair_dns_fuzzy_with_confirm(dry_run=self.dry_run)
            return

        repair_dns_core(
            allow_resolv_conf_edit=False,
            dry_run=self.dry_run,
        )
