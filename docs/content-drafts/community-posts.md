# Community Posts — Copy-Paste Ready Drafts

**Platforms:** Reddit (r/programming, r/MachineLearning), Claude Discord, OpenAI Forum, Python Discord, IndieHackers, Karpathy Gist, Dev.to, alternativeto.net, SourceForge/LibHunt
**Tone per section:** matched to platform norms
**Last updated:** 2026-04-09

---

## Reddit r/programming post

### Title

llm-wiki: a Python CLI that turns AI coding session transcripts into a searchable static wiki (MIT, stdlib-only, no JS frameworks)

### Body

Every AI coding assistant writes full session transcripts to disk. Claude Code saves `.jsonl` under `~/.claude/projects/`, Codex CLI writes to `~/.codex/sessions/`, Cursor, Copilot, and Gemini CLI each have their own stores. You already have hundreds of these and never look at them again.

**[llm-wiki](https://github.com/Pratiyush/llm-wiki)** converts them into a searchable, interlinked static knowledge base. It follows [Karpathy's three-layer LLM Wiki architecture](https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f):

```
raw/    Immutable markdown from .jsonl (auto-redacted PII)
wiki/   LLM-maintained entity/concept/source pages with [[wikilinks]]
site/   Static HTML — browse locally or deploy to GitHub/GitLab Pages
```

**What makes it interesting from an engineering perspective:**

- **One runtime dependency.** The entire build is stdlib Python + the `markdown` library. No npm, no database, no template engine. HTML is generated with f-strings in a single file.
- **Pure SVG visualizations.** The 365-day activity heatmap, tool-calling bar charts, token usage cards, and pricing sparklines are all generated at build time as inline SVG. No D3, no Chart.js, no client-side rendering. CSS custom properties handle light/dark mode across every chart.
- **Pluggable adapter pattern.** Adding a new AI agent is one ~50-line file: subclass `BaseAdapter`, implement `session_store_path()` and `convert()`, ship a fixture and a test. Currently supports Claude Code, Codex CLI, Copilot, Cursor, Gemini CLI, and PDF ingestion.
- **Dual-format output.** Every page ships as HTML (for humans), `.txt` (for LLMs), and `.json` (structured metadata). Site-level exports: `llms.txt`, `llms-full.txt`, JSON-LD graph, sitemap, RSS, and an MCP server with 7 tools.
- **472 tests** including a Playwright E2E suite with 62 Gherkin scenarios.

The live demo rebuilds from synthetic sessions on every push to master: https://pratiyush.github.io/llm-wiki/

```bash
git clone https://github.com/Pratiyush/llm-wiki.git
cd llm-wiki && ./setup.sh
./build.sh && ./serve.sh    # http://127.0.0.1:8765
```

Python 3.9+. MIT license. Works offline. No API keys. No accounts.

**GitHub:** https://github.com/Pratiyush/llm-wiki

---

## Reddit r/MachineLearning post

### Title

[P] llm-wiki: implementation of Karpathy's LLM Wiki spec — multi-agent session indexing, model directory with benchmarks, AI-consumable exports

### Body

A few months ago Karpathy posted [a gist describing an "LLM Wiki"](https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f) — a three-layer knowledge base where raw LLM session transcripts feed a wiki layer maintained by an LLM, which compiles into a browsable static site.

I built a full implementation: **[llm-wiki](https://github.com/Pratiyush/llm-wiki)**.

**What it does:**

It ingests session transcripts from Claude Code, Codex CLI, GitHub Copilot, Cursor, and Gemini CLI, converts them to redacted markdown, and builds a searchable static site with cross-referenced entity pages, activity heatmaps, tool-calling charts, and token usage breakdowns.

**What I think is relevant to this community:**

1. **Multi-agent support with unified indexing.** If you use Claude on some projects and Codex/Copilot/Gemini on others, all sessions show up in the same wiki with colored agent badges. The adapter pattern makes adding a new agent trivial (one ~50-line file).

2. **Structured model directory.** Entity pages with `entity_kind: ai-model` get a structured schema: provider, context window, pricing, benchmarks (GPQA Diamond, SWE-bench, MMLU, etc.), modalities. The build auto-generates vs-comparison pages between any two models with side-by-side tables and shared-benchmark charts. Each model has an append-only changelog with pricing sparklines so you can track changes over time.

3. **AI-consumable exports.** Every page ships as `.txt` and `.json` alongside the HTML. Site-level: `llms.txt` (per llmstxt.org spec), `llms-full.txt` (flattened dump for pasting into an LLM context window), JSON-LD graph, and an MCP server with 7 tools so Claude Desktop or Cursor can query your wiki directly.

4. **Session analytics.** Token usage cards with cache-hit ratios (matching Anthropic's formula), tool-calling frequency charts categorized by type (I/O, Search, Execution, Network, Planning), and a GitHub-style 365-day activity heatmap.

5. **Sub-agent awareness.** Sessions spawned by `Agent` or `TodoWrite` tool calls are linked as children of their parent session, preserving the multi-agent workflow structure.

**Live demo** (synthetic data, rebuilds on every push): https://pratiyush.github.io/llm-wiki/

Python 3.9+, MIT license, one runtime dep (`markdown`). The build is deterministic and runs offline.

**GitHub:** https://github.com/Pratiyush/llm-wiki

---

## Claude Discord / Anthropic Community post

### Title

llm-wiki — Turn your Claude Code session history into a searchable knowledge base

### Body

If you use Claude Code regularly, you have a growing pile of `.jsonl` session transcripts under `~/.claude/projects/` that you probably never revisit. Each one contains architecture decisions, debugging sessions, library evaluations, code snippets — useful knowledge that's locked in a format nobody browses.

I built **llm-wiki** to fix that. It converts your Claude Code sessions into a beautiful static wiki you can search, filter, and cross-reference.

**What it does for Claude Code users specifically:**

- Reads every `.jsonl` under `~/.claude/projects/` and converts to clean, redacted markdown
- Builds a static site with Cmd+K fuzzy search, syntax highlighting, dark mode
- Shows a 365-day activity heatmap of your AI-assisted coding
- Breaks down tool usage per session — see how your Read/Edit/Bash/Grep patterns shift over time
- Token usage cards with cache-hit ratios (using Anthropic's definition: `cache_read / (cache_read + cache_creation + input)`)
- Tracks sub-agent sessions spawned by the Agent tool as children of the parent session
- Auto-redacts usernames, API keys, tokens, and emails before anything hits disk

**Integration with Claude Desktop / Cursor:**

llm-wiki ships an MCP server with 7 tools (search, query, read, lint, sync, list sources, export). One line of config in your Claude Desktop or Cursor MCP settings and the AI can query your session history directly.

**It also supports slash commands inside Claude Code itself:**

- `/wiki-sync` — convert new sessions and ingest into the wiki
- `/wiki-query <question>` — answer questions from your accumulated sessions
- `/wiki-ingest <path>` — ingest a specific source
- `/wiki-build` — rebuild the static site

**Setup:**

```bash
git clone https://github.com/Pratiyush/llm-wiki.git
cd llm-wiki && ./setup.sh
./build.sh && ./serve.sh
```

Everything runs locally. No cloud. No API key needed for the build. Python 3.9+, MIT license.

**Live demo:** https://pratiyush.github.io/llm-wiki/
**GitHub:** https://github.com/Pratiyush/llm-wiki

Based on Karpathy's LLM Wiki spec: https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f

---

## OpenAI Developer Forum post

### Title

llm-wiki: unified wiki for Codex CLI + Copilot + multi-agent coding sessions

### Body

I built an open-source tool that converts AI coding session transcripts into a searchable, interlinked knowledge base. It supports **Codex CLI** and **GitHub Copilot** alongside Claude Code, Cursor, and Gemini CLI — all sessions from all agents show up in one unified wiki.

**Why this matters for Codex CLI / Copilot users:**

If you use Codex CLI, your sessions are stored under `~/.codex/sessions/`. If you use Copilot, your chat history sits in VS Code's storage. Either way, you accumulate valuable context — architecture decisions, debugging approaches, library evaluations — in formats that are hostile to search and review.

llm-wiki converts all of that into a static site with:

- **Cmd+K command palette** with fuzzy search across every session from every agent
- **Colored agent badges** so you can tell at a glance whether a session was Claude, Codex, Copilot, Cursor, or Gemini
- **Tool-calling bar charts** — see which tools each agent used and how frequently (Read, Write, Edit, Bash, Grep, etc.), color-coded by category (I/O, Search, Execution, Network, Planning)
- **Token usage breakdowns** with cache-hit ratios per session
- **Auto-generated vs-comparison pages** between AI models with side-by-side benchmark tables
- **Activity heatmap** — a GitHub-style 365-day grid showing when you coded with AI assistance

**Multi-agent workflow awareness:**

Sessions that spawn sub-agents (via tool calls like Agent or TodoWrite) are linked as parent-child relationships in the wiki, so your multi-step workflows stay connected.

**AI-consumable exports:**

Every page ships as HTML + `.txt` + `.json`. Site-level exports include `llms.txt` (per llmstxt.org), a JSON-LD graph, sitemap, RSS, and an MCP server with 7 tools for live querying.

**Architecture:**

Follows Karpathy's three-layer LLM Wiki pattern. Raw transcripts (immutable, auto-redacted) feed an LLM-maintained wiki layer that compiles into static HTML. The build is deterministic, stdlib-only Python (one dep: `markdown`), and works fully offline.

Adding a new agent adapter is one ~50-line Python file — subclass `BaseAdapter`, implement two methods, ship a fixture and a test. PRs welcome if there are agents I have not covered.

**Live demo:** https://pratiyush.github.io/llm-wiki/
**GitHub:** https://github.com/Pratiyush/llm-wiki

Python 3.9+. MIT license. No API keys. No accounts. Everything local.

---

## Python Discord #showcase post

### Title

llm-wiki — stdlib-only static site generator for AI coding sessions (pure-SVG viz, no JS frameworks, one dep)

### Body

Built a CLI tool that converts AI coding session transcripts into a searchable static wiki. Sharing here because the implementation is aggressively stdlib-only and might be interesting from a Python perspective.

**The constraint:** one runtime dependency (`markdown`). Everything else is stdlib.

**What that means in practice:**

- **HTML generation** — f-strings in a single `build.py` file. No Jinja2, no template engine. Every page is an f-string with the content interpolated.
- **SVG visualizations** — the 365-day activity heatmap, tool-calling bar charts, token usage stacked bars, pricing sparklines, and benchmark comparison charts are all generated at build time as inline SVG strings from stdlib Python. No D3, no matplotlib, no Pillow. CSS custom properties handle dark mode across every chart.
- **YAML frontmatter parsing** — custom parser (stdlib `re`) instead of pulling in PyYAML. Handles inline JSON blocks for structured data (model pricing, benchmarks) with a stitch-and-reparse fallback for edge cases.
- **HTTP server** — `http.server` from stdlib, localhost-only binding.
- **Search index** — pre-built JSON emitted at build time, consumed client-side by vanilla JS. Lazy-loaded in per-project chunks so initial transfer is <1 KB.
- **PII redaction** — regex-based scrubbing of usernames, API keys, tokens, and emails using stdlib `re`. Runs before anything hits disk.
- **PDF ingestion** — optional adapter using stdlib only (tries empty-password decrypt on encrypted PDFs, extracts metadata from document info dict).
- **Image pipeline** — `urllib.request` + `hashlib` for content-addressable local caching of remote images found in converted markdown.

**Adapter pattern:**

Supporting a new AI agent (Claude Code, Codex CLI, Copilot, Cursor, Gemini CLI are built in) is one file: subclass `BaseAdapter`, implement `session_store_path()` and `convert()`, add a fixture and a test. Platform-aware path resolution (macOS/Linux/Windows) per adapter.

**Test suite:**

472 unit tests + 62 Gherkin E2E scenarios (Playwright + pytest-bdd). The E2E suite builds a minimal demo site, serves it on a random port via `http.server`, and drives Chromium.

**TypedDict validation:**

Model entity pages use a stdlib-only `TypedDict` validator in `schema.py` — no Pydantic, no attrs, no dataclasses-json.

The client-side JS is also minimal: highlight.js from CDN for syntax highlighting, vanilla JS for the command palette and theme toggle. No React, no build step, no bundler.

**Live demo:** https://pratiyush.github.io/llm-wiki/
**GitHub:** https://github.com/Pratiyush/llm-wiki
**PyPI:** `pip install llmwiki`

Python 3.9+. MIT license.

---

## IndieHackers post

### Title

I turned 647 AI coding sessions into a searchable wiki — now open sourcing it

### Body

**The problem I had:**

I use AI coding assistants daily — Claude Code, sometimes Codex CLI or Copilot. Every session writes a full transcript to disk. After a year of this, I had 647 session files sitting in various folders on my machine. Full conversations about architecture decisions, debugging sessions, library evaluations, code reviews. I never opened a single one after the session ended.

That felt like a massive waste. Those transcripts contained accumulated knowledge — patterns, decisions, approaches — that I kept re-deriving from scratch.

**What I built:**

[llm-wiki](https://github.com/Pratiyush/llm-wiki) is a Python CLI that converts all those transcripts into a searchable, interlinked static wiki. Think of it as a personal knowledge base that builds itself from your AI coding history.

You get:
- A static site with fuzzy search across every session
- A 365-day activity heatmap showing when you leaned on AI
- Tool usage charts showing how your patterns shifted over time
- Token usage breakdowns so you can see what sessions cost
- Cross-referenced entity pages for projects, tools, and libraries
- An AI model directory with benchmark comparisons

It follows Andrej Karpathy's "LLM Wiki" specification — a three-layer architecture where raw transcripts feed a wiki that compiles into browsable HTML.

**The build process:**

```bash
git clone https://github.com/Pratiyush/llm-wiki.git
cd llm-wiki && ./setup.sh
./build.sh && ./serve.sh
```

Five minutes. Everything runs locally. No cloud account. No API key for the build. Auto-redacts PII before anything touches disk.

**What I learned from 647 sessions:**

- I ask the same architectural question in different ways across projects. The wiki surfaces these contradictions.
- My tool usage shifted dramatically over time. Early sessions were all Bash and Read. Later sessions leaned heavily on Edit and Grep. The charts make this visible.
- The sessions I thought were throwaway debugging contained the most reusable knowledge.

**The tech:**

Python 3.9+, one runtime dependency (`markdown`), no JS frameworks. All visualizations are pure SVG generated at build time. 472 tests. MIT license.

It supports Claude Code, Codex CLI, GitHub Copilot, Cursor, and Gemini CLI. Adding a new agent is one small file.

**Why open source:**

I built this for myself, but every developer using AI coding assistants has the same problem. The transcript format is different per tool, but the value proposition is identical: your accumulated context should not be write-once, read-never.

**Links:**
- GitHub: https://github.com/Pratiyush/llm-wiki
- Live demo: https://pratiyush.github.io/llm-wiki/
- Karpathy's original spec: https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f

I would love feedback on what features matter most to you. The roadmap is driven by what actual users want.

---

## Karpathy Gist Reply

Hi Andrej -- I built a full implementation of this spec: **[llm-wiki](https://github.com/Pratiyush/llm-wiki)**.

It implements the three-layer architecture (raw / wiki / site) with support for Claude Code, Codex CLI, GitHub Copilot, Cursor, and Gemini CLI session transcripts. The wiki layer uses `[[wikilinks]]`, entity/concept/source pages, and contradiction tracking as described in the gist.

Beyond the original spec, it adds:

- Pure-SVG activity heatmap, tool-calling charts, and token usage cards (all build-time, no JS charting libs)
- A structured model directory with auto-generated vs-comparison pages
- AI-consumable exports: `llms.txt`, JSON-LD, per-page `.txt`/`.json` siblings, and an MCP server
- A pluggable adapter pattern for adding new agents (~50 lines per adapter)
- `qmd` collection export for hybrid search at scale (as you recommended in the gist)
- 472 tests + 62 Gherkin E2E scenarios

Stdlib-only Python (one dep: `markdown`). MIT license.

Live demo: https://pratiyush.github.io/llm-wiki/
GitHub: https://github.com/Pratiyush/llm-wiki

Thanks for the spec -- it was a great foundation to build on.

---

## Dev.to cross-post

```yaml
---
title: "I Built a Wiki From My AI Coding Sessions"
published: true
tags: python, opensource, ai, productivity
series: llm-wiki
canonical_url: https://github.com/Pratiyush/llm-wiki
cover_image: https://pratiyush.github.io/llm-wiki/docs/images/home.png
---
```

Every developer using Claude Code, Copilot, Cursor, or Codex CLI has hundreds of session transcripts sitting on their hard drive right now. Full conversations with an AI about architecture decisions, debugging sessions, code reviews, library evaluations. Thousands of hours of context that you will never look at again.

I had 647 of them. I never opened a single one after the session ended.

That bothered me, so I built [llm-wiki](https://github.com/Pratiyush/llm-wiki).

## The problem: write-once, read-never

Every AI coding assistant writes a full transcript to disk. Claude Code saves `.jsonl` files under `~/.claude/projects/`. Codex CLI writes to `~/.codex/sessions/`. Cursor, Gemini CLI, and Copilot each have their own stores.

These transcripts are rich. They contain:

- Every architectural decision you discussed with the AI
- Every debugging session, including the dead ends
- Every library you evaluated and why you picked one over another
- Code snippets you will want again in six months

But the format is hostile. Raw JSONL. No search. No cross-referencing. No way to find "that time I debugged the WebSocket reconnection logic" without `grep`-ing through megabytes of JSON.

So you don't. The transcripts gather dust. Your accumulated knowledge evaporates.

## The solution: a local, searchable knowledge base

**llm-wiki** turns your dormant session history into a searchable, interlinked knowledge base. Locally. In two commands. No cloud services. No API keys. No accounts.

```bash
git clone https://github.com/Pratiyush/llm-wiki.git
cd llm-wiki && ./setup.sh
./build.sh && ./serve.sh    # browse at http://127.0.0.1:8765
```

The tool follows [Andrej Karpathy's LLM Wiki pattern](https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f) -- a three-layer architecture where raw transcripts feed an LLM-maintained wiki that compiles into a static site.

## What you actually get

Check out the [live demo](https://pratiyush.github.io/llm-wiki/) -- it rebuilds from synthetic sessions on every push, so it always shows the latest features.

### A home page with a 365-day activity heatmap

Like GitHub's contribution graph, but for your AI coding sessions. At a glance, see when you leaned heavily on AI assistance and when you went solo.

### Every session, searchable and filterable

A sortable table across all your projects. Filter by project, model, date range, or free text. Hit Cmd+K for a command palette with fuzzy search across everything.

### Session detail pages with syntax highlighting

Every conversation rendered as clean, readable HTML with highlight.js-powered code blocks, collapsible tool results, breadcrumbs, and a reading progress bar.

### An AI model directory

Structured model profiles with context windows, pricing, benchmarks, and auto-generated side-by-side comparison pages. If you use multiple models, you can track how they compare over time with an append-only changelog and pricing sparklines.

### Multi-agent support

Use Claude Code on Monday, Copilot on Tuesday, and Cursor on Wednesday? All three show up in the same wiki with colored agent badges so you can tell who wrote what.

### AI-consumable exports

Every page ships as both HTML (for you) and machine-readable formats (`.txt`, `.json`, JSON-LD, `llms.txt`) so other AI agents can query your wiki directly. There is even an MCP server with 7 tools so Claude Desktop or Cursor can search your knowledge base live.

## The architecture

Three layers, per Karpathy's spec:

1. **Raw** (`raw/`) -- Immutable markdown converted from `.jsonl`. Redacted by default (usernames, API keys, tokens, emails). Never modified after conversion.
2. **Wiki** (`wiki/`) -- LLM-maintained pages. Sources, entities, concepts, syntheses, comparisons, all interlinked with `[[wikilinks]]`. Your coding agent builds this layer via slash commands like `/wiki-ingest`.
3. **Site** (`site/`) -- Static HTML you can browse locally or deploy to GitHub Pages / GitLab Pages / anywhere.

The build is deterministic and stdlib-only. The only runtime dependency is Python's `markdown` library. Syntax highlighting runs client-side via highlight.js from a CDN. No npm. No bundler. No database.

## Works with 6+ agents

| Agent | Status |
|---|---|
| Claude Code | Production since v0.1 |
| Codex CLI | Production since v0.3 |
| Copilot Chat + CLI | Production since v0.9 |
| Cursor | Production since v0.5 |
| Gemini CLI | Production since v0.5 |
| Obsidian | Bidirectional since v0.2 |
| PDF files | Production since v0.5 |

Adding a new agent is one small file -- subclass `BaseAdapter`, ship a fixture and a test.

## Privacy by default

Everything runs locally. Localhost-only binding. No telemetry. No cloud calls. Usernames, API keys, tokens, and emails are redacted before anything hits disk. A `.llmwikiignore` file (gitignore syntax) lets you skip entire projects or date ranges.

Your session history never leaves your machine unless you choose to deploy the site somewhere.

## Try it

The [live demo](https://pratiyush.github.io/llm-wiki/) shows every feature running against safe synthetic data. Your real wiki will look identical -- just with your actual work.

```bash
git clone https://github.com/Pratiyush/llm-wiki.git
cd llm-wiki && ./setup.sh
./build.sh && ./serve.sh
```

Five minutes. No account needed. Works offline.

If you find it useful, [star the repo](https://github.com/Pratiyush/llm-wiki) and consider contributing -- the adapter pattern makes it straightforward to add support for new agents.

**Links:**
- GitHub: [github.com/Pratiyush/llm-wiki](https://github.com/Pratiyush/llm-wiki)
- Live demo: [pratiyush.github.io/llm-wiki](https://pratiyush.github.io/llm-wiki/)
- Karpathy's original spec: [gist.github.com/karpathy/442a6bf555914893e9891c11519de94f](https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f)

---

## alternativeto.net submission text

### Name

llm-wiki

### Short description

Open-source Python CLI that converts AI coding session transcripts (from Claude Code, Codex CLI, GitHub Copilot, Cursor, Gemini CLI) into a searchable, interlinked static wiki with activity heatmaps, tool-calling charts, token usage stats, an AI model directory, and machine-readable exports.

### Long description

llm-wiki turns your dormant AI coding session history into a beautiful, searchable knowledge base. It reads session transcripts from 6+ AI coding assistants, converts them to redacted markdown, and builds a static site with fuzzy search, syntax highlighting, dark mode, and cross-referenced entity pages.

Features include a GitHub-style 365-day activity heatmap, per-session tool-calling bar charts, token usage breakdowns with cache-hit ratios, a structured AI model directory with auto-generated comparison pages, and AI-consumable exports (llms.txt, JSON-LD, MCP server).

Everything runs locally. No cloud. No API keys. No telemetry. Privacy-first with automatic PII redaction. Built on Andrej Karpathy's LLM Wiki specification.

### Tags

AI, Developer Tools, Knowledge Management, Static Site Generator, Python, Open Source, CLI, Session Transcripts, Privacy

### License

MIT

### Platforms

macOS, Linux, Windows

### Alternative to

Obsidian, Logseq, Notion, Rewind.ai

---

## SourceForge / LibHunt description

### One-liner

Python CLI that converts AI coding session transcripts into a searchable static wiki.

### Short description (150 words)

llm-wiki converts session transcripts from Claude Code, Codex CLI, GitHub Copilot, Cursor, and Gemini CLI into a searchable, interlinked static knowledge base. It follows Andrej Karpathy's three-layer LLM Wiki architecture: raw transcripts are converted to redacted markdown, an LLM-maintained wiki layer cross-references entities and concepts with wikilinks, and a static HTML site provides fuzzy search (Cmd+K), syntax highlighting, dark mode, and keyboard shortcuts.

Visualizations include a 365-day activity heatmap, tool-calling bar charts, token usage cards with cache-hit ratios, and pricing sparklines -- all pure SVG generated at build time with no JavaScript charting libraries. Every page ships as HTML, plain text, and structured JSON for AI agent consumption. Includes an MCP server with 7 tools for live querying from Claude Desktop or Cursor.

Python 3.9+. One runtime dependency (markdown). MIT license. Runs fully offline. Auto-redacts PII.

### Category

Developer Tools / Knowledge Management

### Tags

python, ai, developer-tools, static-site-generator, knowledge-base, cli, open-source, claude-code, copilot, session-management
