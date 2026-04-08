@echo off
REM llmwiki — convert new session transcripts to markdown.
REM Usage: sync.bat [--project <sub>] [--since YYYY-MM-DD] [--include-current] [--force] [--dry-run]
cd /d "%~dp0"
python -m llmwiki sync %*
