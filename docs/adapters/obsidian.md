# Obsidian adapter

**Status:** ✅ Production (v0.1) — input mode
**Module:** `llmwiki.adapters.contrib.obsidian`
**Source:** [`llmwiki/adapters/contrib/obsidian.py`](../../llmwiki/adapters/contrib/obsidian.py)

## What it does

Reads plain `.md` files from an Obsidian vault and treats each file as a source document (like a session transcript). This lets you ingest your hand-written notes into the same wiki structure as your agent-generated session markdowns.

Unlike the Claude Code and Codex CLI adapters — which parse `.jsonl` into markdown — the Obsidian adapter reads markdown that you've already written, and hands it straight to the converter for lightweight processing (frontmatter preservation, filtering).

## Default vault locations

The adapter checks these paths in order (first one that exists wins):

```
~/Documents/Obsidian Vault
~/Obsidian
```

Override via `config.json`:

```jsonc
{
  "adapters": {
    "obsidian": {
      "vault_paths": [
        "~/Documents/Obsidian Vault",
        "~/work/team-vault",
        "~/research/phd-vault"
      ]
    }
  }
}
```

## What gets skipped

### Obsidian internals

The adapter skips these folders entirely because they contain Obsidian's own config and plugin data, not your notes:

- `.obsidian/`
- `.trash/`
- `.git/`
- `node_modules/`
- `Templates/` (and `_templates/`, `templates/`)

Override via `exclude_folders` in config.

### Empty or tiny files

Files smaller than `min_content_chars` (default: 50) are skipped. This filters out stub notes you've created but not filled in.

### `.llmwikiignore` patterns

If the repo has a `.llmwikiignore` file, it applies here too. Useful for skipping entire project folders inside a vault that contains multiple unrelated vaults.

## Project slug derivation

The **top-level folder** under the vault becomes the project slug. So a note at:

```
~/Documents/Obsidian Vault/03 - Learning/RAG vs Wiki.md
```

Gets the project slug `03---learning` (top-level folder name, lowercased and space-hyphenated).

A note at the vault root (no folder) gets the slug `vault-root`.

## Output location

Converted notes land under:

```
raw/sessions/<project-slug>/<note-filename>
```

Example:

```
~/Documents/Obsidian Vault/02 - Projects/ai-newsletter/design.md
  ↓
raw/sessions/02---projects/ai-newsletter-design.md
```

(The hierarchical path below the top-level folder is flattened into the filename with dashes.)

## Frontmatter handling

If your Obsidian notes have YAML frontmatter, llmwiki preserves it verbatim. If they don't, the adapter leaves the file unchanged — the wiki build will render it as plain markdown.

Obsidian-specific frontmatter (like `dataview` queries or `cssclass`) is passed through untouched and may not render correctly in the HTML build. This is intentional — we don't want to clobber your notes.

## Wikilinks

Obsidian's `[[wikilink]]` syntax is native to the llmwiki format, so your existing wikilinks will work. However:

- Wikilinks pointing to notes outside the current project slug may not resolve in the built site (llmwiki groups by project).
- Aliased wikilinks (`[[target|alias]]`) render with the alias.
- Embed wikilinks (`![[attachment.png]]`) are treated as images and will 404 in the built site unless you also copy the attachments.

**Attachment handling is not yet implemented.** See [Epic: v0.2.0 — Extensions](https://github.com/Pratiyush/llm-wiki/issues/2).

## Bidirectional sync (v0.2 roadmap)

Currently the Obsidian adapter is **input-only**: it reads your vault into llmwiki's `raw/` layer.

In v0.2 we plan to add **output mode**: write the compiled wiki (`wiki/sources/`, `wiki/entities/`, `wiki/concepts/`) back into your vault so you can browse llmwiki's output alongside your other notes, with Obsidian's graph view, backlinks panel, and search.

Tracking: [LMW-107 Obsidian output (bidirectional sync)](https://github.com/Pratiyush/llm-wiki/issues).

## Testing the adapter

```bash
python3 -m llmwiki adapters                           # should list obsidian as available
python3 -m llmwiki sync --adapter obsidian --dry-run  # preview conversion
python3 -m llmwiki sync --adapter obsidian            # run it
```

## Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| `available: no` | No vault at the default paths | Add your vault to `config.json` → `adapters.obsidian.vault_paths` |
| Nothing converted | All notes smaller than `min_content_chars` | Lower the threshold or check your vault path |
| Wrong project slugs | Vault has atypical folder naming | Override via `vault_paths` pointing deeper into the vault |
| `.obsidian/` files showing up | Custom vault structure | Add more patterns to `exclude_folders` |
| Attachments 404 in the built site | Attachments not copied | Known issue — will be addressed in v0.2 |

## Privacy

The same redaction pipeline runs on Obsidian notes as on Claude Code sessions — username, API keys, tokens, and emails are redacted before anything hits `raw/`. If your notes contain company-internal names or client identifiers you want redacted too, add them to `extra_patterns` in `config.json`.

## Example config

Full example tuned for a work + personal dual-vault setup:

```jsonc
{
  "adapters": {
    "obsidian": {
      "vault_paths": [
        "~/Documents/Obsidian Vault",
        "~/work/engineering-vault"
      ],
      "exclude_folders": [
        ".obsidian",
        ".trash",
        "Templates",
        "_templates",
        "Daily Notes",
        "archive"
      ],
      "min_content_chars": 100
    }
  },
  "redaction": {
    "extra_patterns": [
      "ACME-[A-Z0-9]{5,}",
      "@acmecorp\\.com"
    ]
  }
}
```
