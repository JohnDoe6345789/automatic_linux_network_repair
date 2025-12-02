"""Action helpers for running network repair commands."""

from __future__ import annotations

from automatic_linux_network_repair.eth_repair.logging_utils import DEFAULT_LOGGER
from automatic_linux_network_repair.eth_repair.shell import DEFAULT_SHELL


def apply_action(desc: str, cmd: list[str], dry_run: bool) -> bool:
    DEFAULT_LOGGER.log(f"[ACTION] {desc}")
    DEFAULT_LOGGER.log(f"         {DEFAULT_SHELL.cmd_str(cmd)}")
    if dry_run:
        return True
    res = DEFAULT_SHELL.run_cmd(cmd, timeout=20)
    if res.returncode != 0:
        DEFAULT_LOGGER.log(
            f"[WARN] Action failed (rc={res.returncode}): {DEFAULT_SHELL.cmd_str(cmd)} stderr={res.stderr.strip()}",
        )
        return False
    return True
