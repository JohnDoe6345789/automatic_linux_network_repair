# Offline installation

Use the wheelhouse helper when the target machine cannot reach PyPI. The script downloads all runtime dependencies, builds a wheel for the project itself, and copies the resulting wheelhouse to a mounted USB drive.

## Build the wheelhouse

From a connected machine with Python 3.10–3.14 installed:

```bash
# Install build dependencies
pip install -r requirements.txt

# Download dependencies and copy wheels to the USB mount point
python scripts/prepare_wheelhouse.py --usb-mount /media/usb
```

After the script completes, the USB drive will contain a `wheelhouse/` directory populated with wheels for `automatic_linux_network_repair` and its dependencies.

## Install from the wheelhouse

On the offline machine:

```bash
sudo mkdir -p /opt/wheelhouse
sudo cp -r /media/usb/wheelhouse /opt/wheelhouse
pip install --no-index --find-links /opt/wheelhouse automatic_linux_network_repair
```

If your Python executable is not on the default `PATH`, replace `pip` with the appropriate interpreter (e.g., `python3 -m pip`). The same `--find-links` directory can be reused across multiple hosts as long as their Python versions satisfy the package requirement range (>=3.10,<3.15).
