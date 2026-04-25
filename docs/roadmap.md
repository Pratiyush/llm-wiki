# llmwiki Roadmap — Phase × Layer × Item, prioritised

**Last updated:** 2026-04-08

This document is the master plan. It slices the [feature matrix](feature-matrix.md) three ways so you can see:

- **By layer** — what you're building in each of the 8 architectural layers
- **By phase** — what ships in v0.1 vs v0.2 vs later
- **By priority** — MoSCoW ordering for execution sequence

## The 8 layers

Every feature belongs to exactly one architectural layer:

| Layer | What lives here | Owner |
|---|---|---|
| L0 Raw | Immutable converted markdown under `raw/` | Converter |
| L1 Wiki | LLM-maintained pages under `wiki/` | Agent (via slash commands) |
| L2 Site | Generated HTML under `site/` | Builder |
| L3 Viewer | HTTP server, search, keyboard shortcuts | Browser-side JS |
| L4 Distribution | Scripts, plugins, packaging | Setup/install |
| L5 Schema | `CLAUDE.md`, `AGENTS.md`, steering rules | Docs |
| L6 Adapters | Session-store parsers (Claude, Codex, Obsidian…) | Adapter registry |
| L7 CI/Ops | Tests, workflows, release automation | GitHub Actions |

## MoSCoW priority

| Priority | Meaning | When to ship |
|---|---|---|
| **M** = Must | v0.1 ships without this → the product fails | v0.1.0 |
| **S** = Should | Strong user value but v0.1 can survive without | v0.1.1 or v0.2.0 |
| **C** = Could | Nice to have; ship when a contributor or issue demands | v0.3+ |
| **W** = Won't | Considered and rejected for scope / philosophy reasons | Never in v1.x |

## The master table

Sorted **first by priority (M → S → C → W), then by layer (L0 → L7)**. Every row is a deliverable.

