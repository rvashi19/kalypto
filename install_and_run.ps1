Write-Host "Setting up Beta Version..." -ForegroundColor Cyan

$projectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$backendDir = Join-Path $projectRoot "backend"
$frontendDir = Join-Path $projectRoot "frontend"

python --version
if (-not $?) {
    Write-Host "Please install Python." -ForegroundColor Red
    exit 1
}

Write-Host "Setting up Backend..." -ForegroundColor Yellow
Set-Location $backendDir
python -m venv venv
& ".\venv\Scripts\python.exe" -m pip install -r requirements.txt

Write-Host "Setting up Frontend..." -ForegroundColor Yellow
Set-Location $frontendDir
npm install

Set-Location $projectRoot
Write-Host "Setup complete. Launching app..." -ForegroundColor Green
& (Join-Path $projectRoot "start_app.ps1")
