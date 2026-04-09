# Architecture

llmwiki has two overlapping structures:

1. The **Karpathy three-layer wiki** (conceptual): `raw/` → `wiki/` → `site/`
2. The **eight-layer build** (implementation): how responsibilities are distributed across Python modules, HTML templates, scripts, CI, etc.

This document covers both.

## Layer 1: Karpathy's three-layer wiki

From the [original LLM Wiki gist](https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f):

```
raw/           IMMUTABLE source documents
    ↓          (llmwiki converts .jsonl → .md here)
wiki/          LLM-MAINTAINED pages
    ↓          (your coding agent writes here via /wiki-ingest)
site/          GENERATED static HTML
               (llmwiki builds here via `llmwiki build`)
```

### raw/ — immutable layer

Everything under `raw/` is treated as source-of-truth. The converter writes to it; nothing else should. If a source is wrong, fix the converter, not the output.

The converter writes one markdown file per session under `raw/sessions/<project>/<date>-<slug>.md`. Each file has YAML frontmatter (project, started, model, tools_used, gitBranch, etc.) and a Conversation body rendered turn-by-turn.

### wiki/ — LLM-maintained layer

Your coding agent owns this layer entirely. It writes via the Ingest Workflow in [CLAUDE.md](../CLAUDE.md):

```
wiki/
├── index.md          catalog of all pages, updated on every ingest
├── log.md            append-only chronological record
├── overview.md       living synthesis across all sources
├── sources/          one summary page per raw source (kebab-case slug)
├── entities/         people, projects, tools (TitleCase.md)
├── concepts/         ideas, frameworks, patterns (TitleCase.md)
└── syntheses/        saved query answers (kebab-case slug)
```

Pages interlink via `[[wikilinks]]`. Contradictions are recorded, not silently overwritten. Pages compound over time — every new source makes the wiki richer.

### site/ — generated static layer

`llmwiki build` reads `raw/` (and `wiki/` if populated) and renders a complete static HTML site. Nothing here is hand-maintained. Safe to delete and regenerate any time.

## Layer 2: The eight-layer build

Internally the code is organised into eight functional layers. Each layer has one clear responsibility, and each feature in [docs/roadmap.md](roadmap.md) maps to exactly one layer.

```
┌──────────────────────────────────────────────────────┐
│  L7  CI / ops          .github/workflows/            │
│  L6  Adapters          llmwiki/adapters/             │
│  L5  Schema / docs     CLAUDE.md, AGENTS.md, docs/   │
│  L4  Distribution      setup.sh, .bat, .claude/      │
│  L3  Viewer            script.js in build.py         │
│  L2  Site              build.py (HTML + CSS)         │
│  L1  Wiki              CLAUDE.md workflows           │
│  L0  Raw               llmwiki/convert.py            │
└──────────────────────────────────────────────────────┘
```

### L0 — Raw

Owner: `llmwiki/convert.py`

Reads .jsonl from the agent's session store (via an adapter), filters out noise records, runs redaction, normalises the output into markdown, and writes to `raw/sessions/`.

Key properties:

- **Idempotent** — mtime tracked in `.llmwiki-state.json`
- **Privacy-first** — username + API keys + tokens + emails redacted by default
- **Live-session safe** — skips files with a record younger than 60 minutes
- **Agent-agnostic** — delegates discovery to the adapter registry

### L1 — Wiki

Owner: your coding agent, following [CLAUDE.md](../CLAUDE.md) / [AGENTS.md](../AGENTS.md)

llmwiki does NOT write to `wiki/` directly. The agent does, via slash commands (`/wiki-ingest`, `/wiki-query`, `/wiki-lint`) that execute the workflows in the schema file.

### L2 — Site (HTML generator)

Owner: `llmwiki/build.py`

