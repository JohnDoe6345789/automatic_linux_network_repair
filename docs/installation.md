# Installation

## Requirements

- Python 3.10–3.14
- Root privileges for most network repair operations
- Common networking tools on the host (e.g., `ip`, `nmcli`, or `iw` for Wi‑Fi management)

## Stable release

Install from PyPI using your preferred package manager:

```bash
uv add automatic_linux_network_repair
# or
pip install automatic_linux_network_repair
```

Verify the CLI is available:

```bash
automatic_linux_network_repair --help
```

## From source

Clone the repository and install it in editable mode:

```bash
git clone https://github.com/JohnDoe6345789/automatic_linux_network_repair.git
cd automatic_linux_network_repair
uv pip install -e .
```

## Offline installs

When the target machine cannot reach PyPI, generate a wheel bundle on a connected system:

```bash
python scripts/prepare_wheelhouse.py --usb-mount /media/usb
```

Copy the resulting `wheelhouse/` directory to the offline host and install with `pip --no-index --find-links /path/to/wheelhouse automatic_linux_network_repair`. See [Offline installation](offline_install.md) for the full workflow.
