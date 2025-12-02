# Building an AppImage

The project can be packaged as an AppImage by combining a PyInstaller binary with the
standard AppDir layout. Use the helper script to automate the process.

## Prerequisites

- Python 3.10+ with the project dependencies installed.
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

## Notes

- The AppImage uses the CLI entrypoint and runs in a terminal.
- Re-run the script after code changes to refresh the binary inside the AppImage.
- If you prefer a system-wide `appimagetool`, place it on your `PATH` and the script
  will use it instead of downloading a local copy.
