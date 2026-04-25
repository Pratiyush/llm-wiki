---
title: "00 · Quickstart Walkthrough"
type: tutorial
docs_shell: true
---

# 00 · Quickstart Walkthrough

**Time:** 15 minutes

**You'll need:** Python 3.9+, pip, Claude Code installed.

**Result:** A working wiki with knowledge graph, HTML site, Obsidian export, and AI-consumable outputs.

## Why this matters

This walks through every feature using `/wiki-*` slash commands from Claude Code. Each step builds on the previous.

---

## 1. Install

```bash
cd ~/Desktop/2026/production-draft/llm-wiki
pip install ".[graph]"
```

Verify:

```
llmwiki --version
# -> llmwiki 1.2.0
```

---

## 2. Scaffold

Run `/wiki-init` in Claude Code. This creates:

```
raw/sessions/     <- immutable session transcripts
wiki/sources/     <- one summary per source
wiki/entities/    <- people, projects, tools
wiki/concepts/    <- ideas, patterns, decisions
wiki/syntheses/   <- saved query answers
site/             <- generated HTML
```

Plus 8 seed files: `index.md`, `overview.md`, `log.md`, `MEMORY.md`, `SOUL.md`, `CRITICAL_FACTS.md`, `hints.md`, `hot.md`.

---

## 3. Sync sessions

Run `/wiki-sync`. This discovers your Claude Code and Codex CLI sessions, converts them to markdown, and ingests them into the wiki.

Expected output:

```
==> adapter: claude_code
  discovered: 487 source files
==> adapter: codex_cli
  discovered: 2 source files
summary: 488 converted, 0 unchanged, ...
```

Check status anytime:

```
llmwiki sync --status
```

---

## 4. Knowledge graph

Run `/wiki-graph`. Graphify (AI-powered) runs by default:

```
graphify: 1432 nodes, 875 edges
graphify: 871 communities detected
graphify: 61 hyperedges attached
graphify: wrote graphify-out/graph.json
graphify: wrote graphify-out/graph.html
graphify: wrote graphify-out/graph.svg
graphify: wrote graphify-out/GRAPH_REPORT.md
```

Open the interactive graph:

```bash
open graphify-out/graph.html
```

Read the analysis report:

```bash
head -50 graphify-out/GRAPH_REPORT.md
```

Query the graph:

```
llmwiki query "what projects is Pratiyush working on"
```

---

## 5. Build the site

Run `/wiki-build`:

```
==> build complete: 1364 HTML files, ~200 MB
```

---

## 6. Browse the site

Run `/wiki-serve`. Opens http://127.0.0.1:8765

**What to explore:**
- **Home** — project cards with session counts and activity heatmap
- **Projects** — click into any project to see its sessions
- **Sessions** — sortable table of every session
- **Graph** — interactive knowledge graph (click nodes to explore)
- **Docs** — tutorials, guides, reference
- **Search** — press Cmd+K to search anything

---

## 7. Quality check

Run `/wiki-lint`:

```
scanned 1269 pages
2358 issues: 1 errors, 1187 warnings, 1170 info
```

Key rules:
- `link_integrity` — finds broken [[wikilinks]]
- `orphan_detection` — pages with no inbound links
- `duplicate_detection` — near-duplicate pages
- `frontmatter_completeness` — missing metadata

---

## 8. Ask the wiki

Run `/wiki-query "what is the architecture of llm-wiki?"`. Claude reads the relevant wiki pages and synthesizes an answer with [[wikilink]] citations.

---

## 9. Exports

All AI-consumable formats are built automatically with `/wiki-build`. You can also export individually:

```
llmwiki export llms-txt        # machine-readable index
llmwiki export llms-full-txt   # full text corpus (2.2 MB)
llmwiki export jsonld           # schema.org graph
llmwiki export sitemap          # sitemap.xml (1,276 URLs)
llmwiki export rss              # RSS feed (50 items)
llmwiki export marp             # slide deck
llmwiki export all              # everything
```

---

## 10. Export to Obsidian

After building the graph, export to your Obsidian vault:

```python
python3 -c "
from llmwiki.graphify_bridge import export_to_obsidian
from pathlib import Path
export_to_obsidian(Path.home() / 'Documents/Obsidian Vault/Temp/Graph')
"
```

Open `~/Documents/Obsidian Vault/Temp/` in Obsidian:
- Press **Cmd+G** for graph view
- Open `graph.canvas` for spatial layout
- Browse `_COMMUNITY_*.md` pages for topic clusters

---

## Verify

Quick sanity check:

```bash
llmwiki --version              # prints version
llmwiki adapters               # 2 core adapters
llmwiki sync --status          # last sync time
ls site/index.html             # site exists
ls graphify-out/GRAPH_REPORT.md # graph exists
```

---

## Troubleshooting

| Problem | Fix |
|---|---|
| `command not found: llmwiki` | Run `pip install ".[graph]"` from the repo root |
| `graphifyy not installed` | Run `pip install ".[graph]"` |
| `0 sessions discovered` | Check `~/.claude/projects/` has `.jsonl` files |
| `build` produces 0 HTML | Run `/wiki-sync` first |
| Obsidian vault empty | Run `/wiki-graph` first to create `graphify-out/graph.json` |

---

## Next

- **[01 · Installation](01-installation.md)** — detailed install guide
- **[02 · First sync](02-first-sync.md)** — deep dive into session conversion
- **[06 · Bring your Obsidian vault](06-bring-your-obsidian-vault.md)** — vault overlay mode
- **[08 · Synthesize with Ollama](08-synthesize-with-ollama.md)** — LLM-powered synthesis
