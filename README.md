# llmwiki

> **LLM-powered knowledge base from your Claude Code, Codex CLI, Cursor, Gemini CLI, and Obsidian sessions.**
> Built on [Andrej Karpathy's LLM Wiki pattern](https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f).

## 👉 Live demo: **[pratiyush.github.io/llm-wiki](https://pratiyush.github.io/llm-wiki/)**

Rebuilt on every `master` push from the synthetic sessions in [`examples/demo-sessions/`](examples/demo-sessions). No personal data. Shows every feature of the real tool (activity heatmap, tool charts, token usage, model info cards, vs-comparisons, project topics) running against safe reference data.

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python 3.9+](https://img.shields.io/badge/python-3.9+-blue.svg)](https://www.python.org/)
[![Version](https://img.shields.io/badge/version-v1.1.0--rc2-10B981.svg)](CHANGELOG.md)
[![Tests](https://img.shields.io/badge/tests-1549%20passing-10B981.svg)](tests/)
[![CI](https://github.com/Pratiyush/llm-wiki/actions/workflows/ci.yml/badge.svg?branch=master)](https://github.com/Pratiyush/llm-wiki/actions/workflows/ci.yml)
[![Link check](https://github.com/Pratiyush/llm-wiki/actions/workflows/link-check.yml/badge.svg?branch=master)](https://github.com/Pratiyush/llm-wiki/actions/workflows/link-check.yml)
[![Wiki checks](https://github.com/Pratiyush/llm-wiki/actions/workflows/wiki-checks.yml/badge.svg?branch=master)](https://github.com/Pratiyush/llm-wiki/actions/workflows/wiki-checks.yml)
[![Docker](https://github.com/Pratiyush/llm-wiki/actions/workflows/docker-publish.yml/badge.svg)](https://github.com/Pratiyush/llm-wiki/pkgs/container/llm-wiki)
[![Works with Claude Code](https://img.shields.io/badge/Claude%20Code-✓-7C3AED.svg)](https://claude.com/claude-code)
[![Works with Codex CLI](https://img.shields.io/badge/Codex%20CLI-✓-7C3AED.svg)](https://github.com/openai/codex)
[![Works with Copilot](https://img.shields.io/badge/GitHub%20Copilot-✓-7C3AED.svg)](https://github.com/features/copilot)
[![Works with Cursor](https://img.shields.io/badge/Cursor-✓-7C3AED.svg)](https://cursor.com)
[![Works with Gemini CLI](https://img.shields.io/badge/Gemini%20CLI-✓-7C3AED.svg)](https://ai.google.dev/gemini-api)
[![Works with Obsidian](https://img.shields.io/badge/Obsidian-✓-7C3AED.svg)](https://obsidian.md)

---

Every Claude Code, Codex CLI, Copilot, Cursor, and Gemini CLI session writes a full transcript to disk. You already have hundreds of them and never look at them again.

**llmwiki** turns that dormant history into a beautiful, searchable, interlinked knowledge base — locally, in two commands. Plus, it produces AI-consumable exports (`llms.txt`, `llms-full.txt`, JSON-LD graph, per-page `.txt` + `.json` siblings) so other AI agents can query your wiki directly.

```bash
./setup.sh                         # one-time install
./build.sh && ./serve.sh           # build + serve at http://127.0.0.1:8765
```

![llm-wiki demo](docs/demo.gif)

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
  - Model info cards with structured schema (provider, pricing, benchmarks)
  - Auto-generated vs-comparison pages between AI models
  - Append-only changelog timeline with pricing sparkline
  - Project topic chips (GitHub-style tags on project cards)
  - Agent labels (colored badges: Claude/Codex/Copilot/Cursor/Gemini)
  - Recently-updated card on the home page
  - Dataview-style structured queries in the command palette
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

### Quality & governance (v1.0)
- **4-factor confidence scoring** — source count, source quality, recency, cross-references; with Ebbinghaus-inspired decay per content-type
- **5-state lifecycle machine** — draft → reviewed → verified → stale → archived with 90-day auto-stale
- **11 lint rules** — 8 structural (frontmatter, link integrity, orphans, freshness, duplicates, index sync…) + 3 LLM-powered (contradictions, claim verification, summary accuracy)
- **Auto Dream** — MEMORY.md consolidation after 24h + 5 sessions: resolve relative dates, prune outdated, 200-line cap
- **9 navigation files** — CLAUDE.md, AGENTS.md, MEMORY.md, SOUL.md, CRITICAL_FACTS.md, hints.md, hot.md + per-project hot caches

### Obsidian-native experience (v1.0)
- **`link-obsidian` CLI** — symlinks the whole project into an Obsidian vault; graph view + backlinks + full-text search just work
- **Dataview dashboard** — 10 ready-to-use queries (recently updated, by confidence, by lifecycle, by project, by entity type, open questions, stale pages)
- **Templater templates** — 4 templates for source/entity/concept/synthesis pages, seeded with confidence + lifecycle + today's date
- **Category pages** — tag-based index pages in both Dataview (Obsidian) and static markdown (HTML) modes
- **Integration guide** — [`docs/obsidian-integration.md`](docs/obsidian-integration.md) covers 6 recommended plugins with per-plugin configs

### Automation
- **SessionStart hook** — auto-syncs new sessions in the background on every Claude Code launch
- **File watcher** — `llmwiki watch` polls agent stores with debounce and runs sync on change
- **Auto-build on sync** — `/wiki-sync` triggers `/wiki-build` (configurable; default on)
- **Configurable scheduled sync** — `llmwiki schedule` generates OS-specific task files (launchd/systemd/Task Scheduler)
- **MCP server** — 12 production tools (query, search, list, read, lint, sync, export, + confidence, lifecycle, dashboard, entity search, category browse) queryable from any MCP client (Claude Desktop, Cline, Cursor, ChatGPT desktop)
- **Multi-agent skill mirror** — `llmwiki install-skills` mirrors `.claude/skills/` to `.codex/skills/` and `.agents/skills/`
- **Pending ingest queue** — SessionStart hook converts + queues; `/wiki-sync` processes queue
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

## Documentation

Full production documentation lives under [`docs/`](docs/). The editorial
hub is **[`docs/index.md`](docs/index.md)** — tutorials, per-agent guides,
reference, and deployment, all in one place.

**Start here:**

| Goal | Read |
|---|---|
| Install and build your first site in 10 minutes | [Tutorial 01 → 02](docs/tutorials/01-installation.md) |
| Use llmwiki with Claude Code | [Tutorial 03](docs/tutorials/03-use-with-claude-code.md) |
| Use llmwiki with Codex CLI | [Tutorial 04](docs/tutorials/04-use-with-codex-cli.md) |
| Query / lint / review your wiki daily | [Tutorial 05](docs/tutorials/05-querying-your-wiki.md) |
| Point llmwiki at an existing Obsidian / Logseq vault | [Tutorial 06](docs/tutorials/06-bring-your-obsidian-vault.md) |
| See four real end-to-end workflows | [Tutorial 07](docs/tutorials/07-example-workflows.md) |

Contributing to docs? See the **[style guide](docs/style-guide.md)**.

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

## Running E2E tests

The unit suite (`pytest tests/` — 472 tests) runs in milliseconds and
covers every module. The **end-to-end suite** under `tests/e2e/` is
separate: it builds a minimal demo site, serves it on a random port,
drives a real browser via [Playwright](https://playwright.dev/python),
and runs scenarios written in [Gherkin](https://cucumber.io/docs/gherkin/)
via [pytest-bdd](https://pytest-bdd.readthedocs.io/).

Why both? Unit tests lock the contract at the module boundary;
E2E locks the contract at the **user's browser**. A diff that passes
unit tests but breaks the Cmd+K palette will fail E2E.

Install the extras (one-time, ~300 MB for Chromium):

```bash
pip install -e '.[e2e]'
python -m playwright install chromium
```

Run the suite:

```bash
pytest tests/e2e/ --browser=chromium
```

Run a single feature:

```bash
pytest tests/e2e/test_command_palette.py --browser=chromium -v
```

The E2E suite is **excluded from the default `pytest tests/` run**
(see the `--ignore=tests/e2e` addopt in `pyproject.toml`) so you
can iterate on the unit suite without waiting for browser installs.
CI runs the E2E job as a separate workflow (`.github/workflows/e2e.yml`)
that only fires on PRs touching `build.py`, the viz modules, or
`tests/e2e/**`.

Feature files live under `tests/e2e/features/` — one per UI area
(homepage, session page, command palette, keyboard nav, mobile nav,
theme toggle, copy-as-markdown, **responsive breakpoints**, **edge
cases**, **accessibility**, **visual regression**). Step definitions
are all in `tests/e2e/steps/ui_steps.py`. Adding a new scenario is
usually a 2-line change to a `.feature` file plus maybe one new step.

Run locally with an HTML report:

```bash
pytest tests/e2e/ --browser=chromium \
  --html=e2e-report/index.html --self-contained-html
open e2e-report/index.html     # macOS — opens the browseable report
```

**Where to see test reports:**

| What | Where |
|---|---|
| Unit test results | GitHub Actions → `ci.yml` → latest run → `lint-and-test` job logs |
| E2E HTML report | GitHub Actions → `e2e.yml` → latest run → Artifacts → `e2e-html-report` (14-day retention) |
| Visual regression screenshots | Same run → Artifacts → `e2e-screenshots` |
| Playwright traces (failed runs only) | Same run → Artifacts → `playwright-traces` (open with `playwright show-trace <zip>`) |
| Demo site deploy status | GitHub Actions → `pages.yml` → latest run |

Locally, the HTML report is one file (`e2e-report/index.html`) that
you can open in any browser — pass/fail per scenario, duration,
stdout/stderr, screenshot on failure.

## Scheduled sync

Run `llmwiki schedule` to generate the right scheduled task file for your OS from your config (cadence, time, paths). Or copy a static template:

| OS | Auto-generate | Static template | Install guide |
|---|---|---|---|
| macOS | `llmwiki schedule --platform macos` | [`launchd.plist`](examples/scheduled-sync-templates/launchd.plist) | [docs/scheduled-sync.md](docs/scheduled-sync.md#macos-launchd) |
| Linux | `llmwiki schedule --platform linux` | [`systemd.timer`](examples/scheduled-sync-templates/llmwiki-sync.timer) + [`.service`](examples/scheduled-sync-templates/llmwiki-sync.service) | [docs/scheduled-sync.md](docs/scheduled-sync.md#linux-systemd) |
| Windows | `llmwiki schedule --platform windows` | [`task.xml`](examples/scheduled-sync-templates/llmwiki-sync-task.xml) | [docs/scheduled-sync.md](docs/scheduled-sync.md#windows-task-scheduler) |

Cadence (`daily` / `weekly` / `hourly`), hour/minute, and paths are all configurable in `examples/sessions_config.json`. See [`docs/scheduled-sync.md`](docs/scheduled-sync.md) for full instructions.

## CLI reference

```bash
llmwiki init                    # scaffold raw/ wiki/ site/ + seed nav files
llmwiki sync                    # convert .jsonl → markdown (auto-build + auto-lint if configured)
llmwiki build                   # compile static HTML + AI exports
llmwiki serve                   # local HTTP server on 127.0.0.1:8765
llmwiki adapters                # list available adapters + configured state (v1.0)
llmwiki graph                   # build knowledge graph (v0.2)
llmwiki watch                   # file watcher with debounce (v0.2)
llmwiki export-obsidian         # write wiki to Obsidian vault (v0.2)
llmwiki export-qmd              # export wiki as a qmd collection (v0.6)
llmwiki export-marp             # export Marp slide deck from wiki (v0.7)
llmwiki eval                    # 7-check structural quality score /100 (v0.3)
llmwiki lint                    # 11-rule wiki lint (8 basic + 3 LLM-powered, v1.0)
llmwiki check-links             # verify internal links in site/ (v0.4)
llmwiki export <format>         # AI-consumable exports (v0.4)
llmwiki synthesize              # auto-ingest synthesis pipeline (v0.5)
llmwiki manifest                # build site manifest + perf budget (v0.4)
llmwiki link-obsidian           # symlink project into Obsidian vault (v1.0)
llmwiki install-skills          # mirror .claude/skills to .codex/ and .agents/ (v1.0)
llmwiki schedule                # generate OS-specific scheduled sync task (v1.0)
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
| [Cursor](https://cursor.com) | `llmwiki.adapters.cursor` | ✅ Production | v0.5 |
| [Gemini CLI](https://ai.google.dev/gemini-api) | `llmwiki.adapters.gemini_cli` | ✅ Production | v0.5 |
| PDF files | `llmwiki.adapters.pdf` | ✅ Production | v0.5 |
| [Copilot Chat](https://github.com/features/copilot) | `llmwiki.adapters.copilot_chat` | ✅ Production | v0.9 |
| [Copilot CLI](https://github.com/features/copilot) | `llmwiki.adapters.copilot_cli` | ✅ Production | v0.9 |
| OpenCode / OpenClaw | — | ⏸ Deferred | — |

Adding a new agent is [one small file](docs/framework.md) — subclass `BaseAdapter`, declare `SUPPORTED_SCHEMA_VERSIONS`, ship a fixture + snapshot test.

## MCP server

llmwiki ships its own MCP server (stdio transport, no SDK dependency) so any MCP client can query your wiki directly.

```bash
python3 -m llmwiki.mcp   # runs on stdin/stdout
```

Twelve production tools (7 core + 5 added in v1.0 `#159`):

| Tool | What |
|---|---|
| `wiki_query(question, max_pages)` | Keyword search + page content (no LLM synthesis) |
| `wiki_search(term, include_raw)` | Raw grep over wiki/ (+ optional raw/) |
| `wiki_list_sources(project)` | List raw source files with metadata |
| `wiki_read_page(path)` | Read one page (path-traversal guarded) |
| `wiki_lint()` | Orphans + broken-wikilinks report |
| `wiki_sync(dry_run)` | Trigger the converter |
| `wiki_export(format)` | Return any AI-consumable export (llms.txt, jsonld, sitemap, rss, manifest) |
| `wiki_confidence(min, max)` | Pages by confidence range (v1.0) |
| `wiki_lifecycle(state)` | Pages by draft/reviewed/verified/stale/archived (v1.0) |
| `wiki_dashboard()` | Health summary: counts by type, lifecycle, confidence (v1.0) |
| `wiki_entity_search(name, entity_type)` | Search entities by name substring or type (v1.0) |
| `wiki_category_browse(tag)` | Browse tags with counts, drill into specific tag (v1.0) |

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

- **Stdlib first** — only mandatory runtime dep is `markdown`. `pypdf` is an optional extra for PDF ingestion.
- **Works offline** — no Google fonts, no external CSS. Syntax highlighting loads from a highlight.js CDN but degrades gracefully without it.
- **Redact by default** — username, API keys, tokens, emails all get redacted before entering the wiki.
- **Idempotent everything** — re-running any command is safe and cheap.
- **Agent-agnostic core** — the converter doesn't know which agent produced the `.jsonl`; adapters translate.
- **Privacy by default** — localhost-only binding, no telemetry, no cloud calls.
- **Dual-format output (v0.4)** — every page ships both for humans (HTML) and AI agents (TXT + JSON + JSON-LD + sitemap + llms.txt).

## Docs

- [Getting started](docs/getting-started.md) — 5-minute quickstart
- **[Setup guide](docs/tutorials/setup-guide.md)** — 15-minute end-to-end tutorial: local setup → deploy to GitHub Pages → customization (v1.0)
- [Obsidian integration](docs/obsidian-integration.md) — 5-minute setup, 6 recommended plugins, config recipes (v1.0)
- [Architecture](docs/architecture.md) — Karpathy 3-layer + 8-layer build breakdown
- [Configuration](docs/configuration.md) — every tuning knob
- [Privacy](docs/privacy.md) — redaction rules + `.llmwikiignore` + localhost binding
- [Scheduled sync](docs/scheduled-sync.md) — daily/weekly/hourly task setup per OS
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
- [Cursor adapter](docs/adapters/cursor.md)
- [Gemini CLI adapter](docs/adapters/gemini-cli.md)
- [Obsidian adapter](docs/adapters/obsidian.md)
- [PDF adapter](docs/adapters/pdf.md)
- [Copilot adapter (Chat + CLI)](docs/adapters/copilot.md)

## Releases

| Version | Focus | Tag |
|---|---|---|
| [v0.1.0](https://github.com/Pratiyush/llm-wiki/releases/tag/v0.1.0) | Core release — Claude Code adapter, god-level HTML UI, schema, CI, plugin scaffolding | `v0.1.0` |
| [v0.2.0](https://github.com/Pratiyush/llm-wiki/releases/tag/v0.2.0) | Extensions — 3 new slash commands, 3 new adapters, Obsidian bidirectional, full MCP server | `v0.2.0` |
| [v0.3.0](https://github.com/Pratiyush/llm-wiki/releases/tag/v0.3.0) | PyPI packaging, eval framework, i18n scaffold | `v0.3.0` |
| [v0.4.0](https://github.com/Pratiyush/llm-wiki/releases/tag/v0.4.0) | AI + human dual format — per-page .txt/.json siblings, llms.txt, JSON-LD graph, sitemap, RSS, schema.org microdata, reading time, related pages, activity heatmap, deep-link anchors, build manifest, link checker, `wiki_export` MCP tool | `v0.4.0` |
| v0.5.0 – v0.9.0 | Internal sprint milestones — features (`_context.md`, auto-ingest, qmd export, model-profile schema, activity heatmap, Copilot adapters, etc.) shipped consolidated under the v0.9.x line. No standalone tags were published. | — |
| [v0.9.1](https://github.com/Pratiyush/llm-wiki/releases/tag/v0.9.1) | Sprint 1 & 2 foundation — link-obsidian CLI, 4-factor confidence scoring, 5-state lifecycle machine, llmbook-reference skill, 7 entity types, flat raw/ naming, pending ingest queue, `_context.md` stubs, meeting + Jira adapters, configurable Web Clipper intake, rich log format | `v0.9.1` |
| [v0.9.2](https://github.com/Pratiyush/llm-wiki/releases/tag/v0.9.2) | Sprint 3 quality — 11 lint rules (8 basic + 3 LLM-powered), Auto Dream MEMORY.md consolidation, Dataview dashboard template, category pages (Dataview + static), auto-build on sync + configurable lint schedule | `v0.9.2` |
| [v0.9.3](https://github.com/Pratiyush/llm-wiki/releases/tag/v0.9.3) | Sprint 3 polish — Obsidian Templater templates, integration guide, two-way editing tests, MCP server 7→12 tools, adapter config validation, pipeline fix (sigstore, PyPI gate) | `v0.9.3` |
| [v0.9.4](https://github.com/Pratiyush/llm-wiki/releases/tag/v0.9.4) | Session C1 (Sprint 4) — multi-agent skill installer, enhanced search with facets, configurable scheduled sync (launchd/systemd/Task Scheduler), CI wiki-checks workflow | `v0.9.4` |
| [v0.9.5](https://github.com/Pratiyush/llm-wiki/releases/tag/v0.9.5) | Docs polish + consistency audit before v1.0.0 | `v0.9.5` |
| [v1.0.0](https://github.com/Pratiyush/llm-wiki/releases/tag/v1.0.0) | Production-ready Obsidian integration — full v1.0 scope | `v1.0.0` |
| [v1.1.0-rc1](https://github.com/Pratiyush/llm-wiki/releases/tag/v1.1.0-rc1) | Solo quick-win sprint — candidates workflow, Ollama scaffold, prompt-cache scaffold | `v1.1.0-rc1` |
| [v1.1.0-rc2](https://github.com/Pratiyush/llm-wiki/releases/tag/v1.1.0-rc2) | Session E — interactive graph viewer + remaining code-only v1.1 work | `v1.1.0-rc2` |

## Roadmap

Shipped milestones:

- **v0.5.0** — Folder-level `_context.md`, auto-ingest, adapter graduations, lazy search index, scheduled sync, WCAG, E2E tests ([milestone](https://github.com/Pratiyush/llm-wiki/milestone/4))
- **v0.6.0** — qmd export, GitLab Pages CI, PyPI release automation, maintainer governance scaffold ([milestone](https://github.com/Pratiyush/llm-wiki/milestone/5))
- **v0.7.0** — Structured model-profile schema, vs-comparison pages, append-only changelog timeline ([milestone](https://github.com/Pratiyush/llm-wiki/milestone/7))
- **v0.8.0** — 365-day activity heatmap, tool-calling bar chart, token usage card, session metrics frontmatter ([milestone](https://github.com/Pratiyush/llm-wiki/milestone/8))
- **v0.9.0** — Project topics, agent labels, Copilot adapters, image pipeline, highlight.js, public demo deployment
- **v0.9.x** — Sprint 1-4 foundation for v1.0.0 Obsidian integration: confidence scoring, lifecycle state machine, 9 navigation files, 11 lint rules, Auto Dream, Dataview dashboard, multi-agent skills, 12-tool MCP server, meeting + Jira adapters

Active milestones:

| Milestone | Focus | Tracking |
|---|---|---|
| **v1.0.0** | Final docs polish + PyPI trusted publisher + release | [Milestone](https://github.com/Pratiyush/llm-wiki/milestone/9) |
| **v1.1.0** | Ollama backend, prompt caching, interactive graph viewer, Homebrew tap | [Milestone](https://github.com/Pratiyush/llm-wiki/milestone/10) |
| **v1.2.0** | ChatGPT + OpenCode adapters, vault-overlay mode, tree-aware search, cache tiers | [Milestone](https://github.com/Pratiyush/llm-wiki/milestone/11) |

### Deployment targets

- **GitHub Pages** — shipped in v0.1 via `.github/workflows/pages.yml` (triggers on push to master). See [`docs/deploy/github-pages.md`](docs/deploy/github-pages.md).
- **Docker / GHCR** — pull and run: `docker compose pull && docker compose up -d`. Image published to `ghcr.io/pratiyush/llm-wiki` on every tag push. See [`docs/deploy/docker.md`](docs/deploy/docker.md).
- **GitLab Pages** — copy [`.gitlab-ci.yml.example`](.gitlab-ci.yml.example) → `.gitlab-ci.yml`. See [`docs/deploy/gitlab-pages.md`](docs/deploy/gitlab-pages.md).
- **Vercel / Netlify** — static deploy after `llmwiki build`. See [`docs/deploy/vercel-netlify.md`](docs/deploy/vercel-netlify.md).
- **Any static host** — `llmwiki build` writes to `site/`, which you can `rsync`/`scp` anywhere.

## Acknowledgements

- [Andrej Karpathy](https://twitter.com/karpathy) for [the LLM Wiki idea](https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f)
- [SamurAIGPT/llm-wiki-agent](https://github.com/SamurAIGPT/llm-wiki-agent), [lucasastorian/llmwiki](https://github.com/lucasastorian/llmwiki), [xoai/sage-wiki](https://github.com/xoai/sage-wiki), and [bashiraziz/llm-wiki-template](https://github.com/bashiraziz/llm-wiki-template) — prior art that shaped this.
- [Python Markdown](https://python-markdown.github.io/) for the rendering pipeline, and [highlight.js](https://highlightjs.org/) for client-side syntax highlighting.
- [llmstxt.org](https://llmstxt.org) for the llms.txt spec used in v0.4.

## License

[MIT](LICENSE) © Pratiyush
