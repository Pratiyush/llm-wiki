---
title: "02 · First sync"
type: tutorial
docs_shell: true
---

# 02 · First sync

**Time:** 5 minutes
**You'll need:** A working `llmwiki` CLI ([tutorial 01](01-installation.md)) and session history from at least one AI-coding agent.
**Result:** A browsable static site at `http://127.0.0.1:8765` listing every session you've ever run.

---

## Why this matters

llmwiki turns dormant JSONL transcripts into a searchable wiki. The first
sync is the "aha" moment: minutes after install, you can browse sessions
you'd forgotten you ran last month.

---

## Step 1 — Dry-run first

A dry-run shows you exactly what will be written without touching disk:

```bash
python3 -m llmwiki sync --dry-run
```

Expected output (numbers vary):

```
==> claude_code: found 647 sessions, 93 sub-agents
==> codex_cli: found 18 sessions
[dry-run] Would write 665 markdown files under raw/sessions/
```

> **Trusted.** Nothing is written. Re-run without `--dry-run` when you're happy.

## Step 2 — Run the real sync

```bash
python3 -m llmwiki sync
```

Expected ending:

```
✓ wrote 665 session pages under raw/sessions/
✓ ingested into wiki/ (30 projects, 647 sources)
✓ auto-build: wrote site/ (687 HTML files, 61 MB)
```

`raw/` is immutable (never hand-edit). `wiki/` is where your agent's
output lives. `site/` is the browsable static site.

## Step 3 — Serve the site

```bash
python3 -m llmwiki serve
```

Output:

```
Serving site/ at http://127.0.0.1:8765
```

Open that URL. You'll see:

- **Home** — project grid + activity heatmap
- **Projects** — one card per project, freshness badge
- **Sessions** — sortable table of every session
- **Graph** — interactive force-directed knowledge graph
- **Search** — Cmd+K command palette, fuzzy match across every page

## Step 4 — (Optional) Cost preview before running synthesis

```bash
python3 -m llmwiki synthesize --estimate
```

Output (numbers vary):

```
627 new sessions, prefix 3,944 tok
Model: claude-sonnet-4-6 (first write)
  Prefix:    3,944 tok  $0.0148
  ...
Batch total: $17.98 (model claude-sonnet-4-6)
```

Nothing is called. Numbers are pre-spend estimates using the rate card
in `llmwiki/cache.py`. Actual numbers come back in `usage` on each API
response.

---

## Verify

From the terminal:

```bash
ls wiki/sources | wc -l                        # ≥ 1
ls site/sessions | wc -l                       # ≥ 1
curl -sI http://127.0.0.1:8765/ | head -1      # HTTP/1.0 200 OK
```

From the browser: click into any project → any session → every inline
code block is syntax-highlighted, every `[[wikilink]]` resolves.

---

## Troubleshooting

**`no sources found`** — `python3 -m llmwiki adapters` must show at least one `configured ✓`. If every line says `-`, the agent hasn't created sessions in the standard paths yet. Run the agent once and retry.

**`Permission denied` on `~/.claude/projects/`** — the adapter reads; it never writes. Check file permissions: `ls -la ~/.claude/projects/ | head -3`.

**Site loads but is empty** — you ran `sync --dry-run`. Re-run without the flag.

**Port 8765 already in use** — `python3 -m llmwiki serve --port 9000` picks a different port.

---

## Next

→ **[03 · Use with Claude Code](03-use-with-claude-code.md)** — the slash-command workflow that keeps your wiki fresh without you thinking about it.
