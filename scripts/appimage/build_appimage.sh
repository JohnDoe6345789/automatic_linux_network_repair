#!/usr/bin/env bash
# Build an AppImage for automatic-linux-network-repair using PyInstaller and appimagetool.

set -euo pipefail

SCRIPT_DIR=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
PROJECT_ROOT=$(cd -- "${SCRIPT_DIR}/../.." && pwd)
APP_NAME="automatic-linux-network-repair"
DIST_DIR="${DIST_DIR:-${PROJECT_ROOT}/dist}"
BUILD_DIR="${BUILD_DIR:-${PROJECT_ROOT}/build/pyinstaller}"
APPDIR="${DIST_DIR}/AppDir"
APPIMAGE_OUTPUT="${DIST_DIR}/${APP_NAME}-$(uname -m).AppImage"
PYINSTALLER_ENTRYPOINT="${PROJECT_ROOT}/src/automatic_linux_network_repair/__main__.py"
APPIMAGETOOL_DIR="${DIST_DIR}/appimagetool"
APPIMAGETOOL="${APPIMAGETOOL_DIR}/appimagetool"
APPIMAGETOOL_URL="https://github.com/AppImage/AppImageKit/releases/download/continuous/appimagetool-x86_64.AppImage"

ensure_writable_dir() {
    local path=$1

    mkdir -p "$path"

    if [ ! -w "$path" ]; then
        echo "Cannot write to ${path}. Adjust its permissions or choose a writable location via DIST_DIR." >&2
        exit 1
    fi
}

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

    ensure_writable_dir "$APPIMAGETOOL_DIR"
    echo "Downloading appimagetool from ${APPIMAGETOOL_URL}..."
    curl -L -o "$APPIMAGETOOL" "$APPIMAGETOOL_URL"
    chmod +x "$APPIMAGETOOL"
}

build_binary() {
    echo "Building PyInstaller binary..."
    ensure_dependency pyinstaller
    ensure_writable_dir "$DIST_DIR"
    rm -rf "$BUILD_DIR"
    pyinstaller \
        --clean \
        --distpath "$DIST_DIR" \
        --workpath "$BUILD_DIR" \
        --onefile \
        --name "$APP_NAME" \
        "$PYINSTALLER_ENTRYPOINT"
}

prepare_appdir() {
    echo "Preparing AppDir layout..."
    rm -rf "$APPDIR"
    mkdir -p "$APPDIR/usr/bin"

    cp "$DIST_DIR/$APP_NAME" "$APPDIR/usr/bin/"
    install -m755 "$SCRIPT_DIR/AppRun" "$APPDIR/AppRun"
    install -m644 "$SCRIPT_DIR/automatic_linux_network_repair.desktop" "$APPDIR/$APP_NAME.desktop"
    install -m644 "$SCRIPT_DIR/automatic_linux_network_repair.svg" "$APPDIR/$APP_NAME.svg"
}

package_appimage() {
    echo "Packaging AppImage..."
    fetch_appimagetool
    rm -f "$APPIMAGE_OUTPUT"
    APPIMAGE_EXTRACT_AND_RUN=1 "$APPIMAGETOOL" "$APPDIR" "$APPIMAGE_OUTPUT"
}

main() {
    build_binary
    prepare_appdir
    package_appimage
    echo "AppImage created at ${APPIMAGE_OUTPUT}"
}

main "$@"
