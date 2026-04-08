# Claude Code adapter

**Status:** ✅ Production (v0.1)
**Module:** `llmwiki.adapters.claude_code`
**Source:** [`llmwiki/adapters/claude_code.py`](../../llmwiki/adapters/claude_code.py)

## What it reads

Claude Code writes one `.jsonl` per session under:

```
~/.claude/projects/<project-dir-slug>/<session-uuid>.jsonl
```

Sub-agent runs (from the `Task` / `Agent` tools) live at:

```
~/.claude/projects/<project-dir-slug>/<session-uuid>/subagents/agent-*.jsonl
```

The adapter walks both locations recursively.

## Project slug derivation

Claude Code encodes the full absolute path of the project into the directory name, with slashes replaced by dashes:

```
/Users/USER/Desktop/2026/production-draft/ai-newsletter
  ↓
-Users-USER-Desktop-2026-production-draft-ai-newsletter
```

The adapter strips the common prefix (`-Users-<user>-Desktop-...-production-draft-`) and returns the friendly project name. So the slug used in `raw/sessions/<project>/…` becomes just `ai-newsletter`.

If the path doesn't contain the expected marker (`draft`, `production`, or `Desktop`), the adapter falls back to the last two path components joined with a dash.

## Known record types

The adapter parses every record type that Claude Code writes as of version 2.x:

| `type` | What it is | How we handle it |
|---|---|---|
| `user` with string content | Real user prompt | Rendered as `### Turn N — User` |
| `user` with array content | Tool-result delivery | Rendered under `**Tool results:**` |
| `assistant` | Model response | Rendered as `### Turn N — Assistant` with text + tool calls |
| `queue-operation` | Internal scheduler | Dropped |
| `file-history-snapshot` | File tracking snapshot | Dropped |
| `progress` | Hook execution log | Dropped |

The list of dropped types lives in `examples/sessions_config.json` under `filters.drop_record_types`. You can add more there without touching code.

## Schema versions supported

```python
SUPPORTED_SCHEMA_VERSIONS = ["2.x"]  # tested against Claude Code 2.1.87
```

When a new version of Claude Code ships, the adapter's behaviour is:

1. Known record types continue to parse as before
2. **Unknown record types are skipped at DEBUG level** — the converter never crashes on a record it doesn't recognise
3. A snapshot test diff will flag any field renames or structural changes

## Redaction specifics for Claude Code

The default redaction config handles Claude Code sessions well because:

- User prompts, file paths, and tool outputs all go through the same `Redactor`
- `/Users/<you>/` is replaced before rendering
- API keys in Bash command outputs, Read/Write tool inputs, and assistant text are all caught by the `sk-...` and `api_key:...` patterns
- Emails in tool results are caught by the email regex

Thinking blocks (`type: "thinking"` inside assistant messages) are **dropped entirely by default**. They're verbose and often contain unredacted reasoning about secrets. Set `drop_thinking_blocks: false` in config if you want them back.

## Live-session detection

Claude Code appends to the current session's `.jsonl` as records happen. If llmwiki reads a file mid-write, it may get a truncated view or corrupt the user's state. To prevent this, the adapter (and `convert.py`) **skips any file whose last record is younger than 60 minutes**.

This means:

- A session that ended more than an hour ago → converted on next sync
- A session that ended 5 minutes ago → skipped until the next sync that runs more than an hour after it ended
- A session that's still active → always skipped

Override with `--include-current` or lower `filters.live_session_minutes` in config.

## Sub-agent handling

When the `Task` or `Agent` tool is used, Claude Code writes the sub-agent's conversation to a separate file under `subagents/`. The adapter treats these as **separate session pages** but tags them with `is_subagent: true` in the frontmatter so they can be grouped under the parent on project pages.

File naming for sub-agents:

```
raw/sessions/<project>/<date>-<parent-slug>-subagent-<agent-id-8>.md
```

## Testing the adapter

```bash
python3 -m llmwiki adapters      # should list claude_code as available
python3 -m llmwiki sync --dry-run --project ai-newsletter
```

## Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| `available: no` in adapters list | `~/.claude/projects/` doesn't exist | Run Claude Code at least once |
| Zero sessions converted, all "live" | Live filter too aggressive | `--include-current` or lower `live_session_minutes` |
| Sessions show wrong project name | Path marker not found | Check `derive_project_slug()` fallback |
| Unredacted paths in output | `real_username` not set | Edit `config.json` |
| `module 'tomllib' not found` | Old converter version | Update to current version (uses `json`, not `tomllib`) |

## Reference

- [Claude Code session format](https://docs.claude.com/claude-code/session-history) (if the docs page exists — TODO verify)
- [`llmwiki/adapters/claude_code.py`](../../llmwiki/adapters/claude_code.py) — the adapter source
- [`llmwiki/convert.py`](../../llmwiki/convert.py) — the shared converter
