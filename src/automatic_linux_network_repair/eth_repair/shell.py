"""Shell helpers used throughout the Ethernet repair tool."""

from __future__ import annotations

import shlex
import subprocess
from typing import List

from automatic_linux_network_repair.eth_repair.logging_utils import debug
from automatic_linux_network_repair.eth_repair.types import CommandResult


def cmd_str(cmd: List[str]) -> str:
    return " ".join(shlex.quote(part) for part in cmd)


def run_cmd(
    cmd: List[str],
    timeout: int = 5,
) -> CommandResult:
    """Run command and capture stdout/stderr."""
    debug(f"Running: {cmd_str(cmd)}")
    try:
        proc = subprocess.run(
            cmd,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=timeout,
            text=True,
        )
    except Exception as exc:  # noqa: BLE001 - broad to log spawn issues
        debug(f"Command failed to start: {exc}")
        return CommandResult(
            cmd=cmd,
            returncode=255,
            stdout="",
            stderr=str(exc),
        )

    debug(
        f"Command rc={proc.returncode} stdout={proc.stdout!r} "
        f"stderr={proc.stderr!r}",
    )
    return CommandResult(
        cmd=cmd,
        returncode=proc.returncode,
        stdout=proc.stdout,
        stderr=proc.stderr,
    )
