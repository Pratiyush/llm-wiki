#!/usr/bin/env bash
# llmwiki — start a local HTTP server on 127.0.0.1:8765.
# Usage: ./serve.sh [--port N] [--host H] [--open]
set -eu
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"
exec python3 -m llmwiki serve "$@"