Converts every file under `raw/sessions/` (and any hand-authored files under `wiki/`) into static HTML. Uses `python-markdown` (the only runtime dep) — syntax highlighting runs in the browser via highlight.js loaded from a pinned jsdelivr CDN (v0.5, #73), so the build pipeline itself stays stdlib-only. Writes to `site/`.

Pages rendered (v0.9 surface):

- `site/index.html` — home with hero + 365-day activity heatmap + token-usage stat grid + recently-updated card + project grid with topic chips
- `site/projects/index.html` — project grid with freshness badges
- `site/projects/<project>.html` — per-project page with topics strip, 365-day heatmap (scoped), tool-calling bar chart, token timeline, main sessions + sub-agents
- `site/sessions/index.html` — sortable sessions table with filter bar
- `site/sessions/<project>/<slug>.html` — per-session transcript with tool chart + token card + full conversation
- `site/models/index.html` — sortable AI-model directory (v0.7, #55)
- `site/models/<slug>.html` — per-model info card + changelog timeline + pricing sparkline (v0.7, #56)
- `site/vs/index.html` — auto-generated vs-comparison index (v0.7, #58)
- `site/vs/<a>-vs-<b>.html` — side-by-side info table + benchmark chart + price delta
- `site/changelog.html` — `CHANGELOG.md` rendered as a first-class page (v0.4.2, #72)
- `site/search-index.json` — pre-built client-side search index
- `site/sources/<project>/<slug>.md` — copies of raw source for download
- Plus AI-consumable exports: `llms.txt`, `llms-full.txt`, `graph.jsonld`, `sitemap.xml`, `rss.xml`, per-page `.txt` + `.json` siblings

### L3 — Viewer (browser JS)

Owner: `script.js` (a string constant inside `build.py`)

Everything that happens in the browser, in vanilla JS:

- Theme toggle with `data-theme` attribute + localStorage + system preference
- Reading progress bar (scroll-linked CSS)
- Copy-as-markdown + copy-code buttons (Clipboard API + `document.execCommand` fallback for HTTP)
- Auto-collapse of long tool-result sections into `<details>`
- Cmd+K command palette (fuzzy search over `search-index.json`)
- Keyboard shortcuts: `/`, `g h`, `g p`, `g s`, `j`, `k`, `?`
- Sessions-table filter bar (project, model, date range, slug text)

Zero dependencies. No bundler. No framework. One file.

### L4 — Distribution

Owner: the repo root + `.claude-plugin/`

How users install and run llmwiki:

- `setup.sh` / `setup.bat` — one-click install
- `sync.sh` / `sync.bat` — wrappers around `python3 -m llmwiki sync`
- `build.sh` / `build.bat` — wrappers around `python3 -m llmwiki build`
- `serve.sh` / `serve.bat` — wrappers around `python3 -m llmwiki serve`
- `upgrade.sh` / `upgrade.bat` — `git pull` + re-run setup
- `.claude-plugin/plugin.json` + `marketplace.json` — Claude Code plugin packaging
- `.claude/commands/` — 7 slash commands
- `.claude/skills/` — 5 auto-discoverable skills
- `llmwiki/mcp/` — MCP server stub

### L5 — Schema / docs

Owner: root-level markdown + `docs/`

Tells humans and agents how the system works:

- `CLAUDE.md` — Claude Code schema with Ingest / Query / Lint workflows
- `AGENTS.md` — Codex / OpenCode / Gemini mirror of the same
- `.kiro/steering/` — always-loaded contribution / format / verification rules
- `docs/framework.md` — Open Source Framework v4.1 adapted for llmwiki
- `docs/research.md` — Phase 1.25 research report
- `docs/feature-matrix.md` — 161 features across 16 categories
- `docs/roadmap.md` — Phase × Layer × Item MoSCoW table

### L6 — Adapters

Owner: `llmwiki/adapters/`

One file per agent. Each subclass of `BaseAdapter` does three things:

1. Knows where the agent writes its session store
2. Walks that store to discover `.jsonl` files
3. Derives a friendly project slug from the path

Everything else (record parsing, filtering, redaction, rendering) is shared in `convert.py`.

### L7 — CI / ops

Owner: `.github/workflows/` + `tests/`

- `ci.yml` — lint + tests + build smoke on every push + PR (Python 3.9 and 3.12 matrix)
- `gitleaks.yml` — secret scan
- `pages.yml` — build + deploy to GitHub Pages on tag push (Phase 6.5 Self-Demo)
- `tests/fixtures/<agent>/` — synthetic fixtures
- `tests/snapshots/<agent>/` — expected markdown outputs
- `tests/test_*.py` — pytest unit + snapshot tests

## Adding an adapter

See [framework.md §5.25 Adapter Flow](framework.md) for the full contract. TL;DR: one new file at `llmwiki/adapters/<agent>.py`, one fixture, one snapshot test, one doc page, one README line, one CHANGELOG entry.

## Design principles

1. **Stdlib first.** Runtime dep: `markdown` only. Nothing else. Syntax highlighting runs client-side via a CDN-loaded highlight.js (v0.5, #73) so the build stays deterministic and offline-capable.
2. **Privacy by default.** Redact everything sensitive before it hits disk.
3. **Idempotent everything.** Re-running any command is safe and cheap.
4. **Localhost only.** No network, no telemetry, no cloud. The user controls if/when to publish.
5. **One file per concern.** build.py is one file, not a folder of templates. The whole HTML rendering lives there including CSS + JS.
6. **Agent-agnostic core.** `convert.py` doesn't know which agent produced the .jsonl. Adapters translate.
