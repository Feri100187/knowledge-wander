@echo off
setlocal
cd /d "%~dp0backend"

if not exist ".venv\Scripts\python.exe" (
    echo [ERROR] backend virtual environment not found.
    echo Please create backend\.venv first.
    pause
    exit /b 1
)

".venv\Scripts\python.exe" run_local.py
set "EXIT_CODE=%ERRORLEVEL%"

if not "%EXIT_CODE%"=="0" (
    echo.
    echo [ERROR] Backend exited with code %EXIT_CODE%.
)

pause
exit /b %EXIT_CODE%
