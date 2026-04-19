---
title: "06 · Bring your Obsidian / Logseq vault"
type: tutorial
docs_shell: true
---

# 06 · Bring your Obsidian / Logseq vault

**Time:** 10 minutes
**You'll need:** An existing Obsidian or Logseq vault with real notes in it.
**Result:** llmwiki writes new entity / concept / source pages *inside* your vault at paths you control, never overwriting your existing notes.

---

## Why this matters

If you already have hundreds of Obsidian or Logseq pages, you shouldn't have
to migrate them to llmwiki's `raw/` + `wiki/` tree to get the benefits of
auto-ingested sessions. Vault-overlay mode compiles your vault **in place** —
your existing notes stay untouched, new pages land where you tell them.

---

## Step 1 — Point `llmwiki sync` at your vault

Obsidian:

```bash
python3 -m llmwiki sync --vault "~/Documents/Obsidian Vault"
```

Logseq:

```bash
python3 -m llmwiki sync --vault ~/src/my-logseq-graph
```

Expected opening lines:

```
==> vault: /Users/you/Documents/Obsidian Vault (format: obsidian,
    entities→Wiki/Entities, concepts→Wiki/Concepts)
```

The format is **auto-detected** by directory contents:

| Marker | Format |
|---|---|
| `.obsidian/` | Obsidian |
| `logseq/` or `config.edn` | Logseq |
| neither | Plain (behaves like Obsidian) |

If both `.obsidian/` and `logseq/` exist (happens when you open a Logseq
vault in Obsidian once), Logseq wins.

## Step 2 — Understand where new pages land

Default layout writes under `Wiki/<type>/` at the vault root:

| Page type | Obsidian / Plain | Logseq |
|---|---|---|
| Entity | `Wiki/Entities/RAG.md` | `pages/wiki___entities___RAG.md` |
| Concept | `Wiki/Concepts/Karpathy.md` | `pages/wiki___concepts___Karpathy.md` |
| Source | `Wiki/Sources/2026-session.md` | `pages/wiki___sources___2026-session.md` |
| Synthesis | `Wiki/Syntheses/llm-stack.md` | `pages/wiki___syntheses___llm-stack.md` |
| Candidate | `Wiki/Candidates/NewEntity.md` | `pages/wiki___candidates___NewEntity.md` |

Obsidian wikilinks are bare slugs: `[[RAG]]`. Logseq wikilinks are
namespace-aware: `[[wiki/entities/RAG]]`. llmwiki writes the correct
format for your vault without you thinking about it.

## Step 3 — Trust the non-destructive default

Run sync twice. The second run **never overwrites** an existing page:

```
==> wrote 14 entity pages (12 new, 2 skipped: already exist)
==> appended to 5 existing pages under ## Connections
```

Under the hood:

- **New page** → written (no conflict).
- **Existing page** → sync reads frontmatter + body. If it can add new
  inbound wikilinks under `## Connections`, it does so **idempotently**
  (re-running doesn't duplicate). Your prose stays intact.
- **Force overwrite** → `--allow-overwrite` flag, which announces itself
  loudly: `--allow-overwrite: existing vault pages may be clobbered`.

## Step 4 — The round-trip safety loop

The workflow that makes vault-overlay actually worth using:

1. llmwiki writes `Wiki/Entities/RAG.md` with basic frontmatter + a two-line description.
2. You open Obsidian, add prose, rearrange headings, link to five more pages.
3. Next `llmwiki sync --vault`:
   - Sees the page already exists → **skips the write**.
   - Finds new `[[RAG]]` mentions in newly-synthesised sources → appends them under your existing `## Connections` heading (idempotent).
   - Your prose stays intact.

You can now use Obsidian's graph view + backlinks + full-text search
over your llmwiki output without any migration.

## Step 5 — (Optional) Build a static site from the vault

```bash
python3 -m llmwiki build --vault ~/my-vault --out ~/my-vault-site
```

This compiles pages *from* the vault into a gitignorable static site
under `~/my-vault-site/`. Same `site/graph.html`, `search-index.json`,
per-page `.txt` / `.json` siblings.

---

## Python API

If you're scripting:

```python
from pathlib import Path
from llmwiki.vault import (
    append_section,
    format_wikilink,
    resolve_vault,
    vault_page_path,
    write_vault_page,
)

vault = resolve_vault(Path("~/my-vault").expanduser())

# Where should a new entity land?
path = vault_page_path(vault, "entities", "RAG")

# Write it — raises FileExistsError on clobber by default
write_vault_page(path, "# RAG\n\nRetrieval-augmented generation.\n")

# Append to a user-owned page without rewriting
session = vault_page_path(vault, "sources", "2026-session")
link = format_wikilink(vault, "entities", "RAG")
append_section(session, "Connections", f"- {link}")
```

Full reference: **[`docs/guides/existing-vault.md`](../guides/existing-vault.md)**.

---

## Verify

```bash
python3 -m llmwiki sync --vault ~/my-vault --dry-run
ls "~/my-vault/Wiki/Entities" | head -5
cat "~/my-vault/Wiki/Entities/Some-Page.md" | head -10
```

---

## Troubleshooting

**"vault directory does not exist"** — typo in path, or shell didn't expand `~`. Quote the path: `--vault "~/Obsidian Vault"`.

**Detected as Plain, not Obsidian** — the `.obsidian/` marker is missing. Open the folder in Obsidian once to create it, then retry.

**`FileExistsError` on every page** — your vault already has pages at the default paths. Either use `--allow-overwrite` (bulk re-ingest) or keep the existing pages and let `append_section` merge new info.

**Logseq pages landing under `Wiki/…` instead of `pages/…`** — your Logseq config is in a non-standard location. Ensure a `logseq/` subdir or root-level `config.edn` exists.

---

## Non-goals (intentional)

- Bidirectional `raw/` sync — session transcripts stay in the repo-local `raw/sessions/`, not inside your vault. Keeps auto-generated junk out of your notes.
- Parsing Logseq `config.edn` for non-default `pages/` — detection is marker-only.
- Flat-namespace filenames for Obsidian users.

All three are explicit follow-ups if demand emerges.

---

## Next

→ **[07 · Example workflows](07-example-workflows.md)** — four real, end-to-end use cases.
