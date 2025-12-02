# Usage

`automatic_linux_network_repair` exposes a Typer-based CLI that can run in non-interactive and menu-driven modes. Most commands require root privileges to apply changes to network devices or configuration files.

## CLI basics

```bash
sudo automatic_linux_network_repair --help
```

Common global options:

- `--interface / -i` – Interface to target (defaults to `eth0`; falls back to detected devices when missing).
- `--auto` – Run fuzzy diagnostics and attempt repairs without prompting.
- `--dry-run` – Log intended actions without making changes.
- `--verbose` – Emit debug logging to the console and `/tmp/eth_repair.log`.

## Ethernet repair

- **Automatic run:** `sudo automatic_linux_network_repair --auto` diagnoses link state, DHCP, routing, and DNS issues, applying safe repairs in order.
- **Interactive menu:** `sudo automatic_linux_network_repair --interface eth1` opens a menu that can:
  - Show adapter status and connectivity checks
  - Bring links up and renew IPv4 leases
  - Restart routing and network manager services
  - Repair DNS (systemd‑resolved symlinks or manual resolv.conf)
  - Switch to another detected interface
  - Display all adapters and addresses
  - Access advanced systemd/DNS controls (enable/disable systemd‑resolved, adjust `/etc/resolv.conf` symlinks, or write public DNS entries)

## Wi‑Fi scanning and connection

Subcommands under `wifi` select the best available backend (`nmcli`, `iwctl`, `wpa_cli`, or `iwlist`) and can auto-detect a wireless interface using `iw`, `nmcli`, or `ip link`.

```bash
# List nearby networks on the detected wireless interface
sudo automatic_linux_network_repair wifi scan

# Force a specific interface and backend
sudo automatic_linux_network_repair wifi scan --interface wlp0s20f3 --backend nmcli

# Connect to a network (default security: WPA2)
sudo automatic_linux_network_repair wifi connect "MySSID" --password "hunter2"

# Connect to an open network
sudo automatic_linux_network_repair wifi connect "Guest" --security open
```

The command reports which backend succeeded and surfaces stderr details when a backend fails.

## Systemd validation

Use `validate-systemd` to lint unit files and `resolved.conf`:

```bash
sudo automatic_linux_network_repair validate-systemd --path /etc/systemd
```

The command:

- Checks whether `systemctl` and `systemd-analyze` are available; exits with code 1 if missing.
- Lints `/etc/systemd/resolved.conf` (or the provided path) for invalid IP lists and unsupported option values.
- Runs `systemd-analyze verify` against each unit-like file under the specified tree and summarizes pass/fail counts.

Non-zero exit codes indicate missing tools or validation failures so the command can be wired into CI or provisioning scripts.

## Render a systemd configuration dump

Use `systemd-panel` to walk a systemd directory, run `systemd-analyze cat-config` on every file, and render a readable summary table:

```bash
sudo automatic_linux_network_repair systemd-panel --path /etc/systemd

# Or render a pre-generated dump file
automatic_linux_network_repair systemd-panel --dump-file /tmp/systemd_dump.txt

# Optionally emit a JSON schema alongside the rendered panel
automatic_linux_network_repair systemd-panel --dump-file /tmp/systemd_dump.txt --schema-json /tmp/systemd_schema.json

# A packaged sample schema ships at
# automatic_linux_network_repair/systemd_schemas/systemd_schema_sample.json
# and can be loaded via automatic_linux_network_repair.systemd_schemas.load_sample_schema().
# The file includes active values plus commented defaults and can be rendered
# back into a cat-config-style dump with systemd_panel.systemd_dump_from_schema().
```

Launch an interactive editor to choose a file and setting to change. By default it walks `/etc/systemd` and writes a drop-in
next to the selected file:

```
sudo automatic_linux_network_repair systemd-edit

# The editor shows a preview and asks for confirmation before writing to disk

# Use a captured dump and override where the drop-in is written
automatic_linux_network_repair systemd-edit --dump-file /tmp/systemd_dump.txt --dropin-dir /tmp/dropins
```
