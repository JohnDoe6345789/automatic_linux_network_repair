# Building an AppImage

The project can be packaged as an AppImage by combining a PyInstaller binary with the
standard AppDir layout. Use the helper script to automate the process.

## Prerequisites

- Python 3.10–3.14 with the project dependencies installed.
- `pyinstaller` version 6.3 or newer (Python 3.12 compatible) available in your active
  environment. It is already pinned in `requirements.txt`.
- `curl` available for fetching `appimagetool` if it is not already present.

## Steps

1. Activate your virtual environment and install the tooling:

   ```bash
   pip install -r requirements.txt
   ```

2. Run the build script from the repository root:

   ```bash
   bash scripts/appimage/build_appimage.sh
   ```

   The script will:

   - Build a one-file PyInstaller binary named `automatic-linux-network-repair`.
   - Assemble the AppDir with the launcher, desktop entry, and icon.
   - Download `appimagetool` on first use (stored at `scripts/appimage/appimagetool`).
   - Produce the final AppImage in `dist/`.

3. Execute the resulting AppImage:

   ```bash
   chmod +x dist/automatic-linux-network-repair*.AppImage
   ./dist/automatic-linux-network-repair*.AppImage --help
   ```

## Debian Bookworm (x86_64, Python 3.11) quickstart

Use these commands on Debian 12 to create an isolated Python 3.11 environment and
build the AppImage end-to-end:

```bash
sudo apt update
sudo apt install -y python3.11 python3.11-venv python3.11-dev build-essential patchelf curl

python3.11 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt

bash scripts/appimage/build_appimage.sh
ls dist/automatic-linux-network-repair-x86_64.AppImage
```

- `patchelf` is required by PyInstaller when building the single-file binary.
- Bookworm ships Python 3.11 by default, but the explicit package names avoid
  picking up an alternative interpreter if one is installed.

### CI support

GitHub Actions does not offer a Debian Bookworm hosted runner. Use a container
job (e.g., `container: debian:12`) or a self-hosted runner when you need this
exact environment. On the default Ubuntu runners, keep the `APPIMAGE_EXTRACT_AND_RUN`
behavior from the build script so the AppImage creation still works without FUSE.

You can also build the AppImage inside `Dockerfile.appimage` directly from a
GitHub Actions job that runs on `ubuntu-latest`:

```yaml
- uses: actions/checkout@v4
- name: Build AppImage in Docker
  run: |
    docker build -f Dockerfile.appimage -t aln-appimage .
    mkdir -p dist
    docker run --rm -v "${{ github.workspace }}/dist:/app/dist" aln-appimage
- uses: actions/upload-artifact@v4
  with:
    name: appimage
    path: dist/*.AppImage
```

## Build inside Docker (Debian Bookworm)

To keep the Debian 12 toolchain isolated, use the provided `Dockerfile.appimage`
to build the AppImage inside a container:

```bash
docker build -f Dockerfile.appimage -t aln-appimage .
docker run --rm -v "$(pwd)/dist:/app/dist" aln-appimage
```

The container installs Python 3.11 along with PyInstaller requirements and sets
`APPIMAGE_EXTRACT_AND_RUN=1` so the build works without FUSE. The generated
AppImage is emitted to your local `dist/` directory via the bind mount.

If the mounted `dist/` directory is read-only for the container user, set a
custom output path with `DIST_DIR=/tmp/dist` (or another writable location) and
copy the resulting AppImage back to your host afterwards.

## Notes

- The AppImage uses the CLI entrypoint and runs in a terminal.
- Re-run the script after code changes to refresh the binary inside the AppImage.
- If you prefer a system-wide `appimagetool`, place it on your `PATH` and the script
  will use it instead of downloading a local copy.
- The script sets `APPIMAGE_EXTRACT_AND_RUN=1` when invoking `appimagetool` so it can
  run in environments without FUSE (e.g., CI runners or containers).
