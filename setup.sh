#!/usr/bin/env bash
# llmwiki — one-click installer for macOS / Linux.
#
# Usage: ./setup.sh
# Idempotent — safe to re-run.

set -eu
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "==> llmwiki setup"
echo "    root: $SCRIPT_DIR"

# 1. Python check
if ! command -v python3 >/dev/null 2>&1; then
  echo "error: python3 is required but was not found in PATH" >&2
  exit 1
fi
PY_VER=$(python3 -c 'import sys; print(".".join(map(str, sys.version_info[:2])))')
echo "    python: $PY_VER"

# 2. Check for markdown package
# #sec-18 (#562): pin to the same version floor as pyproject.toml so a
# fresh setup never installs a markdown wheel older than llmwiki's
# tested baseline. Bump both files together when the floor moves.
if ! python3 -c "import markdown" 2>/dev/null; then
  echo "==> installing python 'markdown' (required)"
  python3 -m pip install --user --quiet 'markdown>=3.9' 2>&1 | tail -2 || true
fi

# 3. Syntax highlighting (v0.5): highlight.js loads from CDN at view time,
#    so there is no longer an optional Python dep to install here.

# 4. Scaffold raw/ wiki/ site/
python3 -m llmwiki init

# 5. Show available adapters
python3 -m llmwiki adapters

# 6. First sync (status probe so users see how many sessions exist
#    without actually converting them yet)
echo
echo "==> sync status:"
python3 -m llmwiki sync --status || true

echo
echo "================================================================"
echo "  Setup complete."
echo "================================================================"
echo
echo "Next steps:"
echo "  ./sync.sh                   # convert new sessions to markdown"
echo "  ./build.sh                  # generate the static HTML site"
echo "  ./serve.sh                  # browse at http://127.0.0.1:8765/"
echo
echo "Optional SessionStart hook — auto-sync on every Claude Code launch:"
echo "  Add this to ~/.claude/settings.json under 'hooks':"
echo '    "SessionStart": [ { "hooks": [ { "type": "command",'
# #sec-11 (#555): wrap the path in JSON-string-escaped quotes so a user
# whose checkout sits under "/Users/some path/llmwiki" still gets a
# valid hook entry. Without quotes the shell splits on the space, the
# python invocation runs against `/Users/some` and the trailing
# `path/...` becomes a separate argv. Paste-friendly + correct.
echo "      \"command\": \"(python3 \\\"$SCRIPT_DIR/llmwiki/convert.py\\\" > /tmp/llmwiki-sync.log 2>&1 &) ; exit 0\" } ] } ]"
