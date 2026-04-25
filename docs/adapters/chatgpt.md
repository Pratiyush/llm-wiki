---
title: "ChatGPT adapter"
type: navigation
docs_shell: true
---

# ChatGPT adapter

Ingests your **ChatGPT conversation export** (`conversations.json`) so
every chat you ever had becomes part of the wiki alongside Claude Code
/ Codex / Cursor sessions.

Opt-in — the adapter is marked `is_ai_session = True` but **`default: no`**
because the source file lives in a user-chosen path.

## What it reads

A single `conversations.json` exported via Settings → Data Controls →
Export Data in the ChatGPT web app.  The file carries every
conversation in your account.  The adapter:

1. Parses the parent→children `mapping` tree for each conversation.
2. Linearises the active chain (the one that made it to the final
   response) — no dead branches.
3. Extracts `role` + `text` per node, skipping tool / system nodes.
4. Emits frontmatter-tagged markdown under `raw/sessions/chatgpt/`.

## Enable it

Copy the export somewhere stable (e.g. `~/Documents/chatgpt-export/`)
and point the adapter at `conversations.json`:

```jsonc
// sessions_config.json
{
  "chatgpt": {
    "enabled": true,
    "conversations_json": "~/Documents/chatgpt-export/conversations.json"
  }
}
```

Then:

```bash
llmwiki sync --adapter chatgpt
```

If `enabled` is omitted the adapter stays silent (AI-session-opt-in
rule from #326 doesn't apply because the default `conversations_json`
path is unknown — we need explicit opt-in).

## Output layout

```
raw/sessions/chatgpt/<YYYY-MM-DDTHH-MM>-chatgpt-<slug>.md
```

Where `<slug>` comes from the conversation title (sanitised to
filesystem-safe chars via the usual slug normaliser).

## Gotchas

- Re-exporting overwrites the old `conversations.json`.  Re-sync after
  each export to pick up new conversations — the existing state file
  handles idempotency for unchanged conversations.
- GPT-4o sessions include image/audio modalities; the adapter drops
  those and keeps only the text turns (a future PR could inline
  transcribed audio).
- The source file can exceed 100 MB — first sync takes a minute.

## Code

- `llmwiki/adapters/contrib/chatgpt.py`
- Tests: `tests/test_chatgpt_adapter.py` (28 cases)
- Issue history: #44 (initial) · #326 (is_ai_session flag)

## See also

- [CLI `adapters` subcommand](../reference/cli.md#adapters--list-every-adapter--its-status)
- [Configuration reference](../configuration-reference.md)
