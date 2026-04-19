# Running llmwiki on an existing Obsidian / Logseq vault

> Status: shipped in v1.2.0 (#54). Use `llmwiki sync --vault <path>`
> to point the pipeline at an existing knowledge vault instead of the
> repo's `wiki/` directory.

Already have hundreds of Obsidian or Logseq pages? You don't have to
migrate them. llmwiki can **read + write inside the vault in place**:

- Session transcripts still land in the repo's local `raw/sessions/`
  (so the vault isn't polluted with auto-generated junk).
- New entity / concept / source / synthesis pages the pipeline
  creates land **inside the vault** at paths you configure.
- Wikilinks respect the vault's format (Obsidian bare slugs, Logseq
  namespace paths).
- Your existing pages are **never overwritten** unless you pass
  `--allow-overwrite`. When llmwiki wants to merge new info into a
  page you own, it appends under a `## Connections` heading.

## Quick start

```bash
# Obsidian vault at ~/Documents/Obsidian Vault
llmwiki sync --vault "~/Documents/Obsidian Vault"

# Logseq vault
llmwiki sync --vault ~/src/my-logseq-graph
```

Output you'll see:

```
==> vault: /Users/you/Documents/Obsidian Vault (format: obsidian,
    entities→Wiki/Entities, concepts→Wiki/Concepts)
...
```

If the path doesn't exist or isn't a directory, llmwiki fails fast
with a clear error (exit code 2).

## Format detection

llmwiki auto-detects the vault format from its contents — no config
file required:

| Marker | Format |
|---|---|
| `logseq/` dir **or** `config.edn` at root | Logseq |
| `.obsidian/` dir | Obsidian |
| Neither | Plain (treated as Obsidian-like) |

Logseq wins when both markers exist (it's the more specific marker;
the `.obsidian/` dir can sneak in if you open a Logseq vault in
Obsidian once).

## Where new pages land

Default layout writes under `Wiki/<type>/` at the vault root:

| Page type | Obsidian / Plain | Logseq |
|---|---|---|
| Entity | `Wiki/Entities/RAG.md` | `pages/wiki___entities___RAG.md` |
| Concept | `Wiki/Concepts/Karpathy.md` | `pages/wiki___concepts___Karpathy.md` |
| Source | `Wiki/Sources/2026-session.md` | `pages/wiki___sources___2026-session.md` |
| Synthesis | `Wiki/Syntheses/llm-stack.md` | `pages/wiki___syntheses___llm-stack.md` |
| Candidate | `Wiki/Candidates/NewEntity.md` | `pages/wiki___candidates___NewEntity.md` |

**Obsidian / Plain** — nested folders, filename preserves slug casing,
wikilinks are bare: `[[RAG]]`.

**Logseq** — flat `pages/` directory, filenames use Logseq's triple-
underscore namespace convention (`wiki___entities___RAG.md` is the
page `wiki/entities/RAG`), wikilinks include the namespace:
`[[wiki/entities/RAG]]`.

### Customising the layout

If your vault already uses a different convention (e.g. everything
under `LLM/` instead of `Wiki/`, or people under `Knowledge/People/`),
pass a custom `VaultLayout` when calling the Python API:

```python
from pathlib import Path
from llmwiki.vault import VaultLayout, resolve_vault, vault_page_path

layout = VaultLayout(
    entities="Knowledge/People",
    concepts="Knowledge/Ideas",
    sources="Knowledge/Sessions",
)
vault = resolve_vault(Path("~/my-vault").expanduser(), layout=layout)

print(vault_page_path(vault, "entities", "Karpathy"))
# ~/my-vault/Knowledge/People/Karpathy.md
```

CLI-level overrides land in a follow-up — today the defaults cover the
common case.

## Non-destructive writes — what happens when a page already exists

**Default**: `llmwiki sync --vault <path>` refuses to overwrite any
page that already exists in the vault. If the pipeline wants to write
`Wiki/Entities/RAG.md` and you already have a note there, it:

1. Leaves your page untouched.
2. If the pipeline has info to add (new sessions that reference the
   entity, new inbound wikilinks, etc.), it appends them under a
   `## Connections` heading at the bottom — but only if you don't
   already have that heading. Re-running sync is **idempotent**.

**Escape hatch**: `--allow-overwrite` tells sync to replace pages. Use
this sparingly — only when you're confident the pipeline's version is
authoritative (e.g. you just ran a full re-ingest after fixing upstream
data). The log line announces it loudly:

```
==> vault: /Users/you/vault (format: obsidian, ...)
  --allow-overwrite: existing vault pages may be clobbered
```

## Round-trip: edit in the vault, re-sync safely

The workflow that makes vault-overlay worth using:

1. llmwiki writes `Wiki/Entities/RAG.md` with basic frontmatter + a
   two-line description.
2. You open it in Obsidian/Logseq, add prose, rearrange headings, link
   out to five more pages.
3. Next `llmwiki sync --vault <path>`:
   - Sees the page already exists.
   - Skips the write (non-destructive default).
   - If it found new `[[RAG]]` references in newly-synthesized source
     pages, it appends them under the existing `## Connections`
     heading (idempotent — if the heading already exists, it's a
     no-op).
   - Your prose stays intact.

## Building a static site from the vault

```bash
llmwiki build --vault ~/my-vault --out ~/my-vault-site
```

This compiles pages *from* the vault into a gitignorable static site.
The same `site/graph.html`, `search-index.json`, and per-page `.txt` /
`.json` siblings get written.

## Python API

```python
from pathlib import Path
from llmwiki.vault import (
    VaultFormat,
    append_section,
    detect_vault_format,
    format_wikilink,
    resolve_vault,
    vault_page_path,
    write_vault_page,
)

vault = resolve_vault(Path("~/my-vault").expanduser())
print(vault.format)  # VaultFormat.OBSIDIAN

# Where should a new entity land?
path = vault_page_path(vault, "entities", "RAG")

# Write it (non-destructive — raises FileExistsError on clobber)
write_vault_page(path, "# RAG\n\nRetrieval-augmented generation.\n")

# Append to a user-owned page without rewriting
session = vault_page_path(vault, "sources", "2026-session")
link = format_wikilink(vault, "entities", "RAG")
append_section(session, "Connections", f"- {link}")
```

## Troubleshooting

**"vault directory does not exist"** — typo in the path, or your
shell didn't expand `~` (use quotes: `--vault "~/Obsidian Vault"`).

**"vault path is not a directory"** — you pointed `--vault` at a
single markdown file. Pass the vault root instead.

**Detected as Plain, not Obsidian** — the `.obsidian/` marker is
missing. Open the folder in Obsidian once to create it, then re-run.

**Logseq pages landing under `Wiki/...` instead of `pages/...`** —
your Logseq config file is in an unexpected location. Ensure either a
`logseq/` subdir or a root-level `config.edn` exists.

**`FileExistsError` on every page** — vault already has pages at the
default paths. If you intended to overwrite (bulk re-ingest), re-run
with `--allow-overwrite`. If you intended to merge, use the Python
API `append_section()` directly for per-page control.

## Non-goals (explicitly out of scope for #54)

- **Bidirectional `raw/` sync** — sessions still live in the repo's
  local `raw/sessions/`, not inside the vault. This keeps auto-
  generated transcripts from cluttering the user's notes.
- **Config.edn parsing** — Logseq detection is marker-only. If your
  Logseq config sets a non-default `pages/` directory, the pipeline
  doesn't discover it today.
- **Flat `namespace___slug.md` mode for Obsidian** — Obsidian users
  get folder nesting even if their existing convention is flat. Custom
  `VaultLayout` can't shape the filename format yet (only the prefix).
  Follow-up if there's demand.

## Related

- `#54` — the issue
- `llmwiki/vault.py` — implementation
- `docs/guides/obsidian-integration.md` — the original symlink-based
  integration (still works; vault-overlay is the "no-symlink"
  alternative)
- `#43` — OpenCode adapter (similar vault-touching pattern)
