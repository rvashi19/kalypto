$host.ui.RawUI.WindowTitle = "Video Dubbing System Launcher"

$projectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$backendDir = Join-Path $projectRoot "backend"
$frontendDir = Join-Path $projectRoot "frontend"
$pythonExe = Join-Path $backendDir "venv\Scripts\python.exe"
$backendPort = 8010
$frontendPort = 5173

function Stop-ListenerOnPort([int]$Port) {
    $listeners = Get-NetTCPConnection -State Listen -LocalPort $Port -ErrorAction SilentlyContinue |
        Select-Object -ExpandProperty OwningProcess -Unique

    foreach ($listenerPid in $listeners) {
        if ($listenerPid -and $listenerPid -ne $PID) {
            try {
                Stop-Process -Id $listenerPid -Force -ErrorAction Stop
                Write-Host "Stopped existing process $listenerPid on port $Port" -ForegroundColor Yellow
            } catch {
                Write-Host "Unable to stop process $listenerPid on port $Port" -ForegroundColor DarkYellow
            }
        }
    }
}

Stop-ListenerOnPort $backendPort
Stop-ListenerOnPort $frontendPort

Write-Host "Starting Backend..." -ForegroundColor Green
$backendCommand = @"
`$env:PUBLIC_BACKEND_BASE_URL='http://127.0.0.1:$backendPort'
& '$pythonExe' -m uvicorn main:app --host 127.0.0.1 --port $backendPort
"@
Start-Process powershell -WorkingDirectory $backendDir -ArgumentList @(
    "-NoExit",
    "-Command",
    $backendCommand
)

Write-Host "Starting Frontend..." -ForegroundColor Green
$frontendCommand = @"
`$env:VITE_API_BASE_URL='http://127.0.0.1:$backendPort/api'
npx vite --host 127.0.0.1 --port $frontendPort
"@
Start-Process powershell -WorkingDirectory $frontendDir -ArgumentList @(
    "-NoExit",
    "-Command",
    $frontendCommand
)

Write-Host "Frontend: http://127.0.0.1:$frontendPort" -ForegroundColor Cyan
Write-Host "Backend:  http://127.0.0.1:$backendPort" -ForegroundColor Cyan
