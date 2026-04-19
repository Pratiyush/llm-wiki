#!/usr/bin/env bash
# Demo recording script for asciinema
# Simulates a user running the full llm-wiki workflow
# Usage: asciinema rec demo.cast --command "bash scripts/demo-record.sh" --cols 100 --rows 30

set -e
cd "$(dirname "$0")/.."

# Helper: type commands slowly for visual effect
type_cmd() {
    echo ""
    echo -n "$ "
    for (( i=0; i<${#1}; i++ )); do
        echo -n "${1:$i:1}"
        sleep 0.04
    done
    echo ""
    sleep 0.3
}

pause() { sleep "${1:-1.5}"; }

clear
echo "╔══════════════════════════════════════════════════════╗"
echo "║  llm-wiki — Turn AI coding sessions into a wiki     ║"
echo "║  github.com/Pratiyush/llm-wiki                      ║"
echo "╚══════════════════════════════════════════════════════╝"
pause 2

# 1. Version + adapters
type_cmd "llmwiki --version"
python3 -m llmwiki --version
pause

type_cmd "llmwiki adapters"
python3 -m llmwiki adapters
pause 2

# 2. Sync sessions
type_cmd "llmwiki sync --dry-run"
python3 -m llmwiki sync --dry-run
pause 2

# 3. Build the site
type_cmd "llmwiki build"
python3 -m llmwiki build 2>&1
pause 2

# 4. Show what was generated
type_cmd "ls site/ | head -15"
ls site/ | head -15
pause

type_cmd "echo \"Total HTML pages:\" && find site -name '*.html' | wc -l"
echo "Total HTML pages:" && find site -name '*.html' | wc -l
pause

# 5. Show exports
type_cmd "head -20 site/llms.txt"
head -20 site/llms.txt
pause 2

# 6. Show project breakdown
type_cmd "ls raw/sessions/ | head -10"
ls raw/sessions/ | head -10
pause

# 7. v1.1 — Preview API cost before synthesis (#50)
type_cmd "llmwiki synthesize --estimate"
python3 -m llmwiki synthesize --estimate 2>&1 | head -12
pause 2

# 8. v1.1 — List candidate pages awaiting human review (#51)
type_cmd "llmwiki candidates list"
python3 -m llmwiki candidates list 2>&1 || echo "  (no candidates pending)"
pause 2

# 9. Start server
type_cmd "llmwiki serve --port 8765 &"
python3 -m llmwiki serve --port 8765 &
SERVER_PID=$!
sleep 1
echo "→ Server running at http://localhost:8765"
pause 2

# 10. Wrap up
type_cmd "# Browse to localhost:8765 to explore your wiki!"
echo "Features: heatmap, token stats, tool charts, model directory,"
echo "          search (Cmd+K), dark mode, AI exports (llms.txt, JSON-LD),"
echo "          interactive graph (Graph tab), candidates workflow,"
echo "          Ollama-ready synthesis pipeline."
pause 2

echo ""
echo "★ Star the repo: github.com/Pratiyush/llm-wiki"
echo "★ Live demo: pratiyush.github.io/llm-wiki"
pause 2

# Cleanup
kill $SERVER_PID 2>/dev/null || true
