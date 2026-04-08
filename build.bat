@echo off
REM llmwiki — build the static HTML site.
REM Usage: build.bat [--synthesize] [--out <dir>]
cd /d "%~dp0"
python -m llmwiki build %*
