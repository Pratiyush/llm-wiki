# Changelog

All notable changes to **llmwiki** will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

Versions below 1.0 are pre-production — API and file formats may change.

## [Unreleased]

### Added

- **Token usage card, project timeline, and site-wide stats** (#66) — new `llmwiki/viz_tokens.py` module (stdlib-only) consumes the `token_totals` frontmatter key (#63) and renders three related views. **Session card** shows Input / Cache creation / Cache read / Output in a stacked-bar layout with a cache-hit-ratio badge (green ≥80%, yellow 50–79%, red <50%) — formula matches Anthropic's definition (`cache_read / (cache_read + cache_creation + input)`, excludes output). **Project timeline** is a log-scale area chart of daily total tokens over the project lifetime + aggregate cache hit ratio in the header. **Site-wide stats** on `index.html` show four cards: total tokens, average per session, best-cache-hit project (linked), heaviest project (linked). Human-readable K/M/B number formatting via shared `format_tokens()` helper. Full dark-mode palette via `--token-input / --token-cache-creation / --token-cache-read / --token-output / --token-area-fill / --token-area-stroke` CSS custom properties. Sessions missing `token_totals` (older converter output) degrade gracefully — card renders nothing instead of crashing. 45 new tests.
- **Tool-calling bar chart** (#65) — new `llmwiki/viz_tools.py` module (stdlib-only, pure-SVG) renders a horizontal bar chart of tool usage from the `tool_counts` frontmatter key (#63). One chart per session page (sorted descending, top 10 tools + "Other (N tools)" overflow row) and one aggregate chart per project page. Category-based coloring: I/O (Read/Write/Edit — blue), Search (Grep/Glob/WebSearch — purple), Execution (Bash/Skill — orange), Network (WebFetch/mcp__* — green), Planning (Agent/TodoWrite/ExitPlanMode — slate). Tooltips show `{tool}: {count} calls ({pct}%)`. Long tool names (e.g. `mcp__Claude_in_Chrome__tabs_context_mcp`) are truncated to 28 chars in the label column but preserved in the tooltip. Dark-mode variants for every category via `--tool-cat-*` CSS custom properties. 38 new tests cover: JSON-string and dict frontmatter shapes, aggregation across sessions, category mapping for every standard + MCP tool, sort order, overflow collapse, tooltip grammar, XSS defense, bar-width scaling.
- **GitLab/GitHub-style 365-day activity heatmap** (#64, #72) — new `llmwiki/viz_heatmap.py` module (stdlib-only, pure-SVG) renders a full-year rolling contribution grid at build time. One aggregate heatmap on `site/index.html` counting every main session across all projects, one per-project heatmap on each `projects/<slug>.html` page scoped to that project. Sunday-aligned 53-column grid (369–371 cells depending on where the build date lands in the week), five-level quantile bucketing computed over *non-zero* days so sparse projects don't collapse into a single color, empty days always render as level-0 so the grid dimensions stay constant. Dark-mode variant via `--heatmap-0..4` CSS custom properties (light: ebedf0→216e39, dark: 161b22→39d353). A11y: `role="img"` + descriptive `aria-label`, per-cell `<title>` tooltips. Replaces the v0.4 JS-based tiny-strip heatmap. 22 new tests lock the window bounds, quantile math, SVG structure, and sparse-data edge cases.
- **Session metrics frontmatter** (#63) — converter now emits five new keys per session as JSON inline: `tool_counts`, `token_totals` (input / cache_creation / cache_read / output), `turn_count`, `hour_buckets` (UTC-normalised ISO-hour → activity count), and `duration_seconds`. Foundation for the v0.8 visualization stack (#64 heatmap / #65 tool chart / #66 token card). Stdlib-only; byte-identical on re-run. 24 new tests.
- **Changelog page** (#72) — `CHANGELOG.md` now renders as a first-class page at `site/changelog.html` with a nav-bar link, narrow reading column, keep-a-changelog typography, and the same theme/print styles as the rest of the wiki.
- **highlight.js syntax highlighting** (#73) — replaced server-side Pygments/codehilite with client-side [highlight.js](https://highlightjs.org/) v11.9.0 loaded from a pinned jsdelivr CDN. Both GitHub light (`github.min.css`) and GitHub dark (`github-dark.min.css`) themes are preloaded; the runtime swaps the `disabled` flag on `<link>` tags when the theme toggles so code blocks stay in sync with the rest of the page. Code fences now emit plain `<pre><code class="language-xxx">` via the `fenced_code` extension. Lighter build (no optional Python dep), consistent look across every page, auto-detection for untagged blocks. 15 new tests.
- **Public demo deployment** (#73) — `.github/workflows/pages.yml` now builds a demo site from the eight dummy sessions under [`examples/demo-sessions/`](examples/demo-sessions) on every push to `master` and deploys it to GitHub Pages. No personal data. Three fictional projects (`demo-blog-engine` Rust SSG, `demo-ml-pipeline` DistilBERT fine-tune, `demo-todo-api` FastAPI CRUD) with realistic code fences so visitors can see highlight.js and the full session UX immediately.
- **README screenshots** (#73) — added six embedded screenshots under [`docs/images/`](docs/images) (home, sessions index, session detail, changelog, projects index, code-heavy session) captured from the demo site with headless Chrome at 2x device pixel ratio.

### Changed

- **No optional highlight dependency** (#73) — `pip install -e '.[highlight]'` is now a no-op alias kept only for backwards-compatibility with v0.4 install docs. `setup.sh`, `setup.bat`, `pyproject.toml`, and CI workflows no longer install Pygments.

### Fixed

- **Raw HTML in session prose leaking into the DOM** (#74) — a session transcript that mentioned `<textarea>` (or any tag-shaped substring) in prose used to pass through the markdown library unescaped, leaving an unclosed element that swallowed every following tag — including the `<script>` that boots highlight.js. The v0.5 swap from server-side Pygments to client-side hljs (#73) made this pre-existing bug catastrophic: once the script was inside a stuck textarea, no code block on the page ever got highlighted. Fixed by a new `_EscapeRawHtmlPreprocessor` that runs in the Python `markdown` pipeline after `fenced_code` (priority 25) and before `html_block` (priority 20), escaping `<tagname>` / `</tagname>` patterns outside inline backtick spans. Inline/fenced code, HTML comments (`<!-- llmwiki:metadata -->`), bare `<` in math, blockquotes, tables, headings, and link syntax are all untouched. 9 new regression tests lock it down. Verified on a real 169-code-block session page: 0/172 → 172/172 highlighted after the fix.
- **Code-fence truncation eating pages** (#72) — `truncate_chars` / `truncate_lines` used to cut content mid-code-block, leaving the opening ` ``` ` without a closing fence. The markdown parser then swallowed everything that followed as one giant block (user-visible example: the "Full Directory Tree" section on subagent pages). Fixed by counting unbalanced fences in the kept portion and injecting a closing fence before the truncation marker. 5 new tests; 30 previously-mangled session files regenerated.
- **Sync crash on corrupt JSONL bytes** (#72) — a single stray non-UTF-8 byte in a session transcript used to abort the entire `llmwiki sync` run with `UnicodeDecodeError`. `parse_jsonl` now opens with `errors="replace"` and silently drops non-dict records (rare stray scalars from partial writes that previously crashed `filter_records` with `AttributeError`).

## [0.4.0] — 2026-04-08

**Theme:** AI + human dual-format. Every page ships both as HTML for humans AND as machine-readable `.txt` + `.json` siblings for AI agents, alongside site-level exports that follow open standards (`llms.txt`, JSON-LD, sitemap, RSS).

### Added

#### Part A — AI-consumable exports (`llmwiki/exporters.py`)

- **`llms.txt`** — short index per the [llmstxt.org spec](https://llmstxt.org) with project list, machine-readable links, and AI-agent entry points
- **`llms-full.txt`** — flattened plain-text dump of every wiki page, ordered project → date, capped at 5 MB for pasteable LLM context
- **`graph.jsonld`** — schema.org JSON-LD `@graph` representation with `CreativeWork` nodes for the wiki, projects, and individual sessions, all linked via `isPartOf` relations
- **`sitemap.xml`** — standard sitemap with `lastmod` timestamps and priority hints
- **`rss.xml`** — RSS 2.0 feed of the newest 50 sessions
- **`robots.txt`** — with explicit `llms.txt` + `sitemap.xml` references for AI-agent-aware crawlers
- **`ai-readme.md`** — AI-specific entry point explaining navigation structure, machine-readable siblings, and MCP tool surface
- **Per-page `.txt` siblings** next to every `sessions/<project>/<slug>.html` — plain text version stripped of all markdown/HTML for fast AI consumption
- **Per-page `.json` siblings** with structured frontmatter + body text + SHA-256 + outbound wikilinks — ideal for RAG or structured-data agents
- **Schema.org microdata** on every session page (`itemscope`/`itemtype="https://schema.org/Article"` + `headline` + `datePublished` + `inLanguage`)
- **`<link rel="canonical">`** on every session page for SEO and duplicate-indexing prevention
- **Open Graph tags** (`og:type`, `og:title`, `og:description`, `article:published_time`)
- **`<!-- llmwiki:metadata -->` HTML comment** at the top of every session page — AI agents scraping HTML can parse metadata without fetching the separate `.json` sibling
- **`wiki_export` MCP tool** (7th tool on the MCP server) — returns any AI-consumable export format by name (`llms-txt`, `llms-full-txt`, `jsonld`, `sitemap`, `rss`, `manifest`, or `list`). Capped at 200 KB per response.

#### Part B — Human polish

- **Reading time estimates** on every session page (`X min read` in the metadata strip)
- **Related pages panel** at the bottom of session pages (3-5 related sessions computed from shared project + entities, all client-side from `search-index.json`)
- **Activity heatmap** on the home page — SVG cells with per-day intensity gradient
- **Mark highlighting** support (`<mark>` styled with the accent color) for search results
- **Deep-link icons** on every `h2`/`h3`/`h4` in the content — hover to reveal, click to copy a canonical URL with `#anchor` to the clipboard
- **`.txt` and `.json` download buttons** in the session-actions strip next to Copy-as-markdown

#### Part C — Cross-cutting infra

- **Build manifest** (`llmwiki/manifest.py`) — generates `site/manifest.json` on every build with SHA-256 hashes of all files, total sizes, perf-budget check, and budget violations list
- **Link checker** (`llmwiki/link_checker.py`) — walks `site/` verifying every internal `<a href>`, `<link href>`, and `<script src>` resolves to an existing file. External URLs are skipped. Strict regex filters out code-block artifacts.
- **Performance budget** targets declared in `manifest.py` (cold build <30s, total site <150 MB, per-page <3 MB, CSS+JS <200 KB, `llms-full.txt` <10 MB)
- **New CLI subcommands**: `llmwiki check-links`, `llmwiki export <format>`, `llmwiki manifest` (all with `--fail-on-*` flags for CI integration)

### Tests

- **24 new tests** in `tests/test_v04.py` covering exporters, manifest, link checker, MCP `wiki_export`, schema.org microdata, canonical links, per-page siblings, and CLI subcommands
- **95 tests passing total** (was 71 in v0.3)

### Fixed

- Link checker rewritten to only match `<a>` / `<link>` / `<script>` tag hrefs (not URLs inside code blocks). The initial naive regex was catching runaway multi-line matches from rendered tool-result output.
- Canonical URLs and `.txt`/`.json` sibling links now use the actual HTML filename stem (`date-slug`) instead of the frontmatter `slug` field, which was causing broken link reports.

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
