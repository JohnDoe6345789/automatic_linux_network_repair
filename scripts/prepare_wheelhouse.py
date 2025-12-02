#!/usr/bin/env python3
"""Build a local wheelhouse and copy it to a mounted USB drive."""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Iterable, List

PROJECT_ROOT = Path(__file__).resolve().parent.parent


def _resolve(path: str) -> Path:
    return Path(path).expanduser().resolve()


def _run_command(command: Iterable[str]) -> None:
    printable = " ".join(command)
    print(f"Running: {printable}")
    process = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    print(process.stdout)
    if process.returncode != 0:
        raise SystemExit(f"Command failed: {printable}")


def _prepare_wheelhouse(requirements: Path, wheelhouse: Path) -> None:
    if wheelhouse.exists():
        shutil.rmtree(wheelhouse)
    wheelhouse.mkdir(parents=True, exist_ok=True)

    download_cmd: List[str] = [
        sys.executable,
        "-m",
        "pip",
        "download",
        "--requirement",
        str(requirements),
        "--dest",
        str(wheelhouse),
    ]
    _run_command(download_cmd)

    build_cmd: List[str] = [
        sys.executable,
        "-m",
        "pip",
        "wheel",
        "--no-deps",
        "--wheel-dir",
        str(wheelhouse),
        str(PROJECT_ROOT),
    ]
    _run_command(build_cmd)


def _copy_to_usb(source: Path, usb_mount: Path) -> Path:
    if not usb_mount.exists() or not usb_mount.is_dir():
        raise SystemExit(f"USB mount path does not exist or is not a directory: {usb_mount}")

    target = usb_mount / source.name
    if target.exists():
        shutil.rmtree(target)
    shutil.copytree(source, target)
    return target


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Prepare wheelhouse and copy it to a USB flash drive.")
    parser.add_argument(
        "--requirements",
        default=str(PROJECT_ROOT / "requirements.txt"),
        type=str,
        help="Path to requirements file to download (default: requirements.txt in repo root).",
    )
    parser.add_argument(
        "--wheelhouse",
        default=str(PROJECT_ROOT / "wheelhouse"),
        type=str,
        help="Directory to create the wheelhouse in (default: ./wheelhouse).",
    )
    parser.add_argument(
        "--usb-mount",
        required=True,
        type=str,
        help="Path to mounted USB drive where the wheelhouse will be copied.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    requirements = _resolve(args.requirements)
    wheelhouse = _resolve(args.wheelhouse)
    usb_mount = _resolve(args.usb_mount)

    if not requirements.exists():
        raise SystemExit(f"Requirements file not found: {requirements}")

    print(f"Using requirements: {requirements}")
    print(f"Building wheelhouse in: {wheelhouse}")
    print(f"USB mount path: {usb_mount}")

    _prepare_wheelhouse(requirements, wheelhouse)
    copied_path = _copy_to_usb(wheelhouse, usb_mount)
    print(f"Wheelhouse copied to: {copied_path}")
    print("Done. The USB drive now contains the wheelhouse for offline installation.")


if __name__ == "__main__":
    main()
