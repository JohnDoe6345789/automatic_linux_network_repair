"""Helpers for systemd-resolved and resolv.conf handling."""

from __future__ import annotations

import os

from automatic_linux_network_repair.eth_repair.actions import apply_action
from automatic_linux_network_repair.eth_repair.logging_utils import DEFAULT_LOGGER
from automatic_linux_network_repair.eth_repair.probes import read_resolv_conf_summary
from automatic_linux_network_repair.eth_repair.shell import DEFAULT_SHELL
from automatic_linux_network_repair.eth_repair.types import ResolvConfMode


def systemd_resolved_status() -> dict[str, bool | None]:
    """Return dict with keys: active (bool), enabled (bool or None if unknown)."""
    active_res = DEFAULT_SHELL.run_cmd(["systemctl", "is-active", "systemd-resolved"])
    enabled_res = DEFAULT_SHELL.run_cmd(["systemctl", "is-enabled", "systemd-resolved"])

    active = active_res.returncode == 0
    enabled: bool | None
    if enabled_res.returncode == 0:
        enabled = True
    elif enabled_res.returncode == 1:
        enabled = False
    else:
        enabled = None

    return {"active": active, "enabled": enabled}


def detect_resolv_conf_mode() -> tuple[ResolvConfMode, str]:
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

    DEFAULT_LOGGER.log("")
    DEFAULT_LOGGER.log("=== systemd / DNS status ===")
    DEFAULT_LOGGER.log(f"systemd-resolved active : {status['active']}")
    DEFAULT_LOGGER.log(f"systemd-resolved enabled: {status['enabled']}")
    DEFAULT_LOGGER.log(f"/etc/resolv.conf mode   : {mode.value} ({detail})")
    DEFAULT_LOGGER.log("")
    DEFAULT_LOGGER.log("/etc/resolv.conf (first lines):")
    for line in read_resolv_conf_summary():
        DEFAULT_LOGGER.log(f"  {line}")
    DEFAULT_LOGGER.log("=======================================")
