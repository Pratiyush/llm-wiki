# Feature Matrix — Every Feature Across the 15 Prior Implementations

**Method:** Cloned and inspected every referenced repo. Listed every feature I found in any of them, rated each by target value to llmwiki (1–5), and marked which ones are already present in at least one reference implementation vs. which are a net-new invention for llmwiki.

**Value legend:**

| Rating | Meaning |
|---|---|
| ⭐⭐⭐⭐⭐ | God-level — killer feature, llmwiki ships without it is pointless |
| ⭐⭐⭐⭐ | Strong must-have — ship in v0.1 |
| ⭐⭐⭐ | Should-have — ship in v0.2 or v0.3 |
| ⭐⭐ | Could-have — ship when there's demand |
| ⭐ | Won't-have — researched and rejected |

## A · Core wiki workflows

| # | Feature | Value | Prior art | llmwiki phase |
|---|---|---|---|---|
| A1 | `/wiki-ingest` — read source → write wiki page | ⭐⭐⭐⭐⭐ | SamurAIGPT, kfchou, bashiraziz, Ss1024sS, hsuanguo, louiswang524 | v0.1 |
| A2 | `/wiki-query` — answer questions with citations | ⭐⭐⭐⭐⭐ | Same as above | v0.1 |
| A3 | `/wiki-lint` — orphans / contradictions / stale | ⭐⭐⭐⭐⭐ | Same as above | v0.1 |
| A4 | `/wiki-init` — scaffold empty wiki | ⭐⭐⭐⭐ | kfchou, hsuanguo | v0.1 |
| A5 | `/wiki-update` — update existing page without full re-ingest | ⭐⭐⭐ | kfchou, hsuanguo | v0.2 |
| A6 | `/wiki-graph` — knowledge graph (networkx/vis.js) | ⭐⭐⭐⭐ | SamurAIGPT | v0.2 |
| A7 | `/wiki-compile` — multi-step pipeline (plan → write → validate) | ⭐⭐⭐ | kytmanov, lucasastorian | v0.3 |
| A8 | `/wiki-reflect` — self-reflection over the whole wiki | ⭐⭐⭐ | louiswang524 | v0.2 |
| A9 | `/wiki-merge` — merge two wikis / vaults | ⭐⭐ | louiswang524 | v0.3 |
| A10 | `/wiki-archive` — move stale entries to archive | ⭐⭐⭐ | Astro-Han | v0.2 |

## B · Input adapters (data sources)

| # | Feature | Value | Prior art | llmwiki phase |
|---|---|---|---|---|
| B1 | **Claude Code `.jsonl` adapter** (killer feature) | ⭐⭐⭐⭐⭐ | **None** | v0.1 |
| B2 | **Codex CLI adapter** | ⭐⭐⭐⭐⭐ | bashiraziz (stub), Ss1024sS (script only) | v0.1 stub, v0.2 full |
| B3 | **Obsidian vault adapter** (input mode) | ⭐⭐⭐⭐ | AgriciDaniel, louiswang524, kytmanov, remember-md | v0.1 |
| B4 | Generic markdown (drop in `raw/`) | ⭐⭐⭐⭐ | All | v0.1 |
| B5 | Cursor adapter | ⭐⭐⭐ | bashiraziz | v0.2 |
| B6 | Gemini CLI adapter | ⭐⭐⭐ | SamurAIGPT (schema only) | v0.3 |
| B7 | OpenCode/OpenClaw adapter | ⭐⭐⭐ | remember-md, sinzin91 | v0.3 |
| B8 | PDF ingestion | ⭐⭐⭐ | lucasastorian | v0.3 |
| B9 | URL / web-clipper ingestion | ⭐⭐ | kytmanov | v0.4 |
| B10 | Image ingestion (screenshots, diagrams) | ⭐⭐ | louiswang524 (mentioned) | v0.4 |
| B11 | Slack / Discord export | ⭐ | — | won't |

## C · Page types / templates

