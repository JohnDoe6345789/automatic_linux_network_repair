#!/usr/bin/env python3
"""Compatibility wrapper for the Ethernet repair CLI."""

from automatic_linux_network_repair.eth_repair.cli import main


if __name__ == "__main__":
    raise SystemExit(main())
