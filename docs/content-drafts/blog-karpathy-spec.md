# The Karpathy LLM Wiki Spec -- Implemented and Shipped

**Target:** Dev blog, Hashnode, dev.to, Hacker News
**Length:** ~800 words
**Tone:** Technical but accessible

---

In late 2025, Andrej Karpathy posted [a gist](https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f) describing something he called the "LLM Wiki" -- a structured knowledge base that every LLM-powered coding agent should maintain for its user. The idea was deceptively simple: your AI assistant has hundreds of conversations with you about architecture, debugging, library choices, and design decisions. All of that context evaporates the moment the session ends. What if it didn't?

We took that gist, implemented every concept in it, and shipped it as [llm-wiki](https://github.com/Pratiyush/llm-wiki) -- an open-source tool that turns your AI coding session transcripts into a searchable, interlinked knowledge base. Here is what the spec says, what we built, and where we went further.

## The spec: three layers, one owner each

Karpathy's design has a clean separation of concerns across three layers:

**Raw** -- immutable source documents. Session transcripts go here and are never modified after conversion. If the data is wrong, you fix the converter, not the output.

**Wiki** -- LLM-maintained pages. The coding agent reads the raw layer and produces structured wiki pages: source summaries, entity pages (people, projects, tools), concept pages (patterns, decisions, frameworks), and an interlinked index. Everything connects via wikilinks. Contradictions between sources are flagged, never silently overwritten.

**Site** -- generated output. The build step reads both layers and produces something browsable. Safe to delete and regenerate any time.

Each layer has exactly one owner. The converter owns raw. The LLM owns wiki. The build script owns site. No layer reaches back to modify an earlier one. This constraint is what makes the whole system tractable -- you can reason about each layer independently.

## Our implementation: the full pipeline

llm-wiki implements all three layers as a Python CLI tool. `llmwiki sync` reads `.jsonl` session transcripts from your agent's local store, runs privacy redaction (usernames, API keys, tokens, emails), and writes structured markdown to `raw/`. Your coding agent then ingests those files via slash commands (`/wiki-ingest`, `/wiki-query`, `/wiki-lint`) and maintains the wiki layer. `llmwiki build` compiles everything into a static HTML site -- dark mode, command palette, global search, keyboard shortcuts, syntax highlighting, mobile responsive -- that you can browse locally or deploy to GitHub Pages.

The architecture doc in our repo labels this the "Karpathy three-layer wiki" on one axis, and an "eight-layer build" on the other, distributing responsibilities across adapters, converters, schemas, templates, visualizations, exporters, and CI.

## What we added beyond the spec

The gist describes the conceptual framework. It does not prescribe an adapter pattern, visualization layer, or machine-readable export format. We filled those gaps:

**Eight agent adapters.** Claude Code, Codex CLI, Cursor, Gemini CLI, Copilot Chat, Copilot CLI, Obsidian, and PDF. Each adapter is a thin translation layer (50-100 lines) that knows where an agent stores its sessions and how to discover files there. Adding a new agent is one file, one fixture, one snapshot test. The adapter registry auto-discovers what is installed on your machine and syncs only what it finds.

**Pure-SVG visualizations.** A 365-day activity heatmap (GitHub contribution graph style), tool-calling bar charts with category coloring, token usage cards with cache-hit-ratio badges, pricing sparklines on model changelogs, and project timelines. All rendered at build time as inline SVG by stdlib-only Python functions. No JavaScript charting library. No runtime dependency.

**AI-consumable exports.** Every page ships as HTML for humans and as machine-readable `.txt` + `.json` siblings for AI agents. Site-level exports include `llms.txt` (per the llmstxt.org spec), a JSON-LD knowledge graph with Schema.org types, `sitemap.xml`, `rss.xml`, Open Graph tags, and an MCP server exposing six tools so other agents can query the wiki programmatically.

**Structured model schema.** An opt-in `entity_kind: ai-model` schema lets you declare provider, pricing, benchmarks, context window, and modalities in entity page frontmatter. The build produces a sortable `/models/` directory and auto-generates side-by-side comparison pages for every qualifying model pair.

**Auto-generated comparisons.** The compare module scores every 2-combination of model entities by shared structured fields and emits `/vs/<a>-vs-<b>.html` pages with difference-highlighted tables, benchmark bar charts, and price-delta analysis. User overrides replace the auto-gen for any URL.

## Line-by-line audit

We went through every concept in Karpathy's gist -- 28 distinct ideas spanning the three-layer architecture, page types (source, entity, concept, synthesis, comparison, question), operations (ingest, query, lint, reflect, graph), naming conventions, frontmatter schema, cross-linking rules, contradiction handling, and the append-only log. All 28 are implemented. Three edge cases where our interpretation diverged from the gist's implicit intent have been filed as issues for tracking.

## What's next

The v1.0 release is a stability pass: API freeze, upgrade guide, LTS branch, PyPI stable, Homebrew formula. After that, the roadmap includes an interactive knowledge graph explorer (vis.js with zoom, filter, and click-to-navigate), a refined light theme with user-selectable accent colors, and adapters for ChatGPT conversation exports and open-source agent frameworks.

## Try it

The live demo rebuilds from synthetic sessions on every push: [pratiyush.github.io/llm-wiki](https://pratiyush.github.io/llm-wiki)

The source is on GitHub: [github.com/Pratiyush/llm-wiki](https://github.com/Pratiyush/llm-wiki)

Two commands to run it on your own sessions:

```bash
git clone https://github.com/Pratiyush/llm-wiki.git
cd llm-wiki && ./setup.sh && ./build.sh && ./serve.sh
```

Karpathy described what every AI coding agent should remember. We built the tool that makes it happen.
