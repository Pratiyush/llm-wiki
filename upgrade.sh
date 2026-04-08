#!/usr/bin/env bash
# llmwiki — pull latest from git and re-run setup.
# Usage: ./upgrade.sh
set -eu
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"
echo "==> git pull"
git pull --rebase --autostash || { echo "git pull failed" >&2; exit 1; }
echo "==> re-running setup"
exec bash ./setup.sh
