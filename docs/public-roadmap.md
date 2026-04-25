# llmwiki Public Roadmap

> Track what shipped, what's in progress, and what's next.
> Last updated: 2026-04-09.

## Shipped

| Version | Date | Highlights |
|---|---|---|
| **v0.1** | 2026-04-08 | Claude Code adapter, Karpathy-style wiki schema, god-level HTML site with dark mode, Cmd+K command palette, global search, keyboard shortcuts, copy-as-markdown, collapsible tool results, mobile-responsive, print-friendly |
| **v0.2** | 2026-04-08 | Knowledge graph (`/wiki-graph`), file watcher, Obsidian bidirectional output, MCP server (6 tools), Cursor + Gemini CLI + PDF adapters, hover-to-preview wikilinks, timeline view |
| **v0.3** | 2026-04-08 | Eval framework (7 structural checks, 100-point score), Codex CLI adapter graduated, `pyproject.toml` (PyPI-ready), i18n docs scaffold (zh-CN, ja, es) |
| **v0.4** | 2026-04-08 | AI+human dual format: `llms.txt`, JSON-LD graph, per-page `.txt`/`.json` siblings, `sitemap.xml`, `rss.xml`, Schema.org microdata, Open Graph tags, canonical URLs, build manifest, link checker, performance budgets |
| **v0.5** | 2026-04-08 | highlight.js CDN (replaced Pygments), public demo on GitHub Pages, README screenshots, raw-HTML escape fix, folder-level `_context.md` for LLM navigation |
| **v0.6** | 2026-04-08 | qmd collection exporter, PyPI release automation (OIDC), GitLab Pages deployment, lazy search index (per-project chunks), scheduled sync templates (launchd/systemd/Task Scheduler), WCAG 2.1 AA audit (0 violations), Playwright E2E tests (62 scenarios) |
| **v0.7** | 2026-04-08 | Structured model-profile schema, `/models/` section with sortable benchmarks, vs-comparison pages (auto-generated), project topic chips (GitHub-style), append-only changelog timeline with pricing sparkline |
| **v0.8** | 2026-04-08 | 365-day activity heatmap, tool-calling bar chart, token usage card with cache-hit-ratio badge, session metrics frontmatter |
| **v0.9** | 2026-04-09 | Maintainer governance scaffold (CODE_OF_CONDUCT, SECURITY, CODEOWNERS), review checklist, triage taxonomy, release process, image download pipeline, Cursor + Gemini CLI + PDF adapters graduated to production, Copilot adapter |

## In progress

- **Changelog timeline module** (`llmwiki/changelog_timeline.py`) -- append-only changelog field on model entities with timeline widget, pricing sparkline, and recently-updated card
- **Documentation expansion** -- SEO guide, benchmarks, accessibility report, competitor landscape

## Planned: v1.0

The v1.0 release is a stability pass. No new features -- just hardening.

| Goal | Description |
|---|---|
| API freeze | CLI flags, frontmatter schema, and slash-command contracts locked |
| Upgrade guide | Migration recipes for every breaking change between 0.x and 1.0 |
| LTS branch | v1.x gets security fixes for 12 months |
| Docs polish | Every feature documented, every tutorial up to date |
| PyPI stable | `pip install llm-notebook` with stable version |
| Homebrew formula | `brew install llmwiki` |

## Planned: post-v1.0

| Feature | Notes |
|---|---|
| Interactive knowledge graph explorer | vis.js with zoom, filter, and click-to-navigate |
| Light theme refinement | Warm palette option, user-selectable accent colors |
| ChatGPT conversation-export adapter | Import OpenAI chat history |
| OpenCode / OpenClaw adapter | Support for open-source agent frameworks |
| Local LLM via Ollama | Optional synthesis backend for offline users |
| Plugin marketplace | `.claude-plugin/marketplace.json` community entries |
| Hosted demo mode | One-click deploy without `git clone` |
| Docker image | `docker run llmwiki` |
| Web clipper / URL ingestion | Save web pages directly into the wiki |
| SQLite FTS5 search | Server-side full-text search fallback |

## Community requested

Features requested via GitHub issues. Upvote with a thumbs-up to
signal interest.

| Feature | Issue | Upvotes |
|---|---|---|
| Slack / Discord export ingestion | Declined (out of scope) | -- |
| TUI browser | Deferred to raine/claude-history | -- |
| Real-time collaborative editing | Declined (not a product goal) | -- |
| Sentry / telemetry integration | Declined (privacy rule) | -- |
| Supabase / Postgres backend | Declined (stdlib-first rule) | -- |
| Precompiled Go/Rust binary | Declined (Python-first policy) | -- |

> **Declined items** are documented with rationale in
> [`docs/maintainers/DECLINED.md`](maintainers/DECLINED.md). We keep
> the list visible so contributors don't duplicate investigation effort.

## How features get prioritized

1. **Must (M)** -- the product fails without it. Ships in the current release.
2. **Should (S)** -- strong user value. Ships in the next minor release.
3. **Could (C)** -- nice to have. Ships when a contributor or issue demands.
4. **Won't (W)** -- considered and rejected. Documented in DECLINED.md.

See [`roadmap.md`](roadmap.md) for the full internal roadmap with
layer-by-layer breakdown and MoSCoW priority assignments.
