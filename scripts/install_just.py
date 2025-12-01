"""
Typer-based helper to check and install `just`.

Usage (example with Poetry):

1) Add to pyproject.toml:

   [tool.poetry.scripts]
   dev = "your_package.dev_cli:app"

2) Run:

   poetry run dev install-just
   poetry run dev check-just

This script:
- Detects whether `just` is on PATH.
- Optionally attempts automatic installation on common platforms.
- Always prints explicit manual instructions.
"""

from __future__ import annotations

import platform
import shutil
import subprocess
import sys
from typing import Final

import typer

app = typer.Typer(help="Developer utilities for this project.")

JUST_COMMAND: Final[str] = "just"


def _run_command(command: list[str]) -> int:
    """Run a command and return its exit code."""
    process = subprocess.run(command, check=False)
    return process.returncode


def _is_just_installed() -> bool:
    """Return True if `just` is available on PATH."""
    return shutil.which(JUST_COMMAND) is not None


def _platform_name() -> str:
    """Return a simplified platform name."""
    system = platform.system().lower()
    if system.startswith("linux"):
        return "linux"
    if system == "darwin":
        return "macos"
    if system == "windows":
        return "windows"
    return "unknown"


def _print_manual_instructions() -> None:
    """Print manual installation instructions for `just`."""
    typer.echo()
    typer.echo("Manual installation instructions for `just`:\n")

    typer.echo("Linux (Debian/Ubuntu):")
    typer.echo("  sudo apt install just")
    typer.echo("or (any Linux):")
    typer.echo("  curl -s https://just.systems/install.sh | bash")
    typer.echo()

    typer.echo("macOS (Homebrew):")
    typer.echo("  brew install just")
    typer.echo()

    typer.echo("Windows (Scoop):")
    typer.echo("  scoop install just")
    typer.echo("Windows (Chocolatey):")
    typer.echo("  choco install just")
    typer.echo()

    typer.echo("Rust (any OS, with cargo):")
    typer.echo("  cargo install just")
    typer.echo()

    typer.echo("Releases (manual binary):")
    typer.echo("  https://github.com/casey/just/releases")
    typer.echo()


def _auto_install_linux() -> bool:
    """Try to install `just` on Linux, return True on success."""
    if shutil.which("apt"):
        return _run_command(["sudo", "apt", "update"]) == 0 and _run_command(
            ["sudo", "apt", "install", "-y", "just"],
        ) == 0

    if shutil.which("curl"):
        return (
            _run_command(["bash", "-c", "curl -s https://just.systems/install.sh | bash"])
            == 0
        )

    return False


def _auto_install_macos() -> bool:
    """Try to install `just` on macOS, return True on success."""
    if shutil.which("brew"):
        return _run_command(["brew", "install", "just"]) == 0
    return False


def _auto_install_windows() -> bool:
    """Try to install `just` on Windows, return True on success."""
    if shutil.which("scoop"):
        return _run_command(["scoop", "install", "just"]) == 0

    if shutil.which("choco"):
        return _run_command(["choco", "install", "just", "-y"]) == 0

    return False


def _attempt_auto_install() -> bool:
    """Attempt platform-appropriate automatic installation."""
    system = _platform_name()

    if system == "linux":
        return _auto_install_linux()

    if system == "macos":
        return _auto_install_macos()

    if system == "windows":
        return _auto_install_windows()

    return False


@app.command("check-just")
def check_just() -> None:
    """
    Check whether `just` is installed and print its status.

    This does not attempt to install anything.
    """
    if _is_just_installed():
        typer.secho("`just` is installed and available on PATH.", fg=typer.colors.GREEN)
        version_code = _run_command([JUST_COMMAND, "--version"])
        if version_code != 0:
            typer.secho(
                "Unable to run `just --version` (non-zero exit code).",
                fg=typer.colors.YELLOW,
            )
        raise typer.Exit(code=0)

    typer.secho("`just` is NOT installed or not on PATH.", fg=typer.colors.RED)
    _print_manual_instructions()
    raise typer.Exit(code=1)


@app.command("install-just")
def install_just(
    auto: bool = typer.Option(
        False,
        "--auto",
        help=(
            "Attempt automatic installation using apt/brew/scoop/choco/curl. "
            "Falls back to manual instructions if it fails."
        ),
    ),
) -> None:
    """
    Ensure `just` is installed for this development environment.

    By default, this prints clear installation instructions.
    Pass --auto to attempt a best-effort automatic install.
    """
    if _is_just_installed():
        typer.secho(
            "`just` is already installed and available on PATH.",
            fg=typer.colors.GREEN,
        )
        raise typer.Exit(code=0)

    typer.secho("`just` is not installed.", fg=typer.colors.YELLOW)
    if not auto:
        typer.echo()
        typer.echo("No changes were made because --auto was not provided.")
        _print_manual_instructions()
        raise typer.Exit(code=1)

    typer.echo("Attempting automatic installation of `just`...")
    success = _attempt_auto_install()

    if success and _is_just_installed():
        typer.secho(
            "Automatic installation of `just` appears to have succeeded.",
            fg=typer.colors.GREEN,
        )
        raise typer.Exit(code=0)

    typer.secho(
        "Automatic installation failed or `just` is still not available on PATH.",
        fg=typer.colors.RED,
    )
    _print_manual_instructions()
    raise typer.Exit(code=1)


def main() -> None:
    """Entry point for `python -m` usage."""
    app()


if __name__ == "__main__":
    main()
