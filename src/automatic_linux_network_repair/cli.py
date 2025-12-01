"""Console entrypoints for the network repair toolkit."""

import typer
from rich.console import Console

from automatic_linux_network_repair import utils
from automatic_linux_network_repair.eth_repair.cli import main as eth_repair_main

app = typer.Typer(help="Interactive Ethernet repair helper.")
console = Console()


@app.callback(invoke_without_command=True)
def main(
    ctx: typer.Context,
    interface: str = typer.Option(
        "eth0",
        "--interface",
        "-i",
        help="Interface to repair (default: eth0).",
    ),
    dry_run: bool = typer.Option(
        False,
        "--dry-run",
        help="Log actions but do not make changes.",
    ),
    verbose: bool = typer.Option(
        False,
        "--verbose",
        help="Enable verbose debug logging.",
    ),
    auto: bool = typer.Option(
        False,
        "--auto",
        help="Run non-interactive fuzzy diagnose and repair.",
    ),
) -> None:
    """Delegate to the interactive Ethernet repair helper."""
    if ctx.invoked_subcommand is not None:
        return

    exit_code = eth_repair_main(
        interface=interface,
        dry_run=dry_run,
        verbose=verbose,
        auto=auto,
    )
    raise typer.Exit(code=exit_code)


@app.command()
def example() -> None:
    """Placeholder command retained for compatibility."""
    console.print(
        "Replace this message by putting your code into "
        "automatic_linux_network_repair.cli.main",
    )
    console.print("See Typer documentation at https://typer.tiangolo.com/")
    utils.do_something_useful()


if __name__ == "__main__":
    app()
