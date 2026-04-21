---
title: "Agent mode"
type: navigation
docs_shell: true
---

<div style="background: #0D9488; color: white; padding: 8px 16px; border-radius: 6px; font-weight: 600; margin-bottom: 24px;">AGENT MODE — uses your existing Claude Code / Codex CLI session.</div>

# Mode B · Agent

Runs synthesis + query **inside** the Claude Code or Codex CLI session
that's already open on your machine — no separate API key, no
incremental cost beyond your existing agent subscription.

## Status

**Shipping in v1.1.0-rc8 (#316).** Every slash command is prompt-
driven — `/wiki-sync`, `/wiki-ingest`, `/wiki-query`, `/wiki-reflect`,
`/wiki-update`, `/wiki-lint`.  The new `agent-delegate` synthesize
backend closes the last remaining gap: `llmwiki synthesize` now writes
rendered prompts to `.llmwiki-pending-prompts/<uuid>.md` and returns a
placeholder page with a `<!-- llmwiki-pending: <uuid> -->` sentinel.
The running agent picks the pending prompts up on the next turn and
calls `llmwiki synthesize --complete <uuid>` to rewrite the page with
the actual synthesis.

Zero incremental API cost.  Zero bytes of session content leave your
laptop.  Works when `ANTHROPIC_API_KEY` is unset.

## Setup (no API key)

Just install the slash commands:

```bash
llmwiki install-skills   # copies .claude/commands/*.md into ~/.claude/
```

That's it.  Open Claude Code, type `/wiki-sync`, and it runs.

## Daily flow

```
You: /wiki-sync
Claude: (runs python3 -m llmwiki sync, ingests new pages)

You: /wiki-query when did I last change the convert pipeline?
Claude: (reads wiki/index.md + the relevant source pages, synthesizes)

You: /wiki-graph
Claude: (writes graph/ + opens site/graph.html in your browser)
```

## When to pick this mode

- You already pay for Claude Code or Codex CLI — no extra bill.
- Exploratory work where you want the model to narrate what it's
  doing ("I'm now reading wiki/sources/...").
- Small-to-medium corpus (< 50 sessions) — serial synthesis isn't a
  bottleneck.
- Local-only privacy — no session content leaves your laptop except
  through the agent's existing plumbing.

## Limitations vs Mode A

- **Serial only** — one turn at a time, no batch.  A 647-session
  sync takes hours.
- **Needs the agent to be running** — can't schedule via cron.
- **Subject to the agent's context window** — long synthesize runs
  get truncated.

## See also

- [API mode](../api/) — pay per token to unlock batch + headless.
- [Slash commands reference](../../reference/slash-commands.md) — every
  `/wiki-*` command in one list.
- [Cheatsheet](../../cheatsheet.md) — daily-flow commands on one page.
