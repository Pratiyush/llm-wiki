---
title: "OpenCode / OpenClaw adapter"
type: navigation
docs_shell: true
---

# OpenCode / OpenClaw adapter

Reads `.jsonl` session transcripts written by the
[OpenCode](https://github.com/sst/opencode) / OpenClaw agents —
both use an identical schema.

**AI-session adapter** (`is_ai_session = True`) — fires by default
when its session store is present on disk.

## Session store

The adapter auto-detects the store across platforms:

- **Linux:** `~/.config/opencode/sessions/` and `~/.config/openclaw/sessions/`
- **macOS:** `~/Library/Application Support/opencode/sessions/` and
  `~/Library/Application Support/openclaw/sessions/`
- **Windows:** `%APPDATA%\opencode\sessions\` and `%APPDATA%\openclaw\sessions\`

Both nested (`<project>/<session>.jsonl`) and flat
(`<project>-<session>.jsonl`) layouts are handled.

## What it reads

Each session is a JSONL stream of `{role, content}` records:

```json
{"role": "user",      "content": "start a new feature"}
{"role": "assistant", "content": "…"}
{"role": "tool",      "content": "…"}
```

`normalize_records()` translates that schema into the Claude-style
`{type, message: {role, content}}` that the shared renderer expects:

| OpenCode role | Claude-style type | Claude-style role |
|---|---|---|
| `user` | `user` | `user` |
| `assistant` | `assistant` | `assistant` |
| `tool` | `user` | `tool` (preserved so the renderer can show tool turns distinctly) |

## Enable it

Works out-of-the-box if OpenCode / OpenClaw is installed on this
machine.  To explicitly disable:

```jsonc
// sessions_config.json
{ "opencode": { "enabled": false } }
```

## Output layout

Standard `raw/sessions/<YYYY-MM-DDTHH-MM>-<project>-<slug>.md`.

## Code

- `llmwiki/adapters/contrib/opencode.py`
- Tests: `tests/test_opencode_adapter.py` (23 cases)
- Issue history: #43 (initial)

## See also

- [All adapters](../../README.md#works-with) — comparison table of
  every agent adapter llmwiki supports out of the box.
