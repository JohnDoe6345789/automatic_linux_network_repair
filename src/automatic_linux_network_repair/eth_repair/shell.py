"""Shell helpers used throughout the Ethernet repair tool."""

from __future__ import annotations

import shlex
import subprocess

from automatic_linux_network_repair.eth_repair.logging_utils import (
    DEFAULT_LOGGER,
    LoggingManager,
)
from automatic_linux_network_repair.eth_repair.types import CommandResult


class ShellRunner:
    """Execute shell commands with consistent logging."""

    def __init__(self, *, logger: LoggingManager = DEFAULT_LOGGER) -> None:
        self.logger = logger

    def cmd_str(self, cmd: list[str]) -> str:
        """Return a shell-escaped string for display."""
        return " ".join(shlex.quote(part) for part in cmd)

    def run_cmd(
        self,
        cmd: list[str],
        timeout: int = 5,
    ) -> CommandResult:
        """Run command and capture stdout/stderr."""
        self.logger.debug(f"Running: {self.cmd_str(cmd)}")
        try:
            proc = subprocess.run(
                cmd,
                stdin=subprocess.DEVNULL,
                capture_output=True,
                timeout=timeout,
                text=True,
            )
        except Exception as exc:  # noqa: BLE001 - broad to log spawn issues
            self.logger.debug(f"Command failed to start: {exc}")
            return CommandResult(
                cmd=cmd,
                returncode=255,
                stdout="",
                stderr=str(exc),
            )

        self.logger.debug(
            f"Command rc={proc.returncode} stdout={proc.stdout!r} stderr={proc.stderr!r}",
        )
        return CommandResult(
            cmd=cmd,
            returncode=proc.returncode,
            stdout=proc.stdout,
            stderr=proc.stderr,
        )


DEFAULT_SHELL = ShellRunner()
