"""Action helpers for running network repair commands."""

from __future__ import annotations

from typing import List

from automatic_linux_network_repair.eth_repair.logging_utils import log
from automatic_linux_network_repair.eth_repair.shell import cmd_str, run_cmd


def apply_action(desc: str, cmd: List[str], dry_run: bool) -> bool:
    log(f"[ACTION] {desc}")
    log(f"         {cmd_str(cmd)}")
    if dry_run:
        return True
    res = run_cmd(cmd, timeout=20)
    if res.returncode != 0:
        log(
            f"[WARN] Action failed (rc={res.returncode}): {cmd_str(cmd)} "
            f"stderr={res.stderr.strip()}",
        )
        return False
    return True
