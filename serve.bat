@echo off
REM llmwiki — start a local HTTP server on 127.0.0.1:8765.
REM Usage: serve.bat [--port N] [--host H] [--open]
cd /d "%~dp0"
python -m llmwiki serve %*
