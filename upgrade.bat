@echo off
REM llmwiki — pull latest from git and re-run setup.
cd /d "%~dp0"
echo ==^> git pull
git pull --rebase --autostash
if errorlevel 1 (
  echo git pull failed
  exit /b 1
)
call setup.bat
