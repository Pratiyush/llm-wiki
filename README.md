# llmwiki

> **LLM-powered knowledge base from your Claude Code, Codex CLI, Cursor, Gemini CLI, and Obsidian sessions.**
> Built on [Andrej Karpathy's LLM Wiki pattern](https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f).

## 👉 Live demo: **[pratiyush.github.io/llm-wiki](https://pratiyush.github.io/llm-wiki/)**

Rebuilt on every `master` push from the synthetic sessions in [`examples/demo-sessions/`](examples/demo-sessions). No personal data. Shows every feature of the real tool (activity heatmap, tool charts, token usage, model info cards, vs-comparisons, project topics) running against safe reference data.

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python 3.9+](https://img.shields.io/badge/python-3.9+-blue.svg)](https://www.python.org/)
[![Version](https://img.shields.io/badge/version-v0.9.0-7C3AED.svg)](CHANGELOG.md)
[![Tests](https://img.shields.io/badge/tests-420%20passing-10B981.svg)](tests/)
[![Works with Claude Code](https://img.shields.io/badge/Claude%20Code-✓-7C3AED.svg)](https://claude.com/claude-code)
[![Works with Codex CLI](https://img.shields.io/badge/Codex%20CLI-✓-7C3AED.svg)](https://github.com/openai/codex)

---

Every Claude Code, Codex CLI, and Cursor session writes a full transcript to disk. You already have hundreds of them and never look at them again.

**llmwiki** turns that dormant history into a beautiful, searchable, interlinked knowledge base — locally, in two commands. Plus, it produces AI-consumable exports (`llms.txt`, `llms-full.txt`, JSON-LD graph, per-page `.txt` + `.json` siblings) so other AI agents can query your wiki directly.

```bash
./setup.sh                         # one-time install
./build.sh && ./serve.sh           # build + serve at http://127.0.0.1:8765
```

**Contributing in one line:** read [`CONTRIBUTING.md`](CONTRIBUTING.md), keep PRs focused (one concern each), use `feat:` / `fix:` / `docs:` / `chore:` / `test:` commit prefixes, never commit real session data (`raw/` is gitignored), no new runtime deps. CI must be green to merge.

## Screenshots

All screenshots below are from the **public demo site** which is built on every `master` push from the dummy example sessions. Your own wiki will look identical — just with your real work.

### Home — projects overview with activity heatmap
![llmwiki home page — LLM Wiki header, activity heatmap, and a grid of three demo projects (demo-blog-engine, demo-ml-pipeline, demo-todo-api)](docs/images/home.png)

### All sessions — filterable table across every project
![llmwiki sessions index — activity timeline above a table of eight demo sessions with project, model, date, message count, and tool-call columns](docs/images/sessions.png)

### Session detail — full conversation + tool calls
![llmwiki session detail — Rust blog engine scaffolding session showing summary, breadcrumbs, a TOML Cargo.toml block and a Rust main.rs block, both highlighted by highlight.js](docs/images/session-rust.png)

### Changelog — renders `CHANGELOG.md` as a first-class page
![llmwiki changelog page — keep-a-changelog format with colored headings for Added / Fixed / Changed and auto-linked PR references](docs/images/changelog.png)

### Projects index — freshness badges + per-project stats
![llmwiki projects index — three demo project cards with green/yellow/red freshness badges showing how recently each project was touched](docs/images/projects.png)

## What you get

### Human-readable
- **All your sessions**, converted from `.jsonl` to clean, redacted markdown
- **A Karpathy-style wiki** — `sources/`, `entities/`, `concepts/`, `syntheses/`, `comparisons/`, `questions/` linked with `[[wikilinks]]`
- **A beautiful static site** you can browse locally or deploy to GitHub Pages
  - Global search (Cmd+K command palette with fuzzy match over pre-built index)
  - [highlight.js](https://highlightjs.org/) client-side syntax highlighting (light + dark themes)
  - Dark mode (system-aware + manual toggle with `data-theme`)
  - Keyboard shortcuts: `/` search · `g h/p/s` nav · `j/k` rows · `?` help
  - Collapsible tool-result sections (auto-expand > 500 chars)
  - Copy-as-markdown + copy-code buttons
  - Breadcrumbs + reading progress bar
  - Filter bar on sessions table (project/model/date/text)
  - Reading time estimates (`X min read`)
  - Related pages panel at the bottom of every session
  - Activity heatmap on the home page
  - Hover-to-preview wikilinks
  - Deep-link icons next to every heading
  - Mobile-responsive + print-friendly

### AI-consumable (v0.4)
Every HTML page has sibling machine-readable files at the same URL:

- `<page>.html` — human HTML with schema.org microdata
- `<page>.txt` — plain text version (no HTML tags)
- `<page>.json` — structured metadata + body

Site-level AI-agent entry points:

| File | What |
|---|---|
| [`/llms.txt`](docs/v0.4-roadmap.md) | Short index per [llmstxt.org spec](https://llmstxt.org) |
| `/llms-full.txt` | Flattened plain-text dump (~5 MB cap) — paste into any LLM's context |
| `/graph.jsonld` | Schema.org JSON-LD entity/concept/source graph |
| `/sitemap.xml` | Standard sitemap with `lastmod` |
| `/rss.xml` | RSS 2.0 feed of newest sessions |
| `/robots.txt` | AI-friendly robots with llms.txt reference |
| `/ai-readme.md` | AI-specific navigation instructions |
| `/manifest.json` | Build manifest with SHA-256 hashes + perf budget |

Every page also includes an `<!-- llmwiki:metadata -->` HTML comment that AI agents can parse without fetching the separate `.json` sibling.

### Automation
- **SessionStart hook** — auto-syncs new sessions in the background on every Claude Code launch
- **File watcher** — `llmwiki watch` polls agent stores with debounce and runs sync on change
- **MCP server** — 7 production tools (`wiki_query`, `wiki_search`, `wiki_list_sources`, `wiki_read_page`, `wiki_lint`, `wiki_sync`, `wiki_export`) queryable from any MCP client (Claude Desktop, Cline, Cursor, ChatGPT desktop)
- **No servers, no database, no npm** — Python stdlib + `markdown`. Syntax highlighting loads from a highlight.js CDN at view time.

## How it works

```
┌─────────────────────────────────────┐
│  ~/.claude/projects/*/*.jsonl       │  ← Claude Code sessions
│  ~/.codex/sessions/**/*.jsonl       │  ← Codex CLI sessions
│  ~/Library/.../Cursor/workspaceS…   │  ← Cursor
│  ~/Documents/Obsidian Vault/        │  ← Obsidian
│  ~/.gemini/                         │  ← Gemini CLI
└──────────────┬──────────────────────┘
               │
               ▼   python3 -m llmwiki sync
┌─────────────────────────────────────┐
│  raw/sessions/<project>/            │  ← immutable markdown (Karpathy layer 1)
│     2026-04-08-<slug>.md            │
└──────────────┬──────────────────────┘
               │
               ▼   /wiki-ingest  (your coding agent)
┌─────────────────────────────────────┐
│  wiki/sources/<slug>.md             │  ← LLM-generated wiki (Karpathy layer 2)
│  wiki/entities/<Name>.md            │
│  wiki/concepts/<Name>.md            │
│  wiki/syntheses/<Name>.md           │
│  wiki/comparisons/<Name>.md         │
│  wiki/questions/<Name>.md           │
│  wiki/index.md, overview.md, log.md │
└──────────────┬──────────────────────┘
               │
               ▼   python3 -m llmwiki build
┌─────────────────────────────────────┐
│  site/                              │  ← static HTML + AI exports
│  ├── index.html, style.css, ...     │
│  ├── sessions/<project>/<slug>.html │
│  ├── sessions/<project>/<slug>.txt  │  (AI sibling)
│  ├── sessions/<project>/<slug>.json │  (AI sibling)
│  ├── llms.txt, llms-full.txt        │
│  ├── graph.jsonld                   │
│  ├── sitemap.xml, rss.xml           │
│  ├── robots.txt, ai-readme.md       │
│  ├── manifest.json                  │
│  └── search-index.json              │
└─────────────────────────────────────┘
```

See [docs/architecture.md](docs/architecture.md) for the full 3-layer Karpathy + 8-layer build breakdown.

## Install

### macOS / Linux

```bash
git clone https://github.com/Pratiyush/llm-wiki.git
cd llm-wiki
./setup.sh
```

### Windows

```cmd
git clone https://github.com/Pratiyush/llm-wiki.git
cd llm-wiki
setup.bat
```

### With pip (v0.3+)

```bash
pip install -e .                # basic — everything you need
pip install -e '.[pdf]'         # + PDF ingestion
pip install -e '.[dev]'         # + pytest + ruff
pip install -e '.[all]'         # all of the above
```

Syntax highlighting is now powered by [highlight.js](https://highlightjs.org/), loaded from a CDN at view time — no optional deps required.

### What setup does

1. Creates `raw/`, `wiki/`, `site/` data directories
2. Installs the `llmwiki` Python package in-place
3. Detects your coding agents and enables matching adapters
4. Optionally offers to install the `SessionStart` hook into `~/.claude/settings.json` for auto-sync
5. Runs a first sync so you see output immediately

## For maintainers

Running the project? The governance scaffold lives under [`docs/maintainers/`](docs/maintainers) and is loaded by a dedicated skill:

| File | What it's for |
|---|---|
| [`CONTRIBUTING.md`](CONTRIBUTING.md) | Short rules for contributors — read this first |
| [`CODE_OF_CONDUCT.md`](CODE_OF_CONDUCT.md) | Contributor Covenant 2.1 |
| [`SECURITY.md`](SECURITY.md) | Disclosure process for redaction bugs, XSS, data leaks |
| [`docs/maintainers/ARCHITECTURE.md`](docs/maintainers/ARCHITECTURE.md) | One-page system diagram + layer boundaries + what NOT to add |
| [`docs/maintainers/REVIEW_CHECKLIST.md`](docs/maintainers/REVIEW_CHECKLIST.md) | Canonical code-review criteria |
| [`docs/maintainers/RELEASE_PROCESS.md`](docs/maintainers/RELEASE_PROCESS.md) | Version bump → CHANGELOG → tag → build → publish |
| [`docs/maintainers/TRIAGE.md`](docs/maintainers/TRIAGE.md) | Label taxonomy + stale-issue policy |
| [`docs/maintainers/ROADMAP.md`](docs/maintainers/ROADMAP.md) | Near-term plan + release themes |
| [`docs/maintainers/DECLINED.md`](docs/maintainers/DECLINED.md) | Graveyard of declined ideas with reasons |

Four Claude Code slash commands automate the common ops:

- `/review-pr <N>` — apply the REVIEW_CHECKLIST to a PR and post findings
- `/triage-issue <N>` — label + milestone + priority a new issue
- `/release <version>` — walk the release process step by step
- `/maintainer` — meta-skill that loads every governance doc as context

## CLI reference

```bash
llmwiki init                    # scaffold raw/ wiki/ site/
llmwiki sync                    # convert .jsonl → markdown
llmwiki build                   # compile static HTML + AI exports
llmwiki serve                   # local HTTP server on 127.0.0.1:8765
llmwiki adapters                # list available adapters
llmwiki graph                   # build knowledge graph (v0.2)
llmwiki watch                   # file watcher with debounce (v0.2)
llmwiki export-obsidian         # write wiki to Obsidian vault (v0.2)
llmwiki eval                    # 7-check structural quality score /100 (v0.3)
llmwiki check-links             # verify internal links in site/ (v0.4)
llmwiki export <format>         # AI-consumable exports (v0.4)
llmwiki manifest                # build site manifest + perf budget (v0.4)
llmwiki version
```

Each subcommand has its own `--help`. All commands are also wrapped in one-click shell/batch scripts: `sync.sh`/`.bat`, `build.sh`/`.bat`, `serve.sh`/`.bat`, `upgrade.sh`/`.bat`.

## Works with

| Agent | Adapter | Status | Added in |
|---|---|---|---|
| [Claude Code](https://claude.com/claude-code) | `llmwiki.adapters.claude_code` | ✅ Production | v0.1 |
| [Obsidian](https://obsidian.md) (input) | `llmwiki.adapters.obsidian` | ✅ Production | v0.1 |
| [Obsidian](https://obsidian.md) (output) | `llmwiki.obsidian_output` | ✅ Production | v0.2 |
| [Codex CLI](https://github.com/openai/codex) | `llmwiki.adapters.codex_cli` | ✅ Production | v0.3 |
| [Cursor](https://cursor.com) | `llmwiki.adapters.cursor` | 🟡 Discovery scaffold | v0.2 |
| [Gemini CLI](https://ai.google.dev/gemini-api) | `llmwiki.adapters.gemini_cli` | 🟡 Discovery scaffold | v0.3 |
| PDF files | `llmwiki.adapters.pdf` | 🟡 Scaffold (requires `pypdf` + config) | v0.3 |
| OpenCode / OpenClaw | — | ⏸ Deferred to v0.5+ | — |

Adding a new agent is [one small file](docs/framework.md) — subclass `BaseAdapter`, declare `SUPPORTED_SCHEMA_VERSIONS`, ship a fixture + snapshot test.

## MCP server

llmwiki ships its own MCP server (stdio transport, no SDK dependency) so any MCP client can query your wiki directly.

```bash
python3 -m llmwiki.mcp   # runs on stdin/stdout
```

Seven production tools:

| Tool | What |
|---|---|
| `wiki_query(question, max_pages)` | Keyword search + page content (no LLM synthesis) |
| `wiki_search(term, include_raw)` | Raw grep over wiki/ (+ optional raw/) |
| `wiki_list_sources(project)` | List raw source files with metadata |
| `wiki_read_page(path)` | Read one page (path-traversal guarded) |
| `wiki_lint()` | Orphans + broken-wikilinks report |
| `wiki_sync(dry_run)` | Trigger the converter |
| `wiki_export(format)` | Return any AI-consumable export (llms.txt, jsonld, sitemap, rss, manifest) |

Register in your MCP client's config — e.g. for Claude Desktop, add to `~/Library/Application Support/Claude/claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "llmwiki": {
      "command": "python3",
      "args": ["-m", "llmwiki.mcp"]
    }
  }
}
```

## Configuration

Single JSON config at `examples/sessions_config.json`. Copy to `config.json` and edit:

```json
{
  "filters": {
    "live_session_minutes": 60,
    "exclude_projects": []
  },
  "redaction": {
    "real_username": "YOUR_USERNAME",
    "replacement_username": "USER",
    "extra_patterns": [
      "(?i)(api[_-]?key|secret|token|bearer|password)...",
      "sk-[A-Za-z0-9]{20,}"
    ]
  },
  "truncation": {
    "tool_result_chars": 500,
    "bash_stdout_lines": 5
  },
  "adapters": {
    "obsidian": {
      "vault_paths": ["~/Documents/Obsidian Vault"]
    }
  }
}
```

All paths, regexes, truncation limits, and per-adapter settings are tunable. See [docs/configuration.md](docs/configuration.md).

## `.llmwikiignore`

Gitignore-style pattern file at the repo root. Skip entire projects, dates, or specific sessions without touching config:

```
# Skip a whole project
confidential-client/
# Skip anything before a date
*2025-*
# Keep exception
!confidential-client/public-*
```

## Karpathy's LLM Wiki pattern

This project follows the three-layer structure described in [Karpathy's gist](https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f):

1. **Raw sources** (`raw/`) — immutable. Session transcripts converted from `.jsonl`.
2. **The wiki** (`wiki/`) — LLM-generated. One page per entity, concept, source. Interlinked via `[[wikilinks]]`.
3. **The schema** (`CLAUDE.md`, `AGENTS.md`) — tells your agent how to ingest and query.

See [docs/architecture.md](docs/architecture.md) for the full breakdown and how it maps to the file tree.

## Design principles

- **Stdlib first** — only mandatory runtime dep is `markdown`. `pygments` and `pypdf` are optional.
- **Works offline** — no CDN, no fonts from Google by default (use system fonts).
- **Redact by default** — username, API keys, tokens, emails all get redacted before entering the wiki.
- **Idempotent everything** — re-running any command is safe and cheap.
- **Agent-agnostic core** — the converter doesn't know which agent produced the `.jsonl`; adapters translate.
- **Privacy by default** — localhost-only binding, no telemetry, no cloud calls.
- **Dual-format output (v0.4)** — every page ships both for humans (HTML) and AI agents (TXT + JSON + JSON-LD + sitemap + llms.txt).

## Docs

- [Getting started](docs/getting-started.md) — 5-minute quickstart
- [Architecture](docs/architecture.md) — Karpathy 3-layer + 8-layer build breakdown
- [Configuration](docs/configuration.md) — every tuning knob
- [Privacy](docs/privacy.md) — redaction rules + `.llmwikiignore` + localhost binding
- [Windows setup](docs/windows-setup.md) — Windows-specific gotchas
- [Framework](docs/framework.md) — Open Source Framework v4.1 adapted for agent-native dev tools
- [Research](docs/research.md) — Phase 1.25 analysis of 15 prior LLM Wiki implementations
- [Feature matrix](docs/feature-matrix.md) — all 161 features across 16 categories
- [Roadmap](docs/roadmap.md) — Phase × Layer × Item MoSCoW table
- [v0.4 roadmap](docs/v0.4-roadmap.md) — AI & Human Dual-Format plan
- **Translations**: [i18n/zh-CN](docs/i18n/zh-CN/), [i18n/ja](docs/i18n/ja/), [i18n/es](docs/i18n/es/)

Per-adapter docs:
- [Claude Code adapter](docs/adapters/claude-code.md)
- [Codex CLI adapter](docs/adapters/codex-cli.md)
- [Obsidian adapter](docs/adapters/obsidian.md)

## Releases

| Version | Focus | Tag |
|---|---|---|
| [v0.1.0](https://github.com/Pratiyush/llm-wiki/releases/tag/v0.1.0) | Core release — Claude Code adapter, god-level HTML UI, schema, CI, plugin scaffolding | `v0.1.0` |
| [v0.2.0](https://github.com/Pratiyush/llm-wiki/releases/tag/v0.2.0) | Extensions — 3 new slash commands, 3 new adapters, Obsidian bidirectional, full MCP server | `v0.2.0` |
| [v0.3.0](https://github.com/Pratiyush/llm-wiki/releases/tag/v0.3.0) | PyPI packaging, eval framework, i18n scaffold | `v0.3.0` |
| [v0.4.0](https://github.com/Pratiyush/llm-wiki/releases/tag/v0.4.0) | AI + human dual format — per-page .txt/.json siblings, llms.txt, JSON-LD graph, sitemap, RSS, schema.org microdata, reading time, related pages, activity heatmap, deep-link anchors, build manifest, link checker, `wiki_export` MCP tool | `v0.4.0` |

## Roadmap

Active milestones on GitHub: [v0.5.0](https://github.com/Pratiyush/llm-wiki/milestone/4) · [v0.6.0](https://github.com/Pratiyush/llm-wiki/milestone/5) · [v0.7.0](https://github.com/Pratiyush/llm-wiki/milestone/7) · [v0.8.0](https://github.com/Pratiyush/llm-wiki/milestone/8) · [v0.4.x polish](https://github.com/Pratiyush/llm-wiki/milestone/6).

| Milestone | Focus | Tracking |
|---|---|---|
| **v0.5.0 — Synthesis & Automation** | Optional local LLM synthesis via Ollama, auto-ingest hook on sync, candidate/approval workflow, `_context.md` folder metadata, and graduating three scaffold adapters (Cursor, Gemini CLI, PDF) to production. Default install stays stdlib + `markdown` only. | [Epic #34](https://github.com/Pratiyush/llm-wiki/issues/34) |
| **v0.6.0 — Distribution & Reach** | `brew install llmwiki`, PyPI release automation via OIDC, two more adapters (OpenCode/OpenClaw, ChatGPT conversation export, qmd export), content-freshness badges, and GitLab Pages deployment workflow alongside the existing GitHub Pages one. | [Epic #40](https://github.com/Pratiyush/llm-wiki/issues/40) |
| **v0.7.0 — Structured Data** | Structured model-profile schema with YAML frontmatter (context window, pricing, license, benchmarks), append-only changelog field for time-series tracking, and auto-generated vs-comparison pages. | [Milestone](https://github.com/Pratiyush/llm-wiki/milestone/7) |
| **v0.8.0 — Analytics & Visualization** | Session metrics frontmatter, GitLab-style activity heatmap, per-session tool-calling bar chart, and token-usage card with cache-hit-ratio — all rendered as pure SVG at build time (stdlib only). | [Milestone](https://github.com/Pratiyush/llm-wiki/milestone/8) |
| **v0.4.x — Quality & Polish** | Cross-cutting quality work — Playwright E2E tests, WCAG 2.1 AA accessibility audit, lazy-loading the search index in per-project chunks, and scheduled-sync templates for launchd/systemd/Windows Task Scheduler. | [Milestone](https://github.com/Pratiyush/llm-wiki/milestone/6) |

### Deployment targets

- **GitHub Pages** — shipped in v0.1 via `.github/workflows/deploy.yml` (triggers on tag push).
- **GitLab Pages** — tracked in [#49](https://github.com/Pratiyush/llm-wiki/issues/49), landing in v0.6.
- **Any static host** — `llmwiki build` writes to `site/`, which you can `rsync`/`scp` anywhere.

## Acknowledgements

- [Andrej Karpathy](https://twitter.com/karpathy) for [the LLM Wiki idea](https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f)
- [SamurAIGPT/llm-wiki-agent](https://github.com/SamurAIGPT/llm-wiki-agent), [lucasastorian/llmwiki](https://github.com/lucasastorian/llmwiki), [xoai/sage-wiki](https://github.com/xoai/sage-wiki), and [bashiraziz/llm-wiki-template](https://github.com/bashiraziz/llm-wiki-template) — prior art that shaped this.
- [Python Markdown](https://python-markdown.github.io/) and [Pygments](https://pygments.org/) for the rendering pipeline.
- [llmstxt.org](https://llmstxt.org) for the llms.txt spec used in v0.4.

## License

[MIT](LICENSE) © Pratiyush
