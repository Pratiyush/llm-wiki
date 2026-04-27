Output "/tmp/demovhs/tutorial.gif"
Output "/tmp/demovhs/tutorial.webm"

Set Shell "bash"
Set FontSize 16
Set Width 1280
Set Height 800
Set Theme "Catppuccin Mocha"
Set TypingSpeed 40ms
Set PlaybackSpeed 1.0

# ── Hidden setup: real PS1, fresh sandbox, clear ──────────────
Hide
Type 'export PS1="$ "'
Enter
Type 'export TERM=xterm-256color'
Enter
Type "rm -rf /tmp/demovhs/sandbox && mkdir -p /tmp/demovhs/sandbox && cd /tmp/demovhs/sandbox"
Enter
Type "printf '\\033c'"
Enter
Sleep 200ms
Show

# ── 1. init ──────────────────────────────────────────────────
Type "# llmwiki — every command in 90 seconds"
Sleep 600ms
Enter
Type "# 1. Scaffold a fresh vault"
Sleep 300ms
Enter
Type "llmwiki init"
Sleep 300ms
Enter
Sleep 2500ms

# ── 2. adapters ──────────────────────────────────────────────
Type "# 2. Which adapters can see your sessions on this machine?"
Sleep 300ms
Enter
Type "llmwiki adapters"
Sleep 300ms
Enter
Sleep 3500ms

# ── 3. sync --dry-run ────────────────────────────────────────
Type "# 3. Pull in sessions  (dry-run for the demo)"
Sleep 300ms
Enter
Type "llmwiki sync --help | head -12"
Sleep 300ms
Enter
Sleep 3500ms

# ── 4. build ─────────────────────────────────────────────────
Type "# 4. Build the static site"
Sleep 300ms
Enter
Type "llmwiki build"
Sleep 300ms
Enter
Sleep 3500ms

# ── 5. lint ──────────────────────────────────────────────────
Type "# 5. Lint  — 16 rules: orphans, broken links, stale pages…"
Sleep 300ms
Enter
Type "llmwiki lint"
Sleep 300ms
Enter
Sleep 4000ms

# ── 6. all (one-shot pipeline) ───────────────────────────────
Type "# 6. One-shot: build + graph + export all + lint"
Sleep 300ms
Enter
Type "llmwiki all"
Sleep 300ms
Enter
Sleep 6000ms

# ── 7. serve + smoke test ────────────────────────────────────
Type "# 7. Browse it locally"
Sleep 300ms
Enter
Hide
Type "(llmwiki serve --port 8989 >/tmp/serve.log 2>&1 &) ; sleep 1"
Enter
Sleep 1500ms
Show
Type "curl -sI http://127.0.0.1:8989/ | head -1"
Sleep 300ms
Enter
Sleep 1500ms
Hide
Type "pkill -f 'llmwiki serve' 2>/dev/null"
Enter
Sleep 300ms
Show

# ── 8. closer ────────────────────────────────────────────────
Type "# Done — pip install llm-notebook"
Sleep 400ms
Enter
Sleep 2500ms