| # | Feature | Value | Prior art | llmwiki phase |
|---|---|---|---|---|
| C1 | Source page (`wiki/sources/`) | ⭐⭐⭐⭐⭐ | All | v0.1 |
| C2 | Entity page (`wiki/entities/`) | ⭐⭐⭐⭐⭐ | Most | v0.1 |
| C3 | Concept page (`wiki/concepts/`) | ⭐⭐⭐⭐⭐ | Most | v0.1 |
| C4 | Synthesis page (`wiki/syntheses/`) | ⭐⭐⭐⭐ | SamurAIGPT, kfchou | v0.1 |
| C5 | **Comparison page** (side-by-side diff of 2+ entities) | ⭐⭐⭐⭐ | AgriciDaniel | v0.2 |
| C6 | **Question page** (open questions as first-class entries) | ⭐⭐⭐⭐ | AgriciDaniel | v0.2 |
| C7 | Archive page (demoted / deprecated entries) | ⭐⭐⭐ | Astro-Han | v0.2 |
| C8 | Insight page | ⭐⭐ | hsuanguo | v0.3 |
| C9 | Summary page | ⭐⭐⭐ | hsuanguo | v0.2 |
| C10 | `index.md` catalog | ⭐⭐⭐⭐⭐ | All | v0.1 |
| C11 | `overview.md` living synthesis | ⭐⭐⭐⭐⭐ | All | v0.1 |
| C12 | `log.md` append-only log | ⭐⭐⭐⭐⭐ | All | v0.1 |

## D · Output / viewer

| # | Feature | Value | Prior art | llmwiki phase |
|---|---|---|---|---|
| D1 | **Static HTML site (no deps, no auth)** | ⭐⭐⭐⭐⭐ | xoai (basic), lucasastorian (auth-walled) | v0.1 |
| D2 | **Cmd+K command palette** | ⭐⭐⭐⭐⭐ | **None** | v0.1 |
| D3 | **Global client-side search (pre-built index)** | ⭐⭐⭐⭐⭐ | **None** | v0.1 |
| D4 | **Syntax highlighting (Pygments)** | ⭐⭐⭐⭐⭐ | **None** | v0.1 |
| D5 | **Dark mode toggle with system preference** | ⭐⭐⭐⭐⭐ | lucasastorian web only | v0.1 |
| D6 | **Keyboard shortcuts** (`/`, `g h`, `j/k`) | ⭐⭐⭐⭐⭐ | **None** | v0.1 |
| D7 | **Breadcrumbs** on session pages | ⭐⭐⭐⭐ | **None** | v0.1 |
| D8 | **Collapsible tool-result sections** | ⭐⭐⭐⭐ | **None** | v0.1 |
| D9 | **Reading-progress bar on long pages** | ⭐⭐⭐⭐ | **None** | v0.1 |
| D10 | **Sticky table headers** on sessions index | ⭐⭐⭐⭐ | **None** | v0.1 |
| D11 | **Mobile responsive** | ⭐⭐⭐⭐ | lucasastorian web | v0.1 |
| D12 | **Print-friendly CSS** | ⭐⭐⭐ | **None** | v0.1 |
| D13 | Copy-as-markdown button on every page | ⭐⭐⭐⭐⭐ | **None** | v0.1 |
| D14 | Copy-code button on every `<pre>` | ⭐⭐⭐⭐⭐ | **None** | v0.1 |
| D15 | Download-source-md button | ⭐⭐⭐⭐ | **None** | v0.1 |
| D16 | Anchor links on every heading | ⭐⭐⭐⭐ | SamurAIGPT, others | v0.1 |
| D17 | Knowledge graph view (vis.js) | ⭐⭐⭐⭐ | SamurAIGPT | v0.2 |
| D18 | Obsidian vault as viewer (export mode) | ⭐⭐⭐⭐ | AgriciDaniel, louiswang524 | v0.1 (export), v0.2 (bidirectional) |
| D19 | TUI browser | ⭐⭐ | raine | won't (use their tool) |
| D20 | Timeline view of sessions | ⭐⭐⭐ | **None** | v0.2 |
| D21 | Filter bar on sessions table (project, date, model) | ⭐⭐⭐⭐ | **None** | v0.1 |
| D22 | Hover-to-preview wikilinks (like Obsidian Page Preview) | ⭐⭐⭐⭐ | **None** | v0.2 |

