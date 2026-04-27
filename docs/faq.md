# FAQ

## Is my data sent anywhere?

No. Everything runs locally. There is no telemetry, no analytics, no phoning home. The only network request the built site makes is loading highlight.js from a CDN for syntax highlighting, and that degrades gracefully if blocked.

The `--synthesize` flag on `llmwiki build` calls the local `claude` binary on your machine for overview generation. It is opt-in and does not use any external API directly.

## Which agents are supported?

| Agent | Registry name | Status |
|---|---|---|
| Claude Code | `claude_code` | Production |
| Codex CLI | `codex_cli` | Production |
| GitHub Copilot Chat | `copilot_chat` | Production |
| GitHub Copilot CLI | `copilot_cli` | Production |
| Cursor | `cursor` | Scaffold (SQLite parser in progress) |
| Gemini CLI | `gemini_cli` | Scaffold (schema TBC) |
| Obsidian | `obsidian` | Production (vault as input source) |

> The PDF adapter that used to live here was removed in the simplification sweep.

See [multi-agent-setup.md](multi-agent-setup.md) for per-agent details.

## Do I need an API key?

No. llmwiki reads existing session files from your agents' local session stores. It does not call any LLM API. The wiki layer (`/wiki-ingest`, `/wiki-query`) uses your existing Claude Code (or other agent) session to do the LLM work.

## Can I use it offline?

Yes. The entire build pipeline runs offline. The only external resource is highlight.js loaded from a CDN in the generated HTML for syntax highlighting. If the CDN is unreachable (firewall, offline), code blocks render as plain text -- everything else works normally.

## How do I add a new adapter?

See [adapter-authoring.md](adapter-authoring.md). The short version: extend `BaseAdapter`, set `session_store_path`, implement `is_available()`, add the `@register` decorator, and import it in `discover_adapters()`.

## Where is my data stored?

```
raw/       Converted session transcripts (markdown)
wiki/      LLM-maintained wiki pages
site/      Generated static HTML
```

All three directories are gitignored by default. They never enter version control unless you explicitly un-ignore them.

The converter state file (`.llmwiki-state.json`) tracks which sessions have been processed and is also gitignored.

## Can I deploy to GitLab Pages?

Yes. See [deploy/gitlab-pages.md](deploy/gitlab-pages.md). Copy `.gitlab-ci.yml.example` to `.gitlab-ci.yml`, push, and the pipeline builds and deploys automatically.

For GitHub Pages, see [deploy/github-pages.md](deploy/github-pages.md).

## What's the wiki layer for?

The wiki layer implements layer 2 of [Karpathy's LLM Wiki spec](https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f). While `raw/` holds immutable session transcripts and `site/` holds generated HTML, `wiki/` is maintained by your coding agent:

- `wiki/sources/` -- one summary page per raw session
- `wiki/entities/` -- people, projects, tools, libraries
- `wiki/concepts/` -- ideas, patterns, decisions
- `wiki/syntheses/` -- saved query answers

Pages interlink via `[[wikilinks]]` and compound over time. The wiki layer is optional; the site builds from `raw/` alone.

## How do I search?

The built site includes a client-side search powered by a pre-built `search-index.json`. Access it via:

- **Cmd+K** (macOS) or **Ctrl+K** -- opens the command palette with fuzzy search
- **/** -- focuses the search bar on the current page
- The search bar in the top navigation

Search covers session titles, project names, and content snippets.

## Can multiple agents write to the same wiki?

Yes. Each agent produces sessions with its own adapter name and project slug, so there are no collisions in `raw/sessions/`. The wiki layer (`wiki/`) is agent-agnostic -- entities and concepts from different agents merge naturally.

For example, a Claude Code session about "React hooks" and a Copilot Chat session about "React hooks" both contribute to the same `wiki/entities/React.md` page.

## How do I update a single wiki page without re-ingesting everything?

Use the `/wiki-update` command inside your coding agent session. It performs a surgical edit of one page without running the full ingest workflow.

## What Python version do I need?

Python 3.9 or later. The only runtime dependency is the `markdown` package. Everything else uses the standard library.

## Can I export to other formats?

Yes. llmwiki supports several export formats:

- `llmwiki export llms-txt` -- llms.txt format for AI consumption
- `llmwiki export jsonld` -- JSON-LD knowledge graph
- `llmwiki export sitemap` -- XML sitemap
- `llmwiki export rss` -- RSS feed
- `llmwiki sync --vault PATH` -- write through to an Obsidian vault as part of the regular sync (replaces the removed `export-obsidian` subcommand)

Run `llmwiki export all` to generate everything at once.

> The `export-obsidian`, `export-qmd`, `export-marp`, and `watch` subcommands were removed in v1.2.0. See `docs/UPGRADING.md` for the migration path.
