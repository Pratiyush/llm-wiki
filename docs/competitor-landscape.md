# Competitor Landscape

How llmwiki compares to other tools in the AI session history and
personal knowledge management space.

## The problem

Every AI coding agent (Claude Code, Codex CLI, Cursor, Copilot, Gemini
CLI) writes a full session transcript to disk. After a few months you
have hundreds of sessions containing decisions, code patterns, and
debugging insights -- and you never look at any of them again.

Several tools address this problem. They differ in approach, scope, and
philosophy.

## Comparison table

| Feature | llmwiki | mem0 | Rewind | Pieces | Manual notes |
|---|---|---|---|---|---|
| **Approach** | Compile sessions into a wiki + static site | Memory layer API for LLM apps | System-wide screen recording + OCR | Snippet manager with AI context | Write it yourself |
| **Input sources** | Claude Code, Codex CLI, Cursor, Copilot, Gemini CLI, PDF, Obsidian | Any LLM API call (programmatic) | Everything on screen | Code snippets, links, screenshots | Whatever you type |
| **Output format** | Markdown wiki + HTML site + AI exports | API responses (JSON) | Searchable timeline (proprietary) | Snippet database (proprietary) | Your notes app |
| **Runs locally** | Yes, always | Self-hosted option available | macOS app (local + cloud) | Desktop app (local + cloud) | Depends on your tool |
| **Cloud required** | No | Optional (managed API available) | Yes (for sync + search) | Yes (for AI features) | No |
| **Open source** | MIT | Apache 2.0 | No | No | N/A |
| **API keys required** | No | Yes (for managed) | No (subscription) | No (freemium) | No |
| **Runtime dependencies** | Python 3.9+ stdlib only | Python + vector DB | macOS native | Electron | N/A |
| **Multi-agent support** | 6 agents | Agent-agnostic (API-level) | Agent-agnostic (screen-level) | Agent-agnostic (manual) | N/A |
| **Searchable** | Yes (client-side fuzzy search) | Yes (semantic search) | Yes (OCR + NLP) | Yes (AI-powered) | Depends on your tool |
| **Knowledge graph** | Yes (wikilinks + vis.js) | No | No | Contextual links | No |
| **Static site output** | Yes (deploy to GitHub/GitLab Pages) | No | No | No | No |
| **AI-consumable exports** | llms.txt, JSON-LD, MCP server | Native (it is an API) | No | API available | No |
| **Price** | Free | Free tier + paid | $24.95/month | Free tier + $10/month | Free |

## Detailed comparisons

### llmwiki vs mem0

[mem0](https://github.com/mem0ai/mem0) is a "memory layer for AI
applications" -- it stores and retrieves memories from LLM conversations
via an API. It is designed to be embedded into AI applications, not used
by end users directly.

**When to use mem0:** You are building an AI application and want it to
remember things across conversations. mem0 is a library, not a tool.

**When to use llmwiki:** You are a developer who uses AI coding agents
and wants to browse, search, and learn from your past sessions. llmwiki
is a tool, not a library.

**Key differences:**
- mem0 requires a vector database (Qdrant, Pinecone, etc.) and API keys.
  llmwiki uses Python stdlib only.
- mem0 stores memories as embeddings. llmwiki stores sessions as
  readable markdown with YAML frontmatter.
- mem0 has no UI. llmwiki generates a complete static HTML site.
- mem0 is for machines. llmwiki is for humans (with AI-consumable
  exports as a secondary output).

### llmwiki vs Rewind (now Limitless)

Rewind (later rebranded to [Limitless](https://www.limitless.ai/))
records everything on your screen, indexes it with OCR, and lets
you search your visual history.

**When to use Rewind:** You want to search across all your screen
activity, not just AI coding sessions. You're on macOS and comfortable
with a cloud-connected subscription app.

**When to use llmwiki:** You want structured, deep extraction from AI
coding sessions specifically. You want a local-only, open-source tool
that produces a deployable site.

**Key differences:**
- Rewind captures everything (meetings, browsing, typing). llmwiki
  focuses on AI coding agent sessions.
- Rewind is macOS-only and proprietary. llmwiki is cross-platform,
  open-source, and MIT-licensed.
- Rewind stores data in a proprietary format. llmwiki produces standard
  markdown and HTML.
- Rewind costs $24.95/month. llmwiki is free.

### llmwiki vs Pieces

[Pieces](https://pieces.app/) is a snippet manager that captures code
context from your IDE and provides AI-powered search and suggestions.

**When to use Pieces:** You want a general-purpose snippet manager that
integrates with your IDE and captures code as you write it.

**When to use llmwiki:** You want to compile complete AI session
transcripts into a navigable knowledge base, not just snippets.

**Key differences:**
- Pieces captures snippets. llmwiki captures entire sessions with full
  conversation context.
- Pieces is an Electron app with cloud features. llmwiki is a CLI tool
  that produces static files.
- Pieces has IDE plugins (VS Code, JetBrains). llmwiki integrates at
  the session-transcript level.
- Pieces has a freemium model. llmwiki is free and open source.

### llmwiki vs manual notes

Writing your own notes in Obsidian, Notion, or plain text files.

**When to use manual notes:** You have few sessions, enjoy the process
of note-taking, or need to capture information beyond what's in your
AI session transcripts.

**When to use llmwiki:** You have dozens or hundreds of sessions and
want automated extraction, cross-referencing, and a browsable site
without manual effort.

**Key differences:**
- Manual notes require discipline and time. llmwiki is automated.
- Manual notes capture what you think is important. llmwiki captures
  everything (and lets you search later).
- Manual notes are as organized as you make them. llmwiki enforces a
  consistent schema (Karpathy's LLM Wiki pattern).
- Manual notes don't produce a static site, activity heatmaps, or
  AI-consumable exports.

## llmwiki's positioning

llmwiki occupies a specific niche:

1. **Local-first.** No cloud, no API keys, no accounts. Your data stays
   on your machine (or your own GitHub Pages).

2. **Multi-agent.** Six adapters (Claude Code, Codex CLI, Cursor,
   Copilot, Gemini CLI, PDF) with a clean adapter interface for adding
   more.

3. **Karpathy-standard.** Based on [Andrej Karpathy's LLM Wiki
   pattern](https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f)
   -- sources, entities, concepts, syntheses, comparisons, questions,
   all interlinked with wikilinks.

4. **Stdlib-only.** No numpy, no torch, no node, no database. Python
   3.9+ with zero required dependencies beyond the standard library.

5. **Dual-format.** Every page ships as HTML for humans AND as
   machine-readable `.txt` + `.json` + `llms.txt` + JSON-LD for AI
   agents.

6. **Static output.** The result is a static site you can browse locally
   or deploy anywhere. No server to maintain, no database to back up.

## When llmwiki is NOT the right tool

- You need real-time memory for an AI application you're building (use mem0)
- You want to record everything on your screen, not just AI sessions (use Rewind)
- You want a snippet manager integrated into your IDE (use Pieces)
- You want collaborative editing on a shared wiki (use Notion, Obsidian Publish, or Confluence)
- You need server-side search or a database backend (llmwiki is static-only by design)
