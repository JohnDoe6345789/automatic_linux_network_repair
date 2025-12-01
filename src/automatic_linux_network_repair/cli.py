"""Console entrypoints for the network repair toolkit."""

import typer

from automatic_linux_network_repair.eth_repair.cli import DEFAULT_RUNNER


class NetworkRepairCLI:
    """Object-oriented wrapper for the Typer command-line interface."""

    def __init__(self) -> None:
        self.runner = DEFAULT_RUNNER
        self.app = typer.Typer(help="Interactive Ethernet repair helper.")
        self.app.callback(invoke_without_command=True)(self._main)

    def _main(
        self,
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

        exit_code = self.runner.run(
            interface=interface,
            dry_run=dry_run,
            verbose=verbose,
            auto=auto,
        )
        raise typer.Exit(code=exit_code)

    def run(self) -> None:
        """Invoke the Typer application."""
        self.app()


cli = NetworkRepairCLI()
app = cli.app


if __name__ == "__main__":
    cli.run()
