#!/usr/bin/env bash
# llmwiki — convert new session transcripts to markdown.
# Usage: ./sync.sh [--project <substring>] [--since YYYY-MM-DD] [--include-current] [--force] [--dry-run]
set -eu
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"
exec python3 -m llmwiki sync "$@"
