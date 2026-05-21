@echo off
title LLM-Wiki

echo ============================
echo   LLM-Wiki Start
echo ============================
echo.

REM --- Check Python ---
where python >nul 2>nul
if %errorlevel% neq 0 (
    echo [ERROR] Python not found. Install Python 3.12+
    echo   https://www.python.org/downloads/
    pause
    exit /b 1
)

REM --- Check venv ---
if not exist ".venv\Scripts\activate.bat" (
    echo [INFO] Creating venv...
    python -m venv .venv
    call .venv\Scripts\activate.bat
    echo [INFO] Installing dependencies...
    pip install -e ".[web]" --quiet
) else (
    call .venv\Scripts\activate.bat
)

REM --- Check .env ---
if not exist ".env" (
    echo [WARN] .env not found! See DEPLOY.md
    echo.
    pause
    exit /b 1
)

REM --- Start ---
echo.
echo [START] http://0.0.0.0:8765
echo [HINT]  LAN users: http://YOUR_IP:8765
echo [HINT]  Ctrl+C to stop
echo.

python -m llmwiki web --host 0.0.0.0 --port 8765
pause
