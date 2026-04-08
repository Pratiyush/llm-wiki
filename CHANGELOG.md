# Changelog

All notable changes to **llmwiki** will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

Versions below 1.0 are pre-production — API and file formats may change.

## [Unreleased]

## [0.3.0] — 2026-04-08

### Added

- **`pyproject.toml`** — full PEP 621 metadata, PyPI-ready. Optional dep groups: `highlight` (pygments), `pdf` (pypdf), `dev` (pytest+ruff), `all`. Declared entry point `llmwiki = llmwiki.cli:main`.
- **Eval framework** (`llmwiki/eval.py`) — 7 structural quality checks (orphans, broken links, frontmatter coverage, type coverage, cross-linking, size bounds, contradiction tracking) totalling 100 points. New CLI: `llmwiki eval [--check ...] [--json] [--fail-below N]`. Zero LLM calls, pure structural analysis, runs in under a second on a 300-page wiki.
- **Codex CLI adapter** graduated from v0.2 stub → production with `SUPPORTED_SCHEMA_VERSIONS = ["v0.x", "v1.0"]`, two session store roots, config override, and hashed-path slug derivation.
- **i18n docs scaffold** — translations of `getting-started.md` in Chinese (`zh-CN`), Japanese (`ja`), and Spanish (`es`) under `docs/i18n/`. Each linked back to the English master with a sync date.
- **15 new tests** covering the eval framework, pyproject, i18n scaffold, and version bump.

### Deferred to v0.5+

- OpenCode / OpenClaw adapter
- Homebrew formula
- Local LLM via Ollama (optional synthesis backend)

(per explicit user direction — none of these block a v0.3.0 release)

## [0.2.0] — 2026-04-08

### Added

- **Three new slash commands**: `/wiki-update` (surgical in-place page update), `/wiki-graph` (knowledge graph generator), `/wiki-reflect` (higher-order self-reflection)
- **`llmwiki/graph.py`** — walks every `[[wikilink]]` and produces `graph/graph.json` (canonical) + `graph/graph.html` (vis.js). Reports top-linked, top-linking, orphans, broken edges. CLI: `llmwiki graph [--format json|html|both]`.
- **`llmwiki/watch.py`** — file watcher with polling + debounce. Detects mtime changes in agent session stores and auto-runs `llmwiki sync` after the debounce window. CLI: `llmwiki watch [--adapter ...] [--interval N] [--debounce M]`. Stdlib only, no `watchdog` dep.
- **`llmwiki/obsidian_output.py`** — bidirectional Obsidian output mode. Copies the compiled wiki into a subfolder of an Obsidian vault with backlinks and a README. CLI: `llmwiki export-obsidian --vault PATH [--subfolder NAME] [--clean] [--dry-run]`.
- **Full MCP server** (`llmwiki/mcp/server.py`) — graduated from v0.1 2-tool stub to **6 production tools**: `wiki_query` (keyword search + page content), `wiki_search` (raw grep), `wiki_list_sources`, `wiki_read_page` (path-traversal guarded), `wiki_lint` (structural report), `wiki_sync` (trigger converter).
- **Cursor adapter** (`llmwiki/adapters/cursor.py`) — detects Cursor IDE install on macOS/Linux/Windows, discovers workspace storage.
- **Gemini CLI adapter** (`llmwiki/adapters/gemini_cli.py`) — detects `~/.gemini/` sessions.
- **PDF adapter** (`llmwiki/adapters/pdf.py`) — optional `pypdf` dep, user-configurable roots, disabled by default.
- **Hover-to-preview wikilinks** in the HTML viewer — floating preview cards fetched from the client-side search index.
- **Timeline view** on the sessions index — compact SVG sparkline showing session frequency per day.
- **CLAUDE.md** extended with `/wiki-update`, `/wiki-graph`, `/wiki-reflect` slash command docs and new page types (`comparisons/`, `questions/`, `archive/`).
- **21 new tests** covering adapters, graph builder, Obsidian output, MCP server, file watcher, and CLI subcommands.

## [0.1.0] — 2026-04-08

Initial public release.

### Added

- Python CLI (`python3 -m llmwiki`) with `sync`, `build`, `serve`, `init` subcommands
- Claude Code adapter (`llmwiki.adapters.claude_code`) — converts `~/.claude/projects/*/*.jsonl` to markdown
- Codex CLI adapter stub (`llmwiki.adapters.codex_cli`) — scaffold for v0.2
- Karpathy-style wiki schema in `CLAUDE.md` and `AGENTS.md`
- God-level HTML generator (`llmwiki.build`)
  - Inter + JetBrains Mono typography
  - Light/dark theme toggle with `data-theme` attribute + system preference
  - Global search via pre-built JSON index
  - Cmd+K command palette
  - Keyboard shortcuts (`/` search, `g h` home, `j/k` next/prev session)
  - Syntax highlighting via Pygments (optional dep)
  - Collapsible tool-result sections (click to expand, auto-collapse > 500 chars)
  - Breadcrumbs on session pages
  - Reading progress bar on long pages
  - Sticky table headers on the sessions index
  - Copy-as-markdown and copy-code buttons (with `document.execCommand` fallback for HTTP)
  - Mobile-responsive breakpoints
  - Print-friendly CSS
- One-click scripts for macOS/Linux (`setup.sh`, `build.sh`, `sync.sh`, `serve.sh`)
- One-click scripts for Windows (`setup.bat`, `build.bat`, `sync.bat`, `serve.bat`)
- `.claude/commands/` slash commands: `wiki-sync`, `wiki-build`, `wiki-serve`, `wiki-query`, `wiki-lint`
- `.claude/skills/llmwiki-sync/SKILL.md` — global skill for auto-discovery
- GitHub Actions CI workflow (`.github/workflows/ci.yml`) — lint + build smoke test
- Documentation: getting-started, architecture, configuration, claude-code, codex-cli
- Redaction config with username, API key, token, and email patterns
- Idempotent incremental sync via `.ingestion-state.json` mtime tracking
- Live-session detection — skips sessions with activity in the last 60 minutes
- Sub-agent session support — rendered as separate pages linked from parent
