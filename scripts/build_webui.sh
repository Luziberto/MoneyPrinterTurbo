#!/usr/bin/env sh
# Builds webui-vue/ and copies the output into resource/public/, which
# app/asgi.py already mounts at "/". Not run automatically -- call this
# before starting the API if you want the Vue cockpit served instead of
# the placeholder page, or rely on the Dockerfile's webui-vue-build stage
# when building the container image.
set -e

CURRENT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
cd "$CURRENT_DIR/webui-vue"

if command -v npm >/dev/null 2>&1; then
  npm ci
  npm run build
else
  echo "***** npm not found. Install Node.js to build the Vue cockpit. *****" >&2
  exit 1
fi

rm -rf "$CURRENT_DIR/resource/public"
mkdir -p "$CURRENT_DIR/resource/public"
cp -r "$CURRENT_DIR/webui-vue/dist/." "$CURRENT_DIR/resource/public/"

echo "Built webui-vue -> resource/public/"
