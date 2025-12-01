"""Logging helpers for the Ethernet repair tool."""

from __future__ import annotations

import logging


class LoggingManager:
    """Manage Ethernet repair logging configuration and messages."""

    def __init__(self, logger_name: str = "eth_repair") -> None:
        self.logger = logging.getLogger(logger_name)
        self.logger.propagate = False

    def setup(self, verbose: bool) -> None:
        """Configure logging to console and /tmp/eth_repair.log."""
        level = logging.DEBUG if verbose else logging.INFO

        formatter = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s")

        handlers: list[logging.Handler] = []
        console = logging.StreamHandler()
        console.setFormatter(formatter)
        handlers.append(console)

        try:
            file_handler = logging.FileHandler(
                "/tmp/eth_repair.log",
                mode="a",
                encoding="utf-8",
            )
            file_handler.setFormatter(formatter)
            handlers.append(file_handler)
        except Exception:
            # If we cannot open the log file, continue with console-only logging.
            pass

        self.logger.handlers.clear()
        for handler in handlers:
            self.logger.addHandler(handler)
        self.logger.setLevel(level)

    def log(self, msg: str) -> None:
        """Log an informational message."""
        self.logger.info(msg)

    def debug(self, msg: str) -> None:
        """Log a debug message."""
        self.logger.debug(msg)


DEFAULT_LOGGER = LoggingManager()


# Compatibility wrappers for existing procedural callers.
def setup_logging(verbose: bool) -> None:
    DEFAULT_LOGGER.setup(verbose)


def log(msg: str) -> None:
    DEFAULT_LOGGER.log(msg)


def debug(msg: str) -> None:
    DEFAULT_LOGGER.debug(msg)
