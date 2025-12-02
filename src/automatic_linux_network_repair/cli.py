"""Console entrypoints for the network repair toolkit."""

import json

import typer
from rich.console import Console

from automatic_linux_network_repair import systemd_panel
from automatic_linux_network_repair.eth_repair.cli import DEFAULT_RUNNER
from automatic_linux_network_repair.systemd_validation import validate_systemd_tree
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
        self.app.command("validate-systemd")(self._validate_systemd)
        self.app.command("systemd-panel")(self._systemd_panel)
        self.app.command("systemd-edit")(self._systemd_edit)
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
            typer.echo(f"{net.ssid[:28]:<30} {security[:20]:<22} {signal:<6} {net.bssid or '-'}")

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

    def _systemd_panel(
        self,
        dump_file: str | None = typer.Option(
            None,
            "--dump-file",
            "-f",
            help="Optional path to a pre-generated systemd-analyze cat-config dump.",
        ),
        path: str = typer.Option(
            "/etc/systemd",
            "--path",
            "-p",
            help="Directory to walk and feed into systemd-analyze cat-config.",
        ),
        schema_json: str | None = typer.Option(
            None,
            "--schema-json",
            "-s",
            help="Optional path to write a JSON schema of active settings.",
        ),
    ) -> None:
        """Render a rich panel summarizing a systemd configuration dump."""

        if dump_file:
            try:
                with open(dump_file, encoding="utf-8") as handle:
                    dump_text = handle.read()
            except OSError as exc:
                typer.echo(f"Failed to read {dump_file}: {exc}", err=True)
                raise typer.Exit(code=1) from exc
        else:
            result = systemd_panel.generate_systemd_dump(base_dir=path)
            if result.returncode != 0:
                detail = result.stderr.strip() or result.stdout.strip() or f"rc={result.returncode}"
                typer.echo(f"Failed to generate systemd dump: {detail}", err=True)
                raise typer.Exit(code=1)

            dump_text = result.stdout

        if schema_json:
            schema = systemd_panel.systemd_schema_from_dump(dump_text)
            try:
                with open(schema_json, "w", encoding="utf-8") as handle:
                    json.dump(schema, handle, indent=2, sort_keys=True)
            except OSError as exc:
                typer.echo(f"Failed to write schema to {schema_json}: {exc}", err=True)
                raise typer.Exit(code=1) from exc

        console = Console(force_terminal=False)
        systemd_panel.print_systemd_panel(dump_text, console=console)

    def _systemd_edit(
        self,
        dump_file: str | None = typer.Option(
            None,
            "--dump-file",
            "-f",
            help="Optional path to a pre-generated systemd-analyze cat-config dump.",
        ),
        path: str = typer.Option(
            "/etc/systemd",
            "--path",
            "-p",
            help="Directory to walk and feed into systemd-analyze cat-config.",
        ),
        dropin_dir: str | None = typer.Option(
            None,
            "--dropin-dir",
            "-d",
            help="Optional override for where to write the generated drop-in file.",
        ),
    ) -> None:
        """Launch an interactive editor to tweak active systemd settings."""

        if dump_file:
            try:
                with open(dump_file, encoding="utf-8") as handle:
                    dump_text = handle.read()
            except OSError as exc:
                typer.echo(f"Failed to read {dump_file}: {exc}", err=True)
                raise typer.Exit(code=1) from exc
        else:
            result = systemd_panel.generate_systemd_dump(base_dir=path)
            if result.returncode != 0:
                detail = result.stderr.strip() or result.stdout.strip() or f"rc={result.returncode}"
                typer.echo(f"Failed to generate systemd dump: {detail}", err=True)
                raise typer.Exit(code=1)

            dump_text = result.stdout

        dropin_path = systemd_panel.interactive_edit_systemd_dump(
            dump_text,
            dropin_dir=dropin_dir,
        )

        if dropin_path is None:
            raise typer.Exit(code=1)

        typer.echo(f"Drop-in written to: {dropin_path}")

    def _validate_systemd(
        self,
        path: str = typer.Option(
            "/etc/systemd",
            "--path",
            "-p",
            help="Path to the systemd configuration directory to validate.",
        ),
    ) -> None:
        """Validate systemd unit files when systemd tools are installed."""

        report = validate_systemd_tree(base_dir=path)

        for issue in report.config_issues:
            typer.echo(f"[CONFIG] {issue}", err=True)

        if not report.available:
            typer.echo("systemctl/systemd-analyze not available; skipping unit validation.", err=True)
            raise typer.Exit(code=1)

        if not report.unit_files:
            if report.config_issues:
                typer.echo(f"Checked configuration under {path}; {len(report.config_issues)} issues found.", err=True)
                raise typer.Exit(code=1)

            typer.echo(f"No systemd unit files found under {path}.")
            raise typer.Exit(code=0)

        failures = 0
        failures += len(report.config_issues)
        for validation in report.validations:
            rc = validation.result.returncode
            status = "OK" if rc == 0 else "FAIL"
            detail = ""
            if rc != 0:
                failures += 1
                detail = validation.result.stderr.strip() or validation.result.stdout.strip() or f"rc={rc}"

            message = f"[{status}] {validation.path}"
            if detail:
                message = f"{message}: {detail}"
            typer.echo(message)

        summary = f"Validated {len(report.unit_files)} files; {failures} failures."
        if failures:
            typer.echo(summary, err=True)
            raise typer.Exit(code=1)

        typer.echo(summary)
        raise typer.Exit(code=0)

    def _resolve_wifi_interface(self, interface: str | None) -> str:
        if interface:
            return interface

        detected = self.wifi_manager.detect_interface()
        if detected:
            return detected

        typer.echo("Could not detect a wireless interface; please specify --interface.", err=True)
        raise typer.Exit(code=1)


cli = NetworkRepairCLI()
app = cli.app


if __name__ == "__main__":
    cli.run()
