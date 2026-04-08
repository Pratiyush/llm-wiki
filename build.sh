#!/usr/bin/env bash
# llmwiki — build the static HTML site.
# Usage: ./build.sh [--synthesize] [--out <dir>]
set -eu
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"
exec python3 -m llmwiki build "$@"
