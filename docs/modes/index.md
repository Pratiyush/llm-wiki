---
title: "Pick your mode"
type: navigation
docs_shell: true
---

# Pick your mode

llmwiki runs in **two modes** that share the same three-layer
pipeline (`raw/` → `wiki/` → `site/`) but differ on *who calls the LLM*:

| | **Mode A — API** | **Mode B — Agent** |
|---|---|---|
| **How synthesis runs** | Python → Anthropic API | Claude Code / Codex CLI → slash command |
| **API key needed** | Yes (`ANTHROPIC_API_KEY`) | No (uses your agent's subscription) |
| **Batch + parallel** | Yes (native API batching) | No (serial, one turn at a time) |
| **Cost model** | Pay per token (with prompt cache) | Included in your agent subscription |
| **Runs headless?** | Yes (cron / CI) | No (needs interactive agent session) |
| **Best for** | Large corpora, scheduled sync, CI | Exploratory + per-session enrichment |

## When to pick which

- **You have an Anthropic API key and want to batch-ingest 647 sessions once, then schedule a daily top-up:** Mode A.
- **You use Claude Code or Codex CLI daily and don't want to pay an extra API bill:** Mode B.
- **You're evaluating llmwiki locally and just want the dummy / Ollama backend:** neither — see [Tutorial 08](../tutorials/08-synthesize-with-ollama.md) which works with no agent + no API key.

## The two modes share

Everything except synthesis:

- Adapters (`claude_code`, `codex_cli`, `cursor`, `gemini_cli`, `copilot_chat`, `obsidian`, …) work identically.
- The static site, graph viewer, lint rules, backlinks CLI, tag family — all mode-agnostic.
- `sessions_config.json` is the same file; only `synthesis.backend` differs.

## Read next

- **[API mode](api/)** — Python CLI with prompt caching + batch.
- **[Agent mode](agent/)** — slash commands, no API key.
- **[Upgrade guide](../UPGRADING.md)** — how to switch modes safely.
- **Epic:** [#314 · split LLM Wiki into API mode + Agent mode](https://github.com/Pratiyush/llm-wiki/issues/314)
