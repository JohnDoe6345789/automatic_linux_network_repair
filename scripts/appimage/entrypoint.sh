#!/usr/bin/env bash
# entrypoint.sh: fix dist permissions then run the AppImage build as the builder user
set -euo pipefail

DIST_DIR=/app/dist

if [ ! -e "${DIST_DIR}" ]; then
  mkdir -p "${DIST_DIR}"
elif [ -d "${DIST_DIR}" ]; then
  :
else
  echo "${DIST_DIR} exists but is not a directory" >&2
  exit 1
fi

sudo chown -R builder:builder "${DIST_DIR}"

# The container already runs as the builder user, so invoke the build script
# directly without sudo to avoid sudoers restrictions.
exec bash -lc "PATH=/app/.venv/bin:${PATH} bash scripts/appimage/build_appimage.sh"
