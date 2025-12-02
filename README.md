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
- **Dry-run and logging** – Preview actions without making changes and write verbose logs to `/tmp/eth_repair.log` for later analysis.
- **Distribution helpers** – Build an AppImage for portable distribution or create an offline wheelhouse for air‑gapped installs.

## Quickstart

```bash
pip install automatic_linux_network_repair

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

## Packaging and offline installs

- **AppImage builds** – Use the helper script in `scripts/appimage` to package the CLI as an AppImage. See [`docs/appimage.md`](docs/appimage.md) for prerequisites and step-by-step usage.
- **Preparing an offline wheelhouse** – `scripts/prepare_wheelhouse.py` downloads project dependencies, builds a wheel, and copies the resulting `wheelhouse/` directory to a mounted USB drive so the tool can be installed without internet access.

## Credits

This package was created with [Cookiecutter](https://github.com/audreyfeldroy/cookiecutter) and the [audreyfeldroy/cookiecutter-pypackage](https://github.com/audreyfeldroy/cookiecutter-pypackage) project template.
