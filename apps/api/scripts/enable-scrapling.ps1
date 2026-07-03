# enable-scrapling.ps1 — one-command local enable of the optional Scrapling provider.
#
#   ./scripts/enable-scrapling.ps1              # HTTP fetching only (lean)
#   ./scripts/enable-scrapling.ps1 -WithBrowsers # also install Chromium for JS rendering
#
# Installs the optional dependency, optionally the browser, and prints the env vars
# to set. Does NOT modify requirements.txt (kept lean); the Dockerfile has a build arg
# for deploys. Stealth features are never used by the provider.

param([switch]$WithBrowsers)

$ErrorActionPreference = "Stop"
$here = Split-Path -Parent $MyInvocation.MyCommand.Path
$apiDir = Split-Path -Parent $here

Write-Host "[scrapling] Installing optional dependency…" -ForegroundColor Cyan
python -m pip install -r "$apiDir/requirements-scrapling.txt"

if ($WithBrowsers) {
    Write-Host "[scrapling] Installing browser (Chromium) for JS rendering…" -ForegroundColor Cyan
    scrapling install
}

Write-Host ""
Write-Host "[scrapling] Installed. To turn the provider ON, set these env vars:" -ForegroundColor Green
Write-Host '    $env:COMPLIANCE_SCRAPER_PROVIDER = "scrapling"'
if ($WithBrowsers) {
    Write-Host '    $env:COMPLIANCE_SCRAPLING_RENDER_JS = "true"   # JS rendering (needs the browser)'
} else {
    Write-Host '    # (leave COMPLIANCE_SCRAPLING_RENDER_JS unset/false for HTTP-only fetching)'
}
Write-Host ""
Write-Host "For production (Docker/Render): build with --build-arg INSTALL_SCRAPLING=true" -ForegroundColor Yellow
