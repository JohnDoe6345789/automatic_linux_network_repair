"""Console entrypoints for the network repair toolkit."""

import typer

from automatic_linux_network_repair.eth_repair.cli import DEFAULT_RUNNER
from automatic_linux_network_repair.wifi import SecurityType, WirelessManager


class NetworkRepairCLI:
    """Object-oriented wrapper for the Typer command-line interface."""

    def __init__(self) -> None:
        self.runner = DEFAULT_RUNNER
        self.app = typer.Typer(help="Interactive Ethernet and Wi-Fi helper.")
        self.app.callback(invoke_without_command=True)(self._main)
        self._wifi_app = typer.Typer(help="Wi-Fi scanning and connection utilities.")
        self.app.add_typer(self._wifi_app, name="wifi", help="Wi-Fi management")
        self._wifi_app.command("scan")(self._wifi_scan)
        self._wifi_app.command("connect")(self._wifi_connect)
        self.wifi_manager = WirelessManager()

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

    def _wifi_scan(
        self,
        interface: str | None = typer.Option(
            None,
            "--interface",
            "-i",
            help="Wireless interface to scan (default: auto-detect).",
        ),
        backend: str | None = typer.Option(
            None,
            "--backend",
            "-b",
            help="Preferred wireless backend (nmcli, iwctl, wpa_cli, iwlist).",
        ),
    ) -> None:
        """List nearby Wi-Fi networks."""

        resolved_interface = self._resolve_wifi_interface(interface)
        networks = self.wifi_manager.scan(resolved_interface, preferred_backend=backend)
        if not networks:
            typer.echo("No networks detected.")
            raise typer.Exit(code=1)

        typer.echo("SSID                          SECURITY                 SIGNAL  BSSID")
        typer.echo("-" * 74)
        for net in networks:
            security = ",".join(net.security) if net.security else "open"
            signal = f"{net.signal}" if net.signal is not None else "?"
            typer.echo(
                f"{net.ssid[:28]:<30} {security[:20]:<22} {signal:<6} {net.bssid or '-'}"
            )

    def _wifi_connect(
        self,
        ssid: str = typer.Argument(..., help="Target network SSID."),
        password: str | None = typer.Option(
            None,
            "--password",
            "-p",
            help="Passphrase or key (omit for open networks).",
        ),
        security: str = typer.Option(
            "wpa2",
            "--security",
            "-s",
            help="Security type: open, wep, wpa, wpa2, wpa3.",
        ),
        interface: str | None = typer.Option(
            None,
            "--interface",
            "-i",
            help="Wireless interface to configure (default: auto-detect).",
        ),
        backend: str | None = typer.Option(
            None,
            "--backend",
            "-b",
            help="Preferred wireless backend (nmcli, iwctl, wpa_cli, iwlist).",
        ),
    ) -> None:
        """Connect to a Wi-Fi network using the best available backend."""

        sec = SecurityType.from_label(security)
        resolved_interface = self._resolve_wifi_interface(interface)
        result = self.wifi_manager.connect(
            interface=resolved_interface,
            ssid=ssid,
            password=password,
            security=sec,
            preferred_backend=backend,
        )
        if result.success:
            typer.echo(f"Connected to {ssid!r} via {result.backend}: {result.message}")
            raise typer.Exit(code=0)

        typer.echo(
            f"Failed to connect to {ssid!r} via available backends: {result.message}",
            err=True,
        )
        raise typer.Exit(code=1)

    def run(self) -> None:
        """Invoke the Typer application."""
        self.app()

    def _resolve_wifi_interface(self, interface: str | None) -> str:
        if interface:
            return interface

        detected = self.wifi_manager.detect_interface()
        if detected:
            return detected

        typer.echo(
            "Could not detect a wireless interface; please specify --interface.", err=True
        )
        raise typer.Exit(code=1)


cli = NetworkRepairCLI()
app = cli.app


if __name__ == "__main__":
    cli.run()
