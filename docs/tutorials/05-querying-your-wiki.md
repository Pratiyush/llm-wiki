---
title: "05 · Query your wiki"
type: tutorial
docs_shell: true
---

# 05 · Query your wiki

**Time:** 10 minutes
**You'll need:** A wiki with at least one ingested session ([tutorial 02](02-first-sync.md)).
**Result:** Fluency with the nine slash commands that make a wiki worth having — ask questions, inspect the graph, lint for rot, review candidates.

---

## Why this matters

llmwiki isn't about the ingest. The ingest is one-time. The payoff is when
you ask **"have I solved this before?"** and get a confident answer grounded
in your own session history. Every command below is designed for that loop.

---

## The nine slash commands

Each command is backed by a single Markdown file under `.claude/commands/`
that documents what it does. Claude Code renders the docstring when you
type `/`.

| Command | Does |
|---|---|
| `/wiki-sync` | Convert new sessions → markdown → ingest → auto-build |
| `/wiki-ingest <path>` | Ingest one source or folder into `wiki/` |
| `/wiki-query <q>` | Answer a question from the wiki |
| `/wiki-review` | Triage pending candidates (promote / merge / discard) |
| `/wiki-lint` | Run 13 structural + LLM-powered lint rules |
| `/wiki-graph` | Build the interactive knowledge graph |
| `/wiki-build` | Regenerate `site/` |
| `/wiki-serve` | Start the local HTTP server |
| `/wiki-update <page>` | Surgically edit one wiki page |
| `/wiki-reflect` | Higher-order pass — find gaps, suggest new pages |

They share one rule: **nothing destructive without explicit intent**. No
slash command ever rewrites a file you own without prompting first.

---

## Query workflow

### 1. Ask

```
/wiki-query which lint rules exist today and when were they added?
```

Under the hood, Claude Code:

1. Reads `wiki/index.md` + `wiki/overview.md` (and any `cache_tier: L1` pages).
2. Reads relevant `_context.md` stubs from sub-folders before descending.
3. Opens the candidate source / entity / concept pages.
4. Synthesises an answer with inline `[[wikilinks]]` to every source.

### 2. Save the answer (if it's worth keeping)

Claude Code will prompt: *"Save to `wiki/syntheses/lint-rules-timeline.md`?"*
Yes → the answer becomes a first-class wiki page searchable next time.

### 3. Cross-check with the graph

```
/wiki-graph
open site/graph.html
```

The graph viewer shows every `[[wikilink]]` as an edge. Type in the search
box to highlight — if your new answer is central to many sessions, it'll be
a hub. If it's floating on the edge with no inbound links, the ingest
missed something.

---

## Lint workflow

```
/wiki-lint
```

Output (live example):

```
== 28 issues: 0 errors, 22 warnings, 6 info

## link_integrity (22)
  [warning] entities/GPT5.md: broken wikilink [[MultimodalModels]]
  ...
## orphan_detection (6)
  [info] entities/ClaudeSonnet4.md: orphan page
  ...
## cache_tier_consistency (0)
## stale_candidates (0)
```

What to fix:

- **Errors (0 required for a clean state)** — frontmatter missing required
  fields, invalid enum values. Fix immediately.
- **Warnings** — broken wikilinks mostly. Either create the target page or
  remove the `[[link]]`.
- **Info** — orphans + aged candidates. Investigate, don't auto-fix.

See **[`docs/reference/cache-tiers.md`](../reference/cache-tiers.md)** for the cache-tier
consistency rule and **[`docs/testing/visual-regression.md`](../testing/visual-regression.md)** for the
stale-candidates rule.

---

## Review workflow

When `/wiki-ingest` discovers a possibly-new entity (e.g. a company it
hasn't seen before), it drops a candidate file rather than writing
directly to `wiki/entities/`.

```
/wiki-review
```

For each candidate, Claude Code offers three actions:

- **promote** → moves to `wiki/entities/<Name>.md`, sets `status: reviewed`
- **merge** → appends into an existing page under `## Candidate merge — <date>`
- **discard** → moves to `wiki/archive/candidates/<timestamp>/` with a reason file

All three are non-destructive; `llmwiki candidates list` on the CLI shows
the same queue without the chat.

---

## Verify

```bash
python3 -m llmwiki candidates list                    # pending candidates
python3 -m llmwiki lint                               # same as /wiki-lint, plain CLI
python3 -m llmwiki graph && ls graph/                 # graph.json + graph.html
```

---

## Troubleshooting

**`/wiki-query` answers from stale data** — you haven't run `/wiki-sync` since
your latest session. Do that first; it rebuilds `overview.md`.

**Lint reports the same orphan every day** — orphans aren't errors, they're
signal. Either link the page from somewhere (`/wiki-update`) or remove it if
it's no longer useful.

**`/wiki-review` shows candidates you thought you'd merged** — check
`wiki/candidates/<kind>/` — the file is still there. The slash command may
have failed partway; run `python3 -m llmwiki candidates list` to see the
canonical queue.

---

## Next

→ **[06 · Bring your Obsidian / Logseq vault](06-bring-your-obsidian-vault.md)** — point llmwiki at an existing vault so you don't have to migrate.
