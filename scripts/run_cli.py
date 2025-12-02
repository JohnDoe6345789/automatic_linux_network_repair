#!/usr/bin/env python3
"""Launcher for the automatic_linux_network_repair Typer CLI.

This helper adds the local ``src`` directory to ``sys.path`` so the
command-line interface can be exercised from a fresh checkout without
installing the package. All arguments are forwarded to the underlying
Typer application.
"""

from __future__ import annotations

import sys
from pathlib import Path


def main(argv: list[str] | None = None) -> None:
    """Invoke the CLI, ensuring the local source tree is importable."""
    project_root = Path(__file__).resolve().parents[1]
    src_dir = project_root / "src"
    if str(src_dir) not in sys.path:
        sys.path.insert(0, str(src_dir))

    from automatic_linux_network_repair.cli import app

    app(prog_name="automatic-linux-network-repair", args=argv)


if __name__ == "__main__":
    main()
