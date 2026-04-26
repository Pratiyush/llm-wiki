# Multi-Agent Setup

llmwiki reads sessions from multiple coding agents simultaneously. One `llmwiki sync` pulls from every agent installed on your machine.

## Supported agents

| Agent | Registry name | Session store | Status |
|---|---|---|---|
| Claude Code | `claude_code` | `~/.claude/projects/` | Production |
| Codex CLI | `codex_cli` | `~/.codex/sessions/` | Production |
| GitHub Copilot Chat | `copilot-chat` | VS Code workspaceStorage | Production |
| GitHub Copilot CLI | `copilot-cli` | `~/.copilot/session-state/` | Production |
| Cursor | `cursor` | Cursor IDE workspaceStorage | Scaffold (SQLite parser in progress) |
| Gemini CLI | `gemini_cli` | `~/.gemini/` | Scaffold (schema TBC) |
| Obsidian | `obsidian` | Configurable vault paths | Production |
| PDF | `pdf` | Any `.pdf` dropped into `raw/` | Production |

## How auto-detection works

When you run `llmwiki sync`, the system:

1. Imports every adapter in `llmwiki/adapters/`
2. Calls `is_available()` on each — this checks whether the session store path exists on disk
3. Runs only the available adapters (or those you specify with `--adapter`)

No configuration file is needed. If you have Claude Code and Codex CLI installed, both get picked up automatically.

## Checking detected agents

```bash
python3 -m llmwiki adapters
```

Example output:

```
Registered adapters:
  claude_code       available: yes  (Claude Code — reads ~/.claude/projects/*/*.jsonl)
  codex_cli         available: yes  (Codex CLI — reads ~/.codex/sessions/**/*.jsonl)
  copilot-chat      available: no   (GitHub Copilot Chat — reads VS Code workspaceStorage chatSessions)
  copilot-cli       available: no   (GitHub Copilot CLI — reads ~/.copilot/session-state/*/events.jsonl)
  cursor            available: yes  (Cursor IDE — reads chat history)
  gemini_cli        available: no   (Gemini CLI — reads ~/.gemini/ session history)
  obsidian          available: no   (Obsidian vault)
  pdf               available: yes  (PDF files)
```

## Per-agent setup

### Claude Code

Installed automatically if you use Claude Code. Sessions live at `~/.claude/projects/<project-dir-slug>/<session-uuid>.jsonl`. Sub-agent runs are under `subagents/agent-*.jsonl`.

No configuration needed.

### Codex CLI

Install Codex CLI from OpenAI. Sessions are stored at `~/.codex/sessions/` in date-bucketed directories. The adapter reads the `session_meta` record's `cwd` field to derive the project slug.

The adapter normalizes Codex's native JSONL schema (which uses `response_item` and `event_msg` record types) into the shared format automatically.

### GitHub Copilot Chat

Requires the Copilot Chat extension in VS Code, VS Code Insiders, or VSCodium. Sessions live in the editor's workspaceStorage directory under `chatSessions/`.

The adapter checks all three editor variants across macOS, Linux, and Windows paths.

### GitHub Copilot CLI

Requires the Copilot CLI tool. Sessions are stored as `events.jsonl` files under `~/.copilot/session-state/<session-id>/`.

Set `COPILOT_HOME` to override the default `~/.copilot` base directory.

### Cursor

Requires Cursor IDE. The adapter detects the Cursor workspace storage directory. Full SQLite record parsing is in progress; currently discovers `.jsonl` files if present.

### Gemini CLI

Requires Google's Gemini CLI. The adapter checks `~/.gemini/`, `~/.config/gemini/`, `~/.local/share/gemini/`, and `%APPDATA%/gemini/` on Windows.

## Syncing from all agents

```bash
# Sync everything
python3 -m llmwiki sync

# Sync only specific adapters
python3 -m llmwiki sync --adapter claude_code codex_cli

# Dry run to preview
python3 -m llmwiki sync --dry-run
```

The sync is idempotent. State is tracked in `.llmwiki-state.json` by file mtime, so re-running on unchanged files is a fast no-op.

## Agent labels in the UI

Each session in the built site shows a colored badge indicating which agent produced it. The badge is derived from the adapter name in the session's YAML frontmatter. This makes it easy to filter and browse sessions by agent when you use multiple tools.

## Per-adapter configuration

Override adapter paths in `config.json`:

```json
{
  "adapters": {
    "codex_cli": {
      "roots": ["~/custom/codex/sessions"]
    },
    "copilot-chat": {
      "roots": ["/path/to/vscode/workspaceStorage"]
    },
    "gemini_cli": {
      "roots": ["~/.gemini"]
    },
    "obsidian": {
      "vault_paths": ["~/Documents/My Vault"],
      "exclude_folders": [".obsidian", "Templates"],
      "min_content_chars": 50
    }
  }
}
```

## Tips for multi-agent workflows

1. **Use `--adapter` to test one agent at a time** when debugging sync issues.
2. **Each agent gets its own project slug** derived from its session store layout, so sessions from different agents never collide.
3. **The wiki layer is agent-agnostic.** Once sessions are in `raw/`, the wiki ingest treats them identically regardless of which agent produced them.
4. **Schedule `llmwiki sync`** via `launchd` / `systemd` / Task Scheduler for periodic auto-sync across all agents (the `llmwiki watch` daemon was removed in v1.2.0 — see `docs/UPGRADING.md`).
5. **Combine with `.llmwikiignore`** to skip noisy agents or specific projects from any adapter.