## E · Distribution

| # | Feature | Value | Prior art | llmwiki phase |
|---|---|---|---|---|
| E1 | `git clone + ./setup.sh` (macOS/Linux) | ⭐⭐⭐⭐⭐ | Most | v0.1 |
| E2 | `git clone + setup.bat` (Windows) | ⭐⭐⭐⭐⭐ | Few | v0.1 |
| E3 | `pip install -e .` local mode | ⭐⭐⭐⭐ | hsuanguo | v0.1 |
| E4 | **Claude Code plugin** (marketplace install) | ⭐⭐⭐⭐⭐ | kfchou, sinzin91, remember-md | v0.2 |
| E5 | Homebrew formula | ⭐⭐⭐ | raine (Go) | v0.3 |
| E6 | Precompiled single binary (Go/Rust?) | ⭐⭐ | sinzin91 (Go) | won't (Python) |
| E7 | `pip install llm-notebook` on PyPI | ⭐⭐⭐⭐ | lucasastorian | v0.3 |
| E8 | Docker image | ⭐⭐ | — | v0.4 |

## F · Multi-agent support

| # | Feature | Value | Prior art | llmwiki phase |
|---|---|---|---|---|
| F1 | `CLAUDE.md` schema | ⭐⭐⭐⭐⭐ | All | v0.1 |
| F2 | `AGENTS.md` schema (Codex, OpenCode) | ⭐⭐⭐⭐⭐ | SamurAIGPT, Ss1024sS, bashiraziz | v0.1 |
| F3 | `GEMINI.md` schema | ⭐⭐⭐⭐ | SamurAIGPT | v0.2 |
| F4 | `UNIVERSAL.md` — one schema for all agents | ⭐⭐⭐ | Ss1024sS | v0.2 |
| F5 | Adapter registry (`llmwiki.adapters.REGISTRY`) | ⭐⭐⭐⭐⭐ | **None** (bashiraziz has folders, not registry) | v0.1 |
| F6 | Schema version tracking per adapter | ⭐⭐⭐⭐ | **None** | v0.1 |
| F7 | Graceful degradation on unknown record types | ⭐⭐⭐⭐⭐ | **None** | v0.1 |

## G · Infrastructure

| # | Feature | Value | Prior art | llmwiki phase |
|---|---|---|---|---|
| G1 | Raw-file mtime tracker (idempotent sync) | ⭐⭐⭐⭐⭐ | hsuanguo, llmwiki state file | v0.1 |
| G2 | **File watcher (auto-resync on .jsonl change)** | ⭐⭐⭐⭐ | bitsofchris, kytmanov | v0.2 |
| G3 | Git ops integration (auto-commit wiki changes) | ⭐⭐⭐ | kytmanov | v0.2 |
| G4 | **MCP server (expose wiki as tools to agents)** | ⭐⭐⭐⭐⭐ | bitsofchris, lucasastorian | v0.2 |
| G5 | SQLite backend (structured queries) | ⭐⭐⭐ | bashiraziz | v0.3 |
| G6 | Supabase / Postgres backend | ⭐ | lucasastorian | won't |
| G7 | Sentry error tracking | ⭐ | lucasastorian | won't |
| G8 | SessionStart hook auto-sync | ⭐⭐⭐⭐⭐ | remember-md | v0.1 |
| G9 | UserPromptSubmit hook (contextual wiki injection) | ⭐⭐⭐ | remember-md | v0.2 |
| G10 | Live-session detection (skip `<60min` old) | ⭐⭐⭐⭐⭐ | **None** | v0.1 |

## H · Search / discovery

