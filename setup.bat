@echo off
REM llmwiki — one-click installer for Windows.
REM Usage: setup.bat
REM Idempotent — safe to re-run.

setlocal enabledelayedexpansion
cd /d "%~dp0"

echo ==^> llmwiki setup
echo     root: %cd%

REM 1. Python check
where python >nul 2>&1
if errorlevel 1 (
  echo error: python is required but was not found in PATH
  exit /b 1
)
for /f "delims=" %%v in ('python -c "import sys; print(\".\".join(map(str, sys.version_info[:2])))"') do set PY_VER=%%v
echo     python: !PY_VER!

REM 2. Check for markdown
python -c "import markdown" 2>nul
if errorlevel 1 (
  echo ==^> installing python 'markdown' (required)
  python -m pip install --user --quiet markdown
)

REM 3. Syntax highlighting (v0.5): highlight.js loads from CDN at view time,
REM    so there is no longer an optional Python dep to install here.

REM 4. Scaffold raw/ wiki/ site/
python -m llmwiki init

REM 5. Show available adapters
python -m llmwiki adapters

REM 6. First sync (dry-run)
echo.
echo ==^> dry-run of first sync:
python -m llmwiki sync --dry-run

echo.
echo ================================================================
echo   Setup complete.
echo ================================================================
echo.
echo Next steps:
echo   sync.bat                    ^-^- convert new sessions to markdown
echo   build.bat                   ^-^- generate the static HTML site
echo   serve.bat                   ^-^- browse at http://127.0.0.1:8765/
