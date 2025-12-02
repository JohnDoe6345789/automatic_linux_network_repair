#!/usr/bin/env bash
# Build an AppImage for automatic-linux-network-repair using PyInstaller and appimagetool.

set -euo pipefail

SCRIPT_DIR=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
PROJECT_ROOT=$(cd -- "${SCRIPT_DIR}/../.." && pwd)
APP_NAME="automatic-linux-network-repair"
APPDIR="${PROJECT_ROOT}/dist/AppDir"
PYINSTALLER_ENTRYPOINT="${PROJECT_ROOT}/src/automatic_linux_network_repair/__main__.py"
APPIMAGETOOL="${SCRIPT_DIR}/appimagetool"
APPIMAGETOOL_URL="https://github.com/AppImage/AppImageKit/releases/download/continuous/appimagetool-x86_64.AppImage"

ensure_dependency() {
    local name=$1
    if ! command -v "$name" >/dev/null 2>&1; then
        echo "Missing dependency: $name" >&2
        echo "Install it in your active virtual environment before retrying." >&2
        exit 1
    fi
}

fetch_appimagetool() {
    if [ -x "$APPIMAGETOOL" ]; then
        return
    fi

    mkdir -p "$SCRIPT_DIR"
    echo "Downloading appimagetool from ${APPIMAGETOOL_URL}..."
    curl -L -o "$APPIMAGETOOL" "$APPIMAGETOOL_URL"
    chmod +x "$APPIMAGETOOL"
}

build_binary() {
    echo "Building PyInstaller binary..."
    ensure_dependency pyinstaller
    pyinstaller \
        --clean \
        --onefile \
        --name "$APP_NAME" \
        "$PYINSTALLER_ENTRYPOINT"
}

prepare_appdir() {
    echo "Preparing AppDir layout..."
    rm -rf "$APPDIR"
    mkdir -p "$APPDIR/usr/bin"

    cp "$PROJECT_ROOT/dist/$APP_NAME" "$APPDIR/usr/bin/"
    install -m755 "$SCRIPT_DIR/AppRun" "$APPDIR/AppRun"
    install -m644 "$SCRIPT_DIR/automatic_linux_network_repair.desktop" "$APPDIR/$APP_NAME.desktop"
    install -m644 "$SCRIPT_DIR/automatic_linux_network_repair.svg" "$APPDIR/$APP_NAME.svg"
}

package_appimage() {
    echo "Packaging AppImage..."
    fetch_appimagetool
    "$APPIMAGETOOL" "$APPDIR"
}

main() {
    build_binary
    prepare_appdir
    package_appimage
    echo "AppImage created in dist/$(basename "$APP_NAME")*.AppImage"
}

main "$@"