| # | Feature | Value | Prior art | llmwiki phase |
|---|---|---|---|---|
| H1 | **Client-side search index (JSON + fuzzy matcher)** | ⭐⭐⭐⭐⭐ | **None** | v0.1 |
| H2 | Server-side full-text (SQLite FTS5) | ⭐⭐⭐ | bashiraziz | v0.3 |
| H3 | Rerank results by relevance | ⭐⭐ | bitsofchris | v0.3 |
| H4 | Taxonomy / faceted filtering | ⭐⭐⭐ | bitsofchris | v0.2 |
| H5 | Backlinks (bidirectional `[[wikilinks]]`) | ⭐⭐⭐⭐⭐ | **None explicit** | v0.1 |
| H6 | Tag cloud / tag index | ⭐⭐⭐ | **None** | v0.2 |

## I · Testing & quality

| # | Feature | Value | Prior art | llmwiki phase |
|---|---|---|---|---|
| I1 | Unit tests (pytest) | ⭐⭐⭐⭐⭐ | bitsofchris, kytmanov, hsuanguo, lucasastorian | v0.1 |
| I2 | Snapshot tests for adapters | ⭐⭐⭐⭐⭐ | **None** | v0.1 |
| I3 | Fixture-based end-to-end tests | ⭐⭐⭐⭐⭐ | bitsofchris, kytmanov | v0.1 |
| I4 | Eval framework (LLM-judged wiki quality) | ⭐⭐⭐ | xoai | v0.3 |
| I5 | Link checker (CI) | ⭐⭐⭐⭐ | **None explicit** | v0.1 |
| I6 | **Gitleaks secret scanning in CI** | ⭐⭐⭐⭐⭐ | sinzin91 | v0.1 |
| I7 | Privacy check (grep for real PII in fixtures) | ⭐⭐⭐⭐⭐ | **None** | v0.1 |
| I8 | Performance budget enforcement | ⭐⭐⭐⭐ | **None** | v0.1 |

## J · CI / CD

| # | Feature | Value | Prior art | llmwiki phase |
|---|---|---|---|---|
| J1 | `ci.yml` — lint + test on every PR | ⭐⭐⭐⭐⭐ | kytmanov, sinzin91 | v0.1 |
| J2 | `pages.yml` — deploy GitHub Pages demo | ⭐⭐⭐⭐⭐ | xoai | v0.1 |
| J3 | `release.yml` — tag-push releases | ⭐⭐⭐⭐ | sinzin91, kytmanov | v0.2 |
| J4 | PR-merge auto-release | ⭐⭐⭐ | sinzin91 | v0.2 |
| J5 | Version check script | ⭐⭐⭐ | Ss1024sS | v0.2 |
| J6 | Upgrade flow (`./upgrade.sh`) | ⭐⭐⭐⭐ | Ss1024sS | v0.1 |
| J7 | Dependabot (even with no deps — track GHA versions) | ⭐⭐⭐ | many | v0.1 |

## K · Documentation

| # | Feature | Value | Prior art | llmwiki phase |
|---|---|---|---|---|
| K1 | `README.md` with install + demo | ⭐⭐⭐⭐⭐ | All | v0.1 |
| K2 | `SETUP-GUIDE.md` with per-OS instructions | ⭐⭐⭐⭐ | bashiraziz, Ss1024sS | v0.1 |
| K3 | `QUICK-REFERENCE.md` — one-page cheat sheet | ⭐⭐⭐⭐ | bashiraziz | v0.1 |
| K4 | `CHANGELOG.md` | ⭐⭐⭐⭐⭐ | Most | v0.1 |
| K5 | Per-version release notes | ⭐⭐⭐ | Ss1024sS | v0.2 |
| K6 | `ARCHITECTURE.md` formal architecture | ⭐⭐⭐⭐⭐ | bitsofchris, sinzin91 | v0.1 |
| K7 | Knowledge-system playbook | ⭐⭐⭐⭐ | Ss1024sS | v0.1 |
| K8 | Ingest-pipeline doc | ⭐⭐⭐⭐ | Ss1024sS | v0.1 |
| K9 | MCP server doc | ⭐⭐⭐ | bitsofchris | v0.2 |
| K10 | Windows-specific setup doc | ⭐⭐⭐⭐ | bashiraziz | v0.1 |
| K11 | Obsidian integration doc | ⭐⭐⭐⭐ | bashiraziz | v0.1 |
| K12 | Benchmarks doc | ⭐⭐⭐⭐ | sinzin91 | v0.1 |
| K13 | Phased plans (m0/m1/m2/phase2/phase3) | ⭐⭐⭐⭐⭐ | bitsofchris | v0.1 (= `_progress.md`) |
| K14 | Domain examples (personal/research/business) | ⭐⭐⭐⭐ | bashiraziz | v0.2 |
| K15 | Use-case examples (solo/team/multi) | ⭐⭐⭐⭐ | bashiraziz | v0.2 |