| Pri | Layer | ID | Item | Notes |
|:-:|:-:|:--|:--|:--|
| M | L0 | M-L0-01 | **Claude Code `.jsonl` adapter produces clean markdown** | Uses frontmatter, redacts PII, truncates tool output |
| M | L0 | M-L0-02 | **Redaction (username, API keys, tokens, emails)** on by default | Regex-based; patterns configurable |
| M | L0 | M-L0-03 | **Idempotent mtime state file** (`.llmwiki-state.json`) | Re-run is a sub-second no-op |
| M | L0 | M-L0-04 | **Live-session detection** — skip anything with last record `<60min` old | Prevents mid-write reads |
| M | L0 | M-L0-05 | **Sub-agent file handling** — render as separate page, link to parent | `is_subagent: true` in frontmatter |
| M | L0 | M-L0-06 | **`.llmwikiignore`** — skip listed files/projects | One pattern per line, gitignore syntax |
| M | L1 | M-L1-01 | `/wiki-ingest` workflow in CLAUDE.md + AGENTS.md | Karpathy 10-step flow |
| M | L1 | M-L1-02 | `/wiki-query` workflow with `[[wikilink]]` citations | |
| M | L1 | M-L1-03 | `/wiki-lint` workflow — orphans, broken links, contradictions, stale | |
| M | L1 | M-L1-04 | `/wiki-init` scaffold | Creates `raw/`, `wiki/`, seeds `index.md`, `log.md`, `overview.md` |
| M | L1 | M-L1-05 | Source page template with YAML frontmatter | `title`, `type: source`, `tags`, `date`, `source_file`, `project` |
| M | L1 | M-L1-06 | Entity page template (`TitleCase.md`) | `title`, `type: entity`, `sources`, `last_updated` |
| M | L1 | M-L1-07 | Concept page template (`TitleCase.md`) | Same as entity but `type: concept` |
| M | L1 | M-L1-08 | Synthesis page template (`kebab-case.md`) | For saved `/wiki-query` answers |
| M | L1 | M-L1-09 | `index.md` catalog format | Sections: Overview / Sources / Entities / Concepts / Syntheses |
| M | L1 | M-L1-10 | `log.md` append-only format | `## [YYYY-MM-DD] <op> \| <title>` grep-parseable |
| M | L1 | M-L1-11 | `overview.md` living synthesis | Updated on every ingest if warranted |
| M | L1 | M-L1-12 | Contradiction-tracking rule | Never silently overwrite, record both claims |
| M | L2 | M-L2-01 | **HTML builder with god-level CSS** (Inter + JetBrains Mono + purple accent) | Single `build.py` |
| M | L2 | M-L2-02 | Python-markdown with `fenced_code`, `tables`, `toc`, `sane_lists` | Plus normaliser for bad list indent |
| M | L2 | M-L2-03 | **highlight.js syntax highlighting** for all fenced code blocks | Client-side, loaded from CDN |
| M | L2 | M-L2-04 | Per-session HTML page with breadcrumbs | Home › project › session |
| M | L2 | M-L2-05 | Per-project HTML page with session cards | Main sessions + sub-agents collapsed |
| M | L2 | M-L2-06 | Projects index page | Card grid |
| M | L2 | M-L2-07 | Sessions index page with sticky header | Sortable table |
| M | L2 | M-L2-08 | Home page with overview (claude CLI synthesis optional) | `--synthesize` flag |
| M | L2 | M-L2-09 | Strip duplicate H1 from session bodies | Hero already shows title |
| M | L2 | M-L2-10 | Normalise 2-space-indented fenced code blocks | Converter emits them indented inside lists |
| M | L2 | M-L2-11 | Pre-built client-side search index (JSON) | For L3 search to consume |
| M | L3 | M-L3-01 | **Cmd+K command palette** (vanilla JS) | Keyboard-driven nav |
| M | L3 | M-L3-02 | **Global fuzzy search** over pre-built index | Substring + token match |
| M | L3 | M-L3-03 | **Keyboard shortcuts**: `/` focus search, `Esc` clear, `g h` home, `g p` projects, `g s` sessions, `j/k` next/prev on tables | |
| M | L3 | M-L3-04 | **Dark mode toggle** with `data-theme` attribute + localStorage + system default | |
| M | L3 | M-L3-05 | **Copy-as-markdown button** on session pages (hidden textarea source) | Clipboard API + execCommand fallback |
| M | L3 | M-L3-06 | **Copy-code button** on every `<pre>` (JS-wrapped) | On-hover visibility |
| M | L3 | M-L3-07 | **Collapsible tool-result sections** (`<details>`) over 500 chars | Click to expand |
| M | L3 | M-L3-08 | **Reading progress bar** (CSS scroll-linked) | Top of the page |
| M | L3 | M-L3-09 | **Filter bar** on sessions table (project dropdown, date range, model) | Client-side JS filter |
| M | L3 | M-L3-10 | **Download .md button** on every session page | Links to `sources/<path>.md` copy |
| M | L3 | M-L3-11 | **Toast notifications** on copy success | 1.5s fade |
| M | L3 | M-L3-12 | **Focus rings** (a11y) + `prefers-reduced-motion` | |
| M | L3 | M-L3-13 | Mobile responsive (320 / 768 / 1080 breakpoints) | |
| M | L3 | M-L3-14 | Print-friendly CSS | `@media print` |
| M | L3 | M-L3-15 | HTTP server (`python3 -m http.server` wrapper) bound to 127.0.0.1 | `llmwiki serve --port 8765` |
| M | L4 | M-L4-01 | **`setup.sh` / `setup.bat`** — install + first sync | Idempotent, tested |
| M | L4 | M-L4-02 | **`sync.sh` / `sync.bat`** — convert new sessions | Wrapper over `python3 -m llmwiki sync` |
| M | L4 | M-L4-03 | **`build.sh` / `build.bat`** — regenerate HTML | `python3 -m llmwiki build` |
| M | L4 | M-L4-04 | **`serve.sh` / `serve.bat`** — start server | `python3 -m llmwiki serve` |
| M | L4 | M-L4-05 | `upgrade.sh` / `upgrade.bat` — pull + re-run setup | |
| M | L4 | M-L4-06 | `python3 -m llmwiki` module entry (`__main__.py`) | |
| M | L4 | M-L4-07 | `llmwiki.cli.main()` argparse CLI with subcommands | `init`, `sync`, `build`, `serve`, `adapters`, `version` |
| M | L4 | M-L4-08 | `python3 -m llmwiki adapters` lists available adapters | Shows which are installed on this machine |
| M | L5 | M-L5-01 | `CLAUDE.md` schema with Ingest / Query / Lint workflows | Karpathy-compliant |
| M | L5 | M-L5-02 | `AGENTS.md` schema (mirror CLAUDE.md, agent-agnostic) | |
| M | L5 | M-L5-03 | **`.kiro/steering/` always-loaded rules** | contributing, page-format, verification |
| M | L5 | M-L5-04 | `docs/framework.md` — adapted open-source framework | With research phase + kiro style |
| M | L5 | M-L5-05 | `docs/architecture.md` — three-layer + 8-layer breakdown | |
| M | L5 | M-L5-06 | `docs/research.md` — Phase 1.25 research report | |
| M | L5 | M-L5-07 | `docs/feature-matrix.md` — all 161 features | |
| M | L5 | M-L5-08 | `docs/roadmap.md` — this document | |
| M | L5 | M-L5-09 | `docs/getting-started.md` — user install + first run | |
| M | L5 | M-L5-10 | `docs/configuration.md` — every config option | |
| M | L5 | M-L5-11 | `docs/adapters/claude-code.md` — Claude adapter usage | |
| M | L5 | M-L5-12 | `docs/adapters/codex-cli.md` — Codex adapter usage | |
| M | L5 | M-L5-13 | `docs/adapters/obsidian.md` — Obsidian adapter usage | |
| M | L5 | M-L5-14 | `docs/windows-setup.md` — Windows gotchas | |
| M | L5 | M-L5-15 | `docs/privacy.md` — redaction + local-only binding + no telemetry | |
| M | L5 | M-L5-16 | `README.md` with badges, pitch, demo link, install | |
| M | L5 | M-L5-17 | `CHANGELOG.md` per Keep-a-Changelog | |
| M | L5 | M-L5-18 | `LICENSE` (MIT) | |
| M | L6 | M-L6-01 | `llmwiki.adapters.base.BaseAdapter` | Interface + defaults |
| M | L6 | M-L6-02 | `llmwiki.adapters.claude_code.ClaudeCodeAdapter` | Production |
| M | L6 | M-L6-03 | `llmwiki.adapters.codex_cli.CodexCliAdapter` | v0.1 **stub** |
| M | L6 | M-L6-04 | **`llmwiki.adapters.obsidian.ObsidianAdapter`** | Reads `~/Documents/Obsidian Vault/` |
| M | L6 | M-L6-05 | Adapter auto-discovery | `REGISTRY` populated on import |
| M | L6 | M-L6-06 | `SUPPORTED_SCHEMA_VERSIONS` constant per adapter | Schema-version rule |
| M | L6 | M-L6-07 | Graceful degradation on unknown record types | Log DEBUG, never crash |
| M | L7 | M-L7-01 | `.github/workflows/ci.yml` — lint + build smoke on push/PR | |
| M | L7 | M-L7-02 | `.github/workflows/gitleaks.yml` — secret scan | |
| M | L7 | M-L7-03 | `.github/workflows/pages.yml` — GitHub Pages on tag push | |
| M | L7 | M-L7-04 | `tests/fixtures/claude_code/*.jsonl` — synthetic fixtures | |
| M | L7 | M-L7-05 | `tests/test_claude_adapter.py` — snapshot tests | |
| M | L7 | M-L7-06 | `tests/test_convert.py` — converter unit tests | |
| M | L7 | M-L7-07 | `tests/test_build.py` — HTML build smoke | |
| M | L7 | M-L7-08 | Privacy grep in CI (`grep -r '<real_username>' site/` → fail on hit) | |
| M | L7 | M-L7-09 | Performance budget check — build time `<15s`, HTML `<50MB` | |
| M | L7 | M-L7-10 | `CONTRIBUTING.md` + PR template + issue templates | |
| S | L0 | S-L0-01 | Obsidian adapter reads `.md` files directly (no conversion) | Skip `.obsidian/`, trash, templates |
| S | L0 | S-L0-02 | Cursor adapter | |
| S | L0 | S-L0-03 | PDF ingestion (pypdf) | |
| S | L1 | S-L1-01 | `/wiki-update` — update existing page only | |
| S | L1 | S-L1-02 | `/wiki-graph` — networkx + vis.js knowledge graph | |
| S | L1 | S-L1-03 | `/wiki-reflect` — self-reflection across all wiki | |
| S | L1 | S-L1-04 | `/wiki-archive` — move stale entries to `wiki/archive/` | |
| S | L1 | S-L1-05 | Comparison page type (`wiki/comparisons/`) | |
| S | L1 | S-L1-06 | Question page type (`wiki/questions/`) | |
| S | L2 | S-L2-01 | Timeline view of sessions | |
| S | L2 | S-L2-02 | Tag cloud / tag index page | |
| S | L2 | S-L2-03 | Knowledge graph HTML (vis.js) | |
| S | L2 | S-L2-04 | Backlinks section at the bottom of every page | |
| S | L3 | S-L3-01 | Hover-to-preview wikilinks | |
| S | L3 | S-L3-02 | Session timeline chart (sparkline) | |
| S | L3 | S-L3-03 | Search result snippets with highlights | |
| S | L3 | S-L3-04 | Scroll-spy for breadcrumbs | |
| M | L4 | M-L4-09 | **Claude Code plugin packaging** (`.claude-plugin/plugin.json` + `marketplace.json`) | Promoted from S → M on 2026-04-08 |
| M | L4 | M-L4-10 | `.claude/commands/wiki-sync.md`, `wiki-ingest.md`, `wiki-query.md`, `wiki-lint.md`, `wiki-build.md`, `wiki-serve.md` | 6 slash commands |
| M | L4 | M-L4-11 | `.claude/skills/llmwiki-sync/SKILL.md` + `llmwiki-ingest/SKILL.md` + `llmwiki-query/SKILL.md` | Auto-discoverable skills |
| M | L4 | M-L4-12 | **MCP server** exposing `wiki_query`, `wiki_ingest`, `wiki_search`, `wiki_lint` tools | Promoted from S → M on 2026-04-08. Stub in v0.1, full in v0.2. |
| M | L4 | M-L4-13 | `.claude/launch.json` for Claude_Preview integration | Lets contributors preview llmwiki from inside Claude Code |
| S | L4 | S-L4-01 | Claude Code plugin packaging (`.claude-plugin/plugin.json`) | marketplace-ready |
| S | L4 | S-L4-02 | `pip install llm-notebook` on PyPI | |
| S | L4 | S-L4-03 | Homebrew formula | |
| S | L5 | S-L5-01 | Domain examples (personal / research / business) | |
| S | L5 | S-L5-02 | Use-case examples (solo / team / multi-agent) | |
| S | L5 | S-L5-03 | MCP server doc | |
| S | L5 | S-L5-04 | Knowledge-system playbook | |
| S | L6 | S-L6-01 | Codex CLI full implementation (from stub) | |
| S | L6 | S-L6-02 | Gemini CLI adapter | |
| S | L6 | S-L6-03 | Cursor adapter | |
| S | L6 | S-L6-04 | OpenCode / OpenClaw adapter | |
| S | L7 | S-L7-01 | Release automation (tag-push → GitHub Release) | |
| S | L7 | S-L7-02 | Dependabot for GitHub Actions | |
| S | L7 | S-L7-03 | Link checker in CI | |
| C | L1 | C-L1-01 | `/wiki-merge` — merge two vaults | |
| C | L1 | C-L1-02 | `/wiki-compile` — multi-step pipeline | |
| C | L2 | C-L2-01 | Inline diff view for `/wiki-update` changes | |
| C | L3 | C-L3-01 | Page transitions / subtle animations | |
| C | L4 | C-L4-01 | Docker image | |
| C | L5 | C-L5-01 | i18n for docs (zh-CN, ja, es) | |
| C | L6 | C-L6-01 | Web clipper / URL ingestion | |
| C | L6 | C-L6-02 | Image ingestion (OCR) | |
| C | L6 | C-L6-03 | Local LLM via Ollama | |
| C | L7 | C-L7-01 | Eval framework (LLM-judged wiki quality) | |
| C | L7 | C-L7-02 | SQLite FTS5 server-side search fallback | |
| W | L0 | W-L0-01 | Slack / Discord export ingestion | Out of scope |
| W | L2 | W-L2-01 | TUI browser | Defer to raine/claude-history |
| W | L3 | W-L3-01 | Real-time collaborative editing | Not a product goal |
| W | L4 | W-L4-01 | Precompiled Go/Rust binary | Python-first policy |
| W | L7 | W-L7-01 | Sentry / telemetry | Privacy rule |
| W | L7 | W-L7-02 | Supabase / Postgres backend | Stdlib-first rule |

