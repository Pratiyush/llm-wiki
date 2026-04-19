---
title: "07 · Example workflows"
type: tutorial
docs_shell: true
---

# 07 · Example workflows

**Time:** 15 minutes total (read) / 1 hour each (do)
**You'll need:** A working wiki with at least 10 ingested sessions.
**Result:** Four concrete, end-to-end workflows you can adapt to your own use case.

---

## Why this matters

The previous six tutorials taught you what the pieces are. This one shows
what they look like stitched together. Pick the workflow that matches
your day-job and copy it.

---

## Workflow 1 — Daily developer loop

**Who:** solo developer using Claude Code for 80 % of their coding.

**Cadence:** one sync / day, one query / few days.

```
Morning:
  (start a coding session in Claude Code, normal work)

End of coding block:
  /wiki-sync

When you need to recall something:
  /wiki-query when did I last look at <topic>?

Weekly:
  /wiki-lint            (spot broken links, orphans)
  /wiki-review          (approve any candidates)
```

**What you get:** an always-current wiki that takes ~30 seconds of
thought per day. The cost of entry is ~5 minutes; the payoff is six
months of "oh yeah, I solved that in April" moments.

---

## Workflow 2 — Team shared wiki

**Who:** a team where multiple people run Claude Code on the same repo.

**Cadence:** each person syncs locally, the wiki gets published to a
shared site via GitHub Pages on every master push.

```
Each dev:
  clone the llm-wiki repo, run ./setup.sh
  /wiki-sync at the end of each work block
  git add wiki/ && git commit -S -m "wiki: <short summary>"
  git push

CI (on master push):
  python3 -m llmwiki build      (GitHub Pages workflow)
  → site/ published to <team>.github.io/llm-wiki

Everyone else:
  bookmark the published URL; search from Cmd+K
```

**Non-destructive merging.** Two devs sync to separate branches, each
gets their own set of `wiki/sources/<project>/<date>-<slug>.md` files.
Merging is conflict-free because every session has a unique timestamp.

**Deploy guide:** **[`deploy/github-pages.md`](../deploy/github-pages.md)**.

---

## Workflow 3 — Bring-your-own Obsidian vault

**Who:** long-time Obsidian user who doesn't want to migrate 500 notes.

**Cadence:** daily sync writing into the existing vault; Obsidian stays
the reading + editing surface.

```
Daily:
  llmwiki sync --vault "~/Documents/Obsidian Vault"

When a new entity lands:
  open Obsidian → navigate to Wiki/Entities/<name>.md → add prose

Next day's sync:
  sees the page, skips rewrite, appends new inbound links under
  ## Connections (idempotent)
```

**What you get:** auto-generated entity pages that become
human-curated over time. Obsidian's graph view + backlinks + full-text
search now cover your llmwiki output without any migration.

**Deep dive:** **[`tutorials/06-bring-your-obsidian-vault.md`](06-bring-your-obsidian-vault.md)**.

---

## Workflow 4 — Personal knowledge base with cost preview

**Who:** someone planning a large one-shot ingest (hundreds of past
sessions) and worried about the API bill if they turn on
Anthropic-backed synthesis later.

**Cadence:** ingest once (dummy backend), preview cost, then decide
whether to enable Ollama or a cloud synthesis backend.

```
1. First sync uses the DummySynthesizer (local, free, canned text):
     llmwiki sync

2. Preview what an Anthropic-backed re-synthesis would cost:
     llmwiki synthesize --estimate

   Output (numbers vary):
     627 new sessions, prefix 3,944 tok
     Model: claude-sonnet-4-6 (first write)
       Prefix:    3,944 tok  $0.0148
       Fresh:     1,274 tok  $0.0038
       Output:    1,000 tok  $0.0150
       Total:                $0.0336
       + 626 subsequent sessions (cache hit):  $17.9484
     Batch total: $17.9820 (model claude-sonnet-4-6)

3. If the number is acceptable, configure a real backend:
     # For local / free: install Ollama + set synthesis.backend = "ollama"
     # For Anthropic: set synthesis.backend = "anthropic" (v1.2+)
     llmwiki synthesize

4. If the number is too high, stay on the DummySynthesizer. Your wiki
   still works end-to-end — pages are just seeded with canned prose
   until you're ready to pay.
```

**Cache-control plumbing** in `llmwiki/cache.py` ensures Anthropic
prompt-caching reuses the stable prefix (CLAUDE.md schema + index +
overview) across every session — that's where the 50-90 % savings
come from.

**References:** **[`reference/prompt-caching.md`](../reference/prompt-caching.md)**.

---

## Pick one

Don't try to run all four. Start with Workflow 1 (solo / daily) for
a week. Move to Workflow 2 (team) when a second person wants in.
Move to Workflow 3 (vault overlay) when you stop touching Obsidian
for three days in a row and feel the split. Stop at Workflow 4 if
you're never going to synthesize against a paid model.

---

## Verify your workflow is working

Three signals:

1. **You answered "wait, didn't I do this before?" with `/wiki-query` at least once this week.**
2. **`/wiki-lint` has 0 errors every time you run it.**
3. **Your session count on the home page is still growing after a month.** (If it plateaus, you've either stopped using the agent or stopped syncing.)

---

## Troubleshooting

**"The wiki feels out of date"** — when did you last `/wiki-sync`? If > 48 h, sync before investigating anything else.

**"The answers are thin"** — you're using the DummySynthesizer. Switch to Ollama (local, free) or configure an Anthropic backend in `synthesis.backend`. See **[`reference/prompt-caching.md`](../reference/prompt-caching.md)**.

**"Orphans keep growing"** — you're creating entity pages faster than you're linking them. Spend 20 minutes with `/wiki-update` to link them into existing sessions.

---

## That's the tutorial series

You're done. The complete set:

- **[01 · Installation](01-installation.md)**
- **[02 · First sync](02-first-sync.md)**
- **[03 · Use with Claude Code](03-use-with-claude-code.md)**
- **[04 · Use with Codex CLI](04-use-with-codex-cli.md)**
- **[05 · Query your wiki](05-querying-your-wiki.md)**
- **[06 · Bring your Obsidian / Logseq vault](06-bring-your-obsidian-vault.md)**
- **[07 · Example workflows](07-example-workflows.md)** ← you are here

---

## Next

→ **[Docs hub](../index.md)** — reference, deployment, contributor guides, style guide, architecture.