## L · Configuration

| # | Feature | Value | Prior art | llmwiki phase |
|---|---|---|---|---|
| L1 | JSON config with defaults | ⭐⭐⭐⭐⭐ | Most | v0.1 |
| L2 | `config.defaults.json` + user override | ⭐⭐⭐⭐ | remember-md | v0.1 |
| L3 | Environment variable support (`LLMWIKI_*`) | ⭐⭐⭐⭐ | — | v0.1 |
| L4 | Plugin manifest (`.claude-plugin/plugin.json`) | ⭐⭐⭐⭐⭐ | kfchou, sinzin91, remember-md | v0.2 |
| L5 | Claude Code marketplace file | ⭐⭐⭐⭐ | kfchou, sinzin91 | v0.2 |

## M · Privacy & security

| # | Feature | Value | Prior art | llmwiki phase |
|---|---|---|---|---|
| M1 | **Username redaction** (`/Users/you/` → `/Users/USER/`) | ⭐⭐⭐⭐⭐ | **None** | v0.1 |
| M2 | **API key / token / password regex redaction** | ⭐⭐⭐⭐⭐ | **None** | v0.1 |
| M3 | **Email redaction** | ⭐⭐⭐⭐⭐ | **None** | v0.1 |
| M4 | **Gitleaks secret scan in CI** | ⭐⭐⭐⭐⭐ | sinzin91 | v0.1 |
| M5 | **Localhost-only binding by default** | ⭐⭐⭐⭐⭐ | **None explicit** | v0.1 |
| M6 | **No telemetry (hard rule)** | ⭐⭐⭐⭐⭐ | lightweight ones imply | v0.1 |
| M7 | **Local LLM option (Ollama)** | ⭐⭐⭐ | kytmanov | v0.3 |
| M8 | **`.llmwikiignore`** — skip files from sync | ⭐⭐⭐⭐ | **None** | v0.1 |
| M9 | Encrypt raw/ at rest | ⭐⭐ | — | v0.3 |

## N · UX polish

| # | Feature | Value | Prior art | llmwiki phase |
|---|---|---|---|---|
| N1 | Inter + JetBrains Mono typography | ⭐⭐⭐⭐⭐ | — | v0.1 |
| N2 | Proper focus rings (a11y) | ⭐⭐⭐⭐ | — | v0.1 |
| N3 | Smooth scroll | ⭐⭐⭐⭐ | — | v0.1 |
| N4 | Anchor scroll-margin-top | ⭐⭐⭐⭐ | — | v0.1 |
| N5 | Motion-reduced option (`prefers-reduced-motion`) | ⭐⭐⭐ | — | v0.1 |
| N6 | Empty states (no sessions, no results) | ⭐⭐⭐⭐ | — | v0.1 |
| N7 | Loading states | ⭐⭐ | — | won't (static) |
| N8 | Toast notifications on copy success | ⭐⭐⭐⭐ | — | v0.1 |
| N9 | Page transitions | ⭐⭐ | — | v0.2 |

## O · Operational features

| # | Feature | Value | Prior art | llmwiki phase |
|---|---|---|---|---|
| O1 | Contradiction tracking in wiki pages | ⭐⭐⭐⭐⭐ | SamurAIGPT, our CLAUDE.md | v0.1 |
| O2 | Stale-page detection (lint) | ⭐⭐⭐⭐⭐ | Ss1024sS | v0.1 |
| O3 | Version upgrade flow | ⭐⭐⭐⭐ | Ss1024sS | v0.1 |
| O4 | Cross-project wiring (multi-wiki from one repo) | ⭐⭐⭐ | bashiraziz | v0.3 |
| O5 | Wiki changelog (auto-generated from `log.md`) | ⭐⭐⭐⭐ | — | v0.1 |
| O6 | Wiki backup / export | ⭐⭐⭐ | — | v0.2 |
| O7 | Dry-run mode everywhere | ⭐⭐⭐⭐⭐ | — | v0.1 |

