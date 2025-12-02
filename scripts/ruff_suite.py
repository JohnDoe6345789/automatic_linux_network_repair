#!/usr/bin/env python3
"""Run Ruff linting and formatting checks in sequence.

This helper ensures both commands execute, even if one fails, and reports a
summary exit status.
"""

from __future__ import annotations

import subprocess
from typing import Final

Command = tuple[str, list[str]]

COMMANDS: Final[list[Command]] = [
    ("ruff check .", ["ruff", "check", "."]),
    ("ruff format --check", ["ruff", "format", "--check"]),
]


def run_command(label: str, command: list[str]) -> int:
    """Execute a single command and print its result."""
    print(f"Running {label}...")
    result = subprocess.run(command, check=False)
    outcome = "passed" if result.returncode == 0 else "failed"
    print(f"{label} {outcome} with exit code {result.returncode}.")
    return result.returncode


def main() -> None:
    """Run each configured command and exit non-zero if any fail."""
    failures: list[tuple[str, int]] = []

    for label, command in COMMANDS:
        exit_code = run_command(label, command)
        if exit_code != 0:
            failures.append((label, exit_code))

    if failures:
        print("\nSummary: some commands failed:")
        for label, code in failures:
            print(f" - {label}: exit code {code}")
        raise SystemExit(1)

    print("\nSummary: all commands succeeded.")
    raise SystemExit(0)


if __name__ == "__main__":
    main()
