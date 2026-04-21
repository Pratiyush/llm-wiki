---
title: "Agent backend — setup"
type: docs
docs_shell: true
docs_passthrough: true
---

<div style="background: #0D9488; color: white; padding: 8px 16px; border-radius: 6px; font-weight: 600; margin-bottom: 24px;">AGENT MODE — uses your existing Claude Code / Codex CLI session.</div>

# Agent backend — setup

This page walks through enabling the `agent` synthesize backend (#316) — the Mode B companion to the Ollama / dummy backends.

## One-line enable

Set the backend in `sessions_config.json`:

```json
{
  "synthesis": {
    "backend": "agent"
  }
}
```

…then run `/wiki-sync` from inside Claude Code or Codex CLI.  That's it.

## How it works

The agent backend is a thin file-I/O layer over `BaseSynthesizer`.  On each synthesize call:

1. **Backend writes a pending prompt file.**  `llmwiki synthesize` renders the standard `source_page.md` prompt template with the session body + frontmatter, then writes the full prompt to `.llmwiki-pending-prompts/<uuid>.md` under the repo root.

2. **Backend writes a placeholder page.**  `wiki/sources/<project>/<slug>.md` gets a sentinel body:

   ```markdown
   <!-- llmwiki-pending: 3d2a1b0c-…-… -->

   ## Summary

   *Pending agent synthesis — uuid `3d2a1b0c-…-…`.  Prompt at
   `.llmwiki-pending-prompts/3d2a1b0c-…-….md`.*
   ```

3. **Agent reads the prompt on the next turn.**  `/wiki-sync`'s slash command (and the `llmbook-reference` skill) know to look for pending prompts.  Inside the running agent session, the LLM reads the prompt file, synthesizes the actual wiki page body, and calls `complete_pending(uuid, body, page)` which rewrites the placeholder in place.

4. **Prompt file deleted on completion.**  The `.llmwiki-pending-prompts/<uuid>.md` scratch file is removed after a successful completion so the directory never bloats.

## Why no HTTP call?

Because the agent already has an open LLM connection via your existing Claude Code / Codex CLI session.  Making a second HTTP call would double-bill you.  The backend is pure file I/O — the test suite hard-asserts this by neutralising `socket.socket` during synthesis and confirming the call still succeeds.

## Runtime detection

`is_available()` returns `True` when any of these env vars are set:

| Env var | Set by |
|---|---|
| `LLMWIKI_AGENT_MODE` | explicit opt-in (wins over auto-detect) |
| `CLAUDE_CODE` / `CLAUDECODE` | Claude Code session |
| `CODEX_CLI` | Codex CLI session |
| `CURSOR_AGENT` | Cursor chat pane |

Outside an agent runtime, `is_available()` returns `False` and the pipeline falls back to the `dummy` backend instead of silently producing placeholders forever.

## CLI

```bash
# Show pending prompts (0 exit even when empty)
python3 -m llmwiki synthesize --list-pending

# Complete a pending synthesis — body via stdin
python3 -m llmwiki synthesize --complete <uuid> \
  --page wiki/sources/<project>/<slug>.md < body.md

# Complete a pending synthesis — body via file
python3 -m llmwiki synthesize --complete <uuid> \
  --page wiki/sources/<project>/<slug>.md \
  --body /tmp/synth-<uuid>.md
```

Exit codes: `0` success, `1` for any of: missing `--page`, empty body, missing target file, missing sentinel on target page, uuid mismatch between page and `--complete` argument.

## How `/wiki-sync` uses these

Step 6 of the `/wiki-sync` slash command (post-rc8) runs `--list-pending` after ingest. For every pending uuid:

1. Slash command reads `.llmwiki-pending-prompts/<uuid>.md`.
2. Slash command synthesizes the wiki body inside its own agent turn (including the `<!-- suggested-tags: ... -->` block).
3. Slash command writes the body to a scratch file.
4. Slash command runs `llmwiki synthesize --complete <uuid> --page <path> --body <scratch>` which rewrites the placeholder and deletes the prompt file.

The loop is serial — the agent is single-conversation.

## Invariants

- **No network.**  Hard-tested via socket guard.
- **No secrets.**  Works with `ANTHROPIC_API_KEY` unset.
- **Idempotent.**  Re-running `synthesize` on the same slug reuses the existing uuid (no orphan prompt files).
- **Graceful fallback.**  Agent not running → `is_available() = False` → pipeline uses dummy backend.

## Limitations

- **Serial only.**  The agent is single-conversation, so we can't batch.  A 647-session sync takes hours.
- **Context-window bound.**  Very long raw sessions (> 8000 chars) are truncated before being handed to the agent.
- **Needs supervision.**  An unattended cron job can't run agent-mode synthesize — there's no agent on the other end.

## See also

- [Agent mode overview](index.md)
- [API mode](../api/) — Mode A, pay per token, unlocks batch + scheduled sync.
- [CLI reference for `synthesize`](../../reference/cli.md#synthesize--llm-backed-source-page-synthesis)
