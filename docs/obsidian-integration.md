# Obsidian Integration Guide

llmwiki is designed to work natively inside Obsidian. This guide covers
the recommended plugins and configuration for the best experience.

## Why Obsidian?

llmwiki emits plain markdown with YAML frontmatter and `[[wikilinks]]` —
exactly what Obsidian reads natively. Open your `wiki/` folder as an
Obsidian vault (or symlink it into an existing vault) and you get:

- Graph view with entity/concept relationships
- Backlinks panel showing which pages cite each entity
- Full-text search across every wiki page
- Live preview with embedded Dataview queries

## Setup — 5 minutes

### Option 1: Open wiki/ as a standalone vault

```
Obsidian → Open another vault → Open folder as vault → .../llm-wiki/wiki
```

### Option 2: Symlink into an existing vault

Use the built-in CLI:

```bash
python3 -m llmwiki link-obsidian --vault ~/Documents/"Obsidian Vault"
```

This creates `~/Documents/Obsidian Vault/LLM Wiki/` as a symlink to the
llm-wiki project root, so `[[wikilinks]]` resolve and the graph view
shows the entire wiki alongside your other notes.

## Recommended Plugins

Install in Obsidian via `Settings → Community plugins → Browse`.

### Core (required for full experience)

1. **[Dataview](https://blacksmithgu.github.io/obsidian-dataview/)** —
   Required for `wiki/dashboard.md` and category pages. Indexes YAML
   frontmatter and runs live queries.

2. **[Templater](https://silentvoid13.github.io/Templater/)** —
   Point at `examples/obsidian-templates/` so you can create new
   wiki pages with one keystroke. See
   [examples/obsidian-templates/README.md](../examples/obsidian-templates/README.md).

3. **[Obsidian Linter](https://platers.github.io/obsidian-linter/)** —
   Enforces frontmatter ordering, heading hierarchy, and trailing
   newlines. Recommended rules:
   - YAML Timestamp
   - Capitalize Headings (Sentence case)
   - Trailing spaces / Remove Empty Lines Between List Markers

4. **[Obsidian Web Clipper](https://obsidian.md/clipper)** —
   Chrome/Firefox extension for saving web articles directly into
   `raw/web/`. Configure its default save location to your llmwiki's
   `raw/` directory and llmwiki's Web Clipper intake (see #149) will
   auto-queue them for ingestion.

### Optional (LLM-powered)

5. **[Smart Connections](https://github.com/brianpetro/obsidian-smart-connections)** —
   Semantic similarity across notes using local embeddings.
   Complements llmwiki's explicit `[[wikilinks]]` with
   "pages related by meaning."

6. **obsidian-mcp-tools** (jacksteamdev) —
   MCP server exposing Obsidian vault content to Claude Desktop /
   Claude Code. Config lives in `~/.claude/.mcp.json`.

## Plugin Configuration

### Dataview

`Settings → Dataview`:
- ✅ Enable JavaScript Queries (for advanced dashboard widgets)
- ✅ Enable Inline Queries
- ✅ Automatic View Refreshing: 5 seconds (default)

### Templater

`Settings → Templater`:
- Template folder location: `examples/obsidian-templates` (if inside vault)
- Trigger Templater on new file creation: ✅
- Enable System Commands: ✅ (needed for date helpers)

### Obsidian Linter

`Settings → Linter → General`:
- ✅ Lint on save
- ✅ Display message on lint

Enable these YAML rules:
- Format Tags in YAML
- Re-Index File → enable `last_updated`
- YAML Key Sort → push `title`, `type`, `tags` to top

## Graph View Tips

`View → Graph View → Display`:
- Arrows: ✅ (shows link direction)
- Existing files only: ✅ (hides broken links)
- Color groups:
  - `#entities` → blue
  - `#concepts` → green
  - `#sources` → amber
  - `#syntheses` → purple

## Workflow

1. **Ingest** — run `python3 -m llmwiki sync` (converts new sessions)
   and `/wiki-sync` (Claude Code slash command to compile into wiki).
2. **Read & edit** — open Obsidian, browse graph view, click `[[links]]`.
3. **Create** — hit `Cmd/Ctrl+Shift+P → Templater: New from template`.
4. **Review** — open `wiki/dashboard.md` to see what's stale, uncited,
   or low-confidence.
5. **Lint** — `python3 -m llmwiki lint` for structural checks.

## Two-way editing

Obsidian edits directly to `wiki/*.md` are preserved — llmwiki's ingest
pipeline never overwrites sections outside the frontmatter and the
specific sections it manages (`## Summary`, `## Key Facts`, etc.).

Add your own `## Notes` or `## Follow-ups` sections and they stay put
across ingestions.

## Related Docs

- [examples/obsidian-templates/README.md](../examples/obsidian-templates/README.md) — Templater install
- [CLAUDE.md](../CLAUDE.md) — page format specs
- [examples/wiki_dashboard.md](../examples/wiki_dashboard.md) — dashboard template
