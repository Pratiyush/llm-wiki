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
if ! python3 -c "import markdown" 2>/dev/null; then
  echo "==> installing python 'markdown' (required)"
  python3 -m pip install --user --quiet markdown 2>&1 | tail -2 || true
fi

# 3. Optional: pygments for syntax highlighting
if ! python3 -c "import pygments" 2>/dev/null; then
  echo "==> installing python 'pygments' (optional, for syntax highlighting)"
  python3 -m pip install --user --quiet pygments 2>&1 | tail -2 || true
fi

# 4. Scaffold raw/ wiki/ site/
python3 -m llmwiki init

# 5. Show available adapters
python3 -m llmwiki adapters

# 6. First sync (dry-run so users see what would happen)
echo
echo "==> dry-run of first sync:"
python3 -m llmwiki sync --dry-run || true

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
echo "      \"command\": \"(python3 $SCRIPT_DIR/llmwiki/convert.py > /tmp/llmwiki-sync.log 2>&1 &) ; exit 0\" } ] } ]"
