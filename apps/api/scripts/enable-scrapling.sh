#!/usr/bin/env bash
# enable-scrapling.sh — one-command enable of the optional Scrapling provider (Linux/Mac/CI).
#
#   ./scripts/enable-scrapling.sh                 # HTTP fetching only (lean)
#   ./scripts/enable-scrapling.sh --with-browsers # also install Chromium for JS rendering
#
# Installs the optional dependency, optionally the browser, and prints the env vars to
# set. Does NOT modify requirements.txt; the Dockerfile has INSTALL_SCRAPLING for deploys.
# Stealth features are never used by the provider.

set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
API_DIR="$(dirname "$HERE")"
WITH_BROWSERS=false
[ "${1:-}" = "--with-browsers" ] && WITH_BROWSERS=true

echo "[scrapling] Installing optional dependency…"
python -m pip install -r "$API_DIR/requirements-scrapling.txt"

if [ "$WITH_BROWSERS" = "true" ]; then
    echo "[scrapling] Installing browser (Chromium) for JS rendering…"
    scrapling install
fi

echo ""
echo "[scrapling] Installed. To turn the provider ON, set these env vars:"
echo '    export COMPLIANCE_SCRAPER_PROVIDER=scrapling'
if [ "$WITH_BROWSERS" = "true" ]; then
    echo '    export COMPLIANCE_SCRAPLING_RENDER_JS=true   # JS rendering (needs the browser)'
else
    echo '    # (leave COMPLIANCE_SCRAPLING_RENDER_JS unset/false for HTTP-only fetching)'
fi
echo ""
echo "For production (Docker/Render): build with --build-arg INSTALL_SCRAPLING=true"
