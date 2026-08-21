@echo off
setlocal EnableExtensions

set "ROOT=%~dp0"
set "BACKEND=%ROOT%backend"
set "FRONTEND=%ROOT%frontend"
set "PYTHON=%BACKEND%\.venv\Scripts\python.exe"
set "FRONTEND_URL=http://localhost:3000"

if not exist "%PYTHON%" (
    echo [ERROR] backend\.venv\Scripts\python.exe not found.
    echo Please create the backend virtual environment first.
    pause
    exit /b 1
)

if not exist "%BACKEND%\run_local.py" (
    echo [ERROR] backend\run_local.py not found.
    pause
    exit /b 1
)

if not exist "%FRONTEND%\package.json" (
    echo [ERROR] frontend\package.json not found.
    pause
    exit /b 1
)

if not exist "%FRONTEND%\node_modules\" (
    echo [ERROR] frontend\node_modules not found.
    echo Run npm install in frontend first.
    pause
    exit /b 1
)

where npm >nul 2>&1
if errorlevel 1 (
    echo [ERROR] npm was not found on PATH.
    echo Please install Node.js and npm first.
    pause
    exit /b 1
)

echo [INFO] Starting Knowledge Wander Backend...
start "Knowledge Wander Backend" /D "%BACKEND%" cmd /k ""%PYTHON%" run_local.py"

echo [INFO] Starting Knowledge Wander Frontend...
start "Knowledge Wander Frontend" /D "%FRONTEND%" cmd /k "npm run dev"

echo [INFO] Waiting for Frontend at %FRONTEND_URL% ...
powershell.exe -NoProfile -ExecutionPolicy Bypass -Command "$deadline = (Get-Date).AddSeconds(60); while ((Get-Date) -lt $deadline) { try { $response = Invoke-WebRequest -UseBasicParsing -Uri '%FRONTEND_URL%' -TimeoutSec 2; if ($response.StatusCode -ge 200 -and $response.StatusCode -lt 400) { exit 0 } } catch { } Start-Sleep -Seconds 1 }; exit 1"

if errorlevel 1 (
    echo [ERROR] Frontend did not become ready in time.
    echo Backend and frontend windows were left running.
    pause
    exit /b 1
)

echo [INFO] Frontend is ready. Opening %FRONTEND_URL% ...
start "" "%FRONTEND_URL%"

endlocal
exit /b 0
