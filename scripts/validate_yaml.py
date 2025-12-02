#!/usr/bin/env python3
"""Validate YAML syntax across the repository."""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Iterable

import yaml
from yaml import YAMLError

DEFAULT_EXCLUDES = {".git", ".venv", "venv", "build", "dist", "__pycache__"}


def iter_yaml_files(root: Path, excludes: set[str]) -> Iterable[Path]:
    """Yield YAML files under *root* while skipping excluded directories."""
    for path in root.rglob("*.yml"):
        if any(part in excludes for part in path.parts):
            continue
        if path.is_file():
            yield path


def validate_yaml_file(path: Path) -> tuple[bool, str | None]:
    """Load a YAML file and return a tuple indicating success and any error message."""
    try:
        with path.open("r", encoding="utf-8") as handle:
            yaml.safe_load(handle)
    except YAMLError as exc:  # pragma: no cover - defensive error handling
        return False, str(exc)
    except OSError as exc:  # pragma: no cover - filesystem errors
        return False, f"OS error: {exc}"

    return True, None


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate syntax of all YAML files in the repository.")
    parser.add_argument(
        "--root",
        type=Path,
        default=Path(__file__).resolve().parent.parent,
        help="Root directory to scan for YAML files.",
    )
    parser.add_argument(
        "--exclude",
        action="append",
        default=list(DEFAULT_EXCLUDES),
        help="Directories to exclude from the search (can be specified multiple times).",
    )
    args = parser.parse_args()

    root = args.root.resolve()
    excludes = set(args.exclude)

    yaml_files = list(iter_yaml_files(root, excludes))
    if not yaml_files:
        print("No YAML files found.")
        return 0

    failures: list[Path] = []
    for yaml_file in sorted(yaml_files):
        is_valid, error_message = validate_yaml_file(yaml_file)
        relative_path = yaml_file.relative_to(root)
        if is_valid:
            print(f"OK: {relative_path}")
        else:
            print(f"ERROR: {relative_path}")
            print(error_message)
            failures.append(yaml_file)

    if failures:
        print(f"Validation failed for {len(failures)} file(s).")
        return 1

    print("All YAML files validated successfully.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
