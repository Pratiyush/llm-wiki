---
title: "API mode"
type: navigation
docs_shell: true
---

<div style="background: #7C3AED; color: white; padding: 8px 16px; border-radius: 6px; font-weight: 600; margin-bottom: 24px;">API MODE — uses your Anthropic API key.</div>

# Mode A · API

Runs synthesis + query against the Anthropic API directly.  Faster
than Agent mode on large corpora (batch API + prompt cache), costs
money per token, doesn't require Claude Code to be running.

## Status

Scaffolding has shipped — the prompt caching + batch primitives live
in `llmwiki/cache.py`. The full backend lands in
**[#315 · feat: Mode A claude-api synthesis backend with prompt caching](https://github.com/Pratiyush/llm-wiki/issues/315)**.

Until #315 merges, use the **Ollama backend** as a stand-in:
[Tutorial 08 — Synthesize with Ollama](../../tutorials/08-synthesize-with-ollama.md).

## Setup (once #315 ships)

```bash
# In your repo root:
echo "ANTHROPIC_API_KEY=sk-ant-…" >> .env
```

```jsonc
// sessions_config.json
{
  "synthesis": {
    "backend": "claude-api",
    "claude_api": {
      "model": "claude-sonnet-4-6",
      "max_retries": 3
    }
  }
}
```

## Daily flow

```bash
llmwiki synthesize --estimate      # cost preview
llmwiki synthesize                 # batch run with prompt caching
llmwiki build && llmwiki serve --open
```

## Cost model

- **Prompt prefix** (CLAUDE.md + wiki/index.md + wiki/overview.md) is
  cached — one write on the first call, free reads on every subsequent
  call.
- See [prompt caching reference](../../reference/prompt-caching.md) for
  the token math.
- `synthesize --estimate` gives you an incremental-vs-full-force
  breakdown before you spend money.

## When to pick this mode

- Large corpora (100+ sessions) where serial Agent-mode synthesis
  would take hours.
- Headless runs: cron, CI, `launchd` / `systemd` scheduling of `llmwiki sync`.
- Shared server (multiple developers syncing into one wiki) — the API
  key belongs to the server, not individual laptops.

## See also

- [Agent mode](../agent/) — if you already use Claude Code, try this first.
- [Configuration reference — synthesis section](../../configuration-reference.md#full-schema)
- [Prompt caching reference](../../reference/prompt-caching.md)