## Summary by layer

| Layer | Must | Should | Could | Won't | Total |
|---|:-:|:-:|:-:|:-:|:-:|
| L0 Raw | 6 | 3 | 0 | 1 | 10 |
| L1 Wiki | 12 | 6 | 2 | 0 | 20 |
| L2 Site | 11 | 4 | 1 | 1 | 17 |
| L3 Viewer | 15 | 4 | 1 | 1 | 21 |
| L4 Distribution | 8 | 3 | 1 | 1 | 13 |
| L5 Schema/Docs | 18 | 4 | 1 | 0 | 23 |
| L6 Adapters | 7 | 4 | 3 | 0 | 14 |
| L7 CI/Ops | 10 | 3 | 2 | 2 | 17 |
| **TOTAL** | **87** | **31** | **11** | **6** | **135** |

**v0.1 ships with 87 Must-have items.** Everything else is roadmap.

## Summary by phase

| Phase | Focus | Items |
|---|---|---|
| v0.1.0 | Claude Code adapter + god-level UI + schema + CI | All 87 M rows |
| v0.1.x | Bug fixes, docs polish, perf tweaks | From feedback |
| v0.2.0 | Obsidian (bidirectional) + `/wiki-update` + `/wiki-graph` + Claude Code plugin + Cursor adapter | S rows in L1/L2/L3/L6 |
| v0.3.0 | Codex CLI full + Gemini CLI + PDF + Tag cloud + PyPI | Remaining S rows |
| v0.4.0 | Local LLM (Ollama) + Web clipper + Docker | C rows |
| v1.0.0 | Stabilised schema + production adapter test suite + full docs i18n | Lock the API |

## Execution sequence

Because everything in the Must list is already scoped, the execution order that minimises rework is:

1. **L5 first** — Schema files (CLAUDE.md, AGENTS.md, docs, tasks, progress). Done, validates the plan.
2. **L6 registry + base** — Adapter interface. Done.
3. **L0 converter** — Claude Code adapter + redaction + state. Done.
4. **L2 builder** — God-level HTML. **← current work**
5. **L3 viewer JS** — Command palette, search, shortcuts, copy buttons. **← current work**
6. **L4 scripts** — Shell + batch wrappers around the CLI.
7. **L7 tests** — Fixtures, snapshot tests, privacy grep, CI workflows.
8. **L1 seed** — `/wiki-init` seeds + sample ingest for the self-demo.

## How to use this document

- When claiming an item as done, mark it ✅ in the **Status** column of `tasks.md`.
- When adding a new feature idea, add a row here first (with priority + layer) before writing code.
- When cutting scope, move from M → S, not M → delete. Nothing gets silently dropped.