## P · Novel inventions for llmwiki

These are features **no prior implementation has** that llmwiki will ship:

| # | Feature | Value | Rationale |
|---|---|---|---|
| P1 | **Session `.jsonl` → markdown adapter** | ⭐⭐⭐⭐⭐ | The entire reason llmwiki exists |
| P2 | **Cmd+K command palette** | ⭐⭐⭐⭐⭐ | Modern dev-tool UX standard |
| P3 | **Client-side search index + fuzzy matcher** | ⭐⭐⭐⭐⭐ | No dependencies, works offline, instant |
| P4 | **Pygments syntax highlighting at build** | ⭐⭐⭐⭐⭐ | Code blocks look professional |
| P5 | **Keyboard shortcuts** (`/`, `g h`, `j/k`) | ⭐⭐⭐⭐⭐ | Power-user UX |
| P6 | **Breadcrumbs + scroll-spy** | ⭐⭐⭐⭐ | Orient users in long sessions |
| P7 | **Collapsible tool-result sections** | ⭐⭐⭐⭐ | Session transcripts are verbose |
| P8 | **Sticky sessions-table header** | ⭐⭐⭐⭐ | 300-row tables need it |
| P9 | **Filter bar** on sessions table | ⭐⭐⭐⭐ | Project/date/model filters |
| P10 | **Live-session skip (`<60min`)** | ⭐⭐⭐⭐⭐ | Prevents reading mid-write files |
| P11 | **Adapter registry with schema version tracking** | ⭐⭐⭐⭐⭐ | Clean extensibility contract |
| P12 | **Redaction by default (username, keys, tokens, emails)** | ⭐⭐⭐⭐⭐ | No other impl does this |
| P13 | **Performance budget enforced in CI** | ⭐⭐⭐⭐ | 9s cold build, 0.4s no-op |
| P14 | **Hover-to-preview wikilinks** | ⭐⭐⭐⭐ | Obsidian-inspired navigation |
| P15 | **Self-demo via GitHub Pages on tag push** | ⭐⭐⭐⭐⭐ | Zero-effort marketing |

## Total feature count

| Category | Count | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐ | ⭐ |
|---|---|---|---|---|---|---|
| A Core workflows | 10 | 3 | 3 | 3 | 1 | 0 |
| B Input adapters | 11 | 3 | 1 | 4 | 2 | 1 |
| C Page types | 12 | 6 | 3 | 2 | 1 | 0 |
| D Viewer | 22 | 6 | 13 | 3 | 2 | 0 |
| E Distribution | 8 | 3 | 2 | 2 | 2 | 0 |
| F Multi-agent | 7 | 4 | 2 | 1 | 0 | 0 |
| G Infrastructure | 10 | 3 | 2 | 3 | 1 | 1 |
| H Search | 6 | 2 | 0 | 3 | 1 | 0 |
| I Testing | 8 | 5 | 2 | 1 | 0 | 0 |
| J CI/CD | 7 | 2 | 2 | 3 | 0 | 0 |
| K Docs | 15 | 4 | 9 | 2 | 0 | 0 |
| L Config | 5 | 2 | 3 | 0 | 0 | 0 |
| M Privacy | 9 | 6 | 1 | 1 | 1 | 0 |
| N UX polish | 9 | 1 | 5 | 1 | 2 | 0 |
| O Operational | 7 | 3 | 2 | 1 | 0 | 0 |
| P Novel | 15 | 10 | 5 | 0 | 0 | 0 |
| **TOTAL** | **161** | **63** | **55** | **30** | **13** | **2** |

**63 features rated ⭐⭐⭐⭐⭐** are what make this a "god-level" build. They're all ship-in-v0.1 targets.
