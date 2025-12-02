# Automatic Linux Network Repair

![PyPI version](https://img.shields.io/pypi/v/automatic_linux_network_repair.svg)
[![Documentation Status](https://readthedocs.org/projects/automatic_linux_network_repair/badge/?version=latest)](https://automatic_linux_network_repair.readthedocs.io/en/latest/?version=latest)

Automatic Linux Network Repair is a batteries-included command-line assistant for bringing misbehaving network stacks back online. It bundles Ethernet troubleshooting, Wi‑Fi scanning and connection, and systemd validation tools behind a single Typer-based CLI that favors sensible defaults and clear logging.

* PyPI package: https://pypi.org/project/automatic_linux_network_repair/
* Free software: MIT License
* Documentation: https://automatic_linux_network_repair.readthedocs.io.

## Features

- **Interactive Ethernet helper** – Walk through connectivity fixes with a menu that can show adapter status, renew DHCP, restart routing services, repair DNS, and toggle systemd‑resolved symlinks.
- **Non-interactive repair** – Use `--auto` to run fuzzy diagnostics and attempt common repairs automatically (ideal for SSH sessions or remote recovery).
- **Wi‑Fi management** – Scan for nearby networks and connect using the best available backend (`nmcli`, `iwctl`, `wpa_cli`, or `iwlist`), with automatic interface detection when possible.
- **Systemd validation** – Verify unit files and lint `/etc/systemd/resolved.conf` using `systemd-analyze verify`, with concise pass/fail reporting.
- **Systemd configuration panel** – Render `systemd-analyze cat-config` dumps into a single readable panel highlighting active settings.
- **Systemd configuration editor** – Walk discovered systemd files, pick the setting to change via menus, and emit a ready-to-use drop-in.
- **Dry-run and logging** – Preview actions without making changes and write verbose logs to `/tmp/eth_repair.log` for later analysis.
- **Distribution helpers** – Build an AppImage for portable distribution or create an offline wheelhouse for air‑gapped installs.

## Quickstart

```bash
pip install automatic_linux_network_repair

or

pip install .

# Common entrypoint (requires root for most operations)
sudo automatic_linux_network_repair --help
```

### Repair a wired interface

```bash
# Let the tool pick a likely interface and run non-interactive fixes
sudo automatic_linux_network_repair --auto

# Open the interactive menu for a specific interface
sudo automatic_linux_network_repair --interface eth1
```

### Manage Wi‑Fi

```bash
# Discover networks (auto-detect interface)
sudo automatic_linux_network_repair wifi scan

# Connect to a WPA2 network using the preferred backend
sudo automatic_linux_network_repair wifi connect "Office WiFi" --password "s3cret" --security wpa2
```

### Validate systemd configuration

```bash
# Check unit files and lint resolved.conf under /etc/systemd
sudo automatic_linux_network_repair validate-systemd

# Point at an alternative systemd tree (useful for chroots or mounts)
sudo automatic_linux_network_repair validate-systemd --path /mnt/target/etc/systemd
```

### Render a systemd configuration dump

```bash
# Automatically walk /etc/systemd, run systemd-analyze cat-config, and render it
sudo automatic_linux_network_repair systemd-panel --path /etc/systemd

# Or render a previously captured dump file (useful for offline analysis)
automatic_linux_network_repair systemd-panel --dump-file /tmp/systemd_dump.txt

# Optionally save a JSON schema of active settings while rendering
automatic_linux_network_repair systemd-panel --dump-file /tmp/systemd_dump.txt --schema-json /tmp/systemd_schema.json

# A packaged sample schema ships at
# automatic_linux_network_repair/systemd_schemas/systemd_schema_sample.json
# and can be loaded via automatic_linux_network_repair.systemd_schemas.load_sample_schema().
# It includes both active values and commented defaults and can be rendered back
# to a cat-config-style dump with systemd_panel.systemd_dump_from_schema().

# Launch an interactive editor, choose a file + option, and write a drop-in
sudo automatic_linux_network_repair systemd-edit

# The editor shows a preview and asks for confirmation before writing to disk

# Use a pre-generated dump and override where the drop-in is written. The
# override directory must be secure (not a symlink and not world-writable).
automatic_linux_network_repair systemd-edit --dump-file /tmp/systemd_dump.txt --dropin-dir /tmp/dropins
```

## Packaging and offline installs

- **AppImage builds** – Use the helper script in `scripts/appimage` to package the CLI as an AppImage. See [`docs/appimage.md`](docs/appimage.md) for prerequisites and step-by-step usage.
- **Preparing an offline wheelhouse** – `scripts/prepare_wheelhouse.py` downloads project dependencies, builds a wheel, and copies the resulting `wheelhouse/` directory to a mounted USB drive so the tool can be installed without internet access.

## Credits

This package was created with [Cookiecutter](https://github.com/audreyfeldroy/cookiecutter) and the [audreyfeldroy/cookiecutter-pypackage](https://github.com/audreyfeldroy/cookiecutter-pypackage) project template.
