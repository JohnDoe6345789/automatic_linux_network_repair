"""Logging helpers for the Ethernet repair tool."""

from __future__ import annotations

import logging

LOGGER = logging.getLogger("eth_repair")


def setup_logging(verbose: bool) -> None:
    """Configure logging to console and /tmp/eth_repair.log."""
    level = logging.DEBUG if verbose else logging.INFO

    handlers: list[logging.Handler] = []
    console = logging.StreamHandler()
    handlers.append(console)

    try:
        file_handler = logging.FileHandler(
            "/tmp/eth_repair.log",
            mode="a",
            encoding="utf-8",
        )
        handlers.append(file_handler)
    except Exception:
        # If we cannot open the log file, continue with console-only logging.
        pass

    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(message)s",
        handlers=handlers,
    )


def log(msg: str) -> None:
    LOGGER.info(msg)


def debug(msg: str) -> None:
    LOGGER.debug(msg)
