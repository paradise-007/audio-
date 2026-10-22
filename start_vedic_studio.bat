@echo off
chcp 65001 >nul
title Vedic Voice Studio


echo ========================================================
echo   [Vedic Voice Studio] Vedic Voice Studio
echo ========================================================
echo.

set "SCRIPT_DIR=%~dp0"
set "VOICEBOX_DIR=%SCRIPT_DIR%voicebox"
set "PYTHON=%VOICEBOX_DIR%\backend\venv\Scripts\python.exe"

if not exist "%PYTHON%" (
    echo [ERROR] Voicebox virtual environment not found at:
    echo "%PYTHON%"
    pause
    exit /b 1
)

echo [1/2] Launching Vedic Voice Studio UI in browser...
start "" "http://127.0.0.1:8000/vedic"

echo [2/2] Starting Voicebox backend server on http://127.0.0.1:8000 ...
cd /d "%VOICEBOX_DIR%"
"%PYTHON%" -m backend.main --host 127.0.0.1 --port 8000

pause
