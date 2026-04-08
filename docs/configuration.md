# Configuration

Every tuning knob in llmwiki, explained.

## Config file

Copy the default config and edit it:

```bash
cp examples/sessions_config.json config.json
```

`config.json` is gitignored so your settings stay local. The converter auto-loads it if present.

Minimal config:

```json
{
  "redaction": {
    "real_username": "your-unix-username",
    "replacement_username": "USER"
  }
}
```

> Replace `your-unix-username` with the output of `whoami`. The converter uses it to scrub paths like `/Users/<name>/…` or `/home/<name>/…` before writing to `raw/`.

## Full schema

```jsonc
{
  "filters": {
    // Skip sessions with a record younger than this many minutes.
    // Prevents the converter from reading a .jsonl mid-write.
    "live_session_minutes": 60,

    // If non-empty, only convert projects whose slug matches one of these.
    "include_projects": [],

    // Skip projects whose slug contains one of these substrings.
    "exclude_projects": [],

    // Record types to drop entirely (noise / hook progress / queue ops)
    "drop_record_types": [
      "queue-operation",
      "file-history-snapshot",
      "progress"
    ]
  },

  "redaction": {
    // Your OS username. Paths like /Users/<you>/ become /Users/USER/.
    // Auto-detected from $USER if left empty.
    "real_username": "",

    // What to replace real_username with.
    "replacement_username": "USER",

    // Additional regexes to redact (Python re syntax).
    // Anything matching → "<REDACTED>".
    "extra_patterns": [
      "(?i)(api[_-]?key|secret|token|bearer|password)[\"'\\s:=]+[\\w\\-\\.]{8,}",
      "sk-[A-Za-z0-9]{20,}",
      "[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\\.[a-zA-Z0-9-.]+"
    ]
  },

  "truncation": {
    // Max chars per tool result before truncation.
    "tool_result_chars": 500,

    // Max lines from a Bash stdout before truncation.
    "bash_stdout_lines": 5,

    // Max lines from a Write tool content preview.
    "write_content_preview_lines": 5,

    // Max chars per user prompt.
    "user_prompt_chars": 4000,

    // Max chars of assistant text rendered in the markdown body.
    "assistant_text_chars": 8000
  },

  // Drop <thinking> blocks from assistant messages entirely.
  // These are verbose and often redundant with the visible response.
  "drop_thinking_blocks": true,

  // Per-adapter config
  "adapters": {
    "obsidian": {
      "vault_paths": ["~/Documents/Obsidian Vault"],
      "exclude_folders": [".obsidian", "Templates", "_templates", ".trash"],
      "min_content_chars": 50
    }
  }
}
```

## Environment variables

| Variable | What it does |
|---|---|
| `LLMWIKI_HOME` | Override the repo root. Defaults to auto-detection from the script location. |
| `LLMWIKI_CONFIG` | Override the config file path. Defaults to `./config.json` then `examples/sessions_config.json`. |

## CLI flags

### `llmwiki sync`

```bash
python3 -m llmwiki sync [options]

--adapter <name...>       Only run the named adapter(s); default: all available
--since YYYY-MM-DD        Skip sessions with a last record older than this
--project <substring>     Only sync projects whose slug contains this substring
--include-current         Don't skip live (<60 min) sessions
--force                   Ignore the state file; reconvert everything
--dry-run                 Preview what would be written, don't touch disk
```

### `llmwiki build`

```bash
python3 -m llmwiki build [options]

--out <dir>               Output directory; default: ./site
--synthesize              Call the `claude` CLI once to generate an Overview
--claude <path>           Path to the claude binary; default: /usr/local/bin/claude
```

### `llmwiki serve`

```bash
python3 -m llmwiki serve [options]

--dir <dir>               Directory to serve; default: ./site
--port N                  Port number; default: 8765
--host H                  Host to bind; default: 127.0.0.1 (localhost only)
--open                    Open the browser after starting
```

### `llmwiki init`

No options. Scaffolds `raw/`, `wiki/`, `site/` and seeds `wiki/index.md`, `wiki/log.md`, `wiki/overview.md`.

### `llmwiki adapters`

No options. Lists every registered adapter and whether its session store is present on the current machine.

## `.llmwikiignore`

Gitignore-style file at the repo root. One pattern per line. Sessions matching any pattern are skipped during sync.

Example:

```
# Skip a whole project
confidential-client/*

# Skip anything before a date
*2025-11-*

# Skip a specific session
ai-newsletter/2026-04-04-*secret*
```

## Adapter configuration

### Claude Code

Default session store: `~/.claude/projects/`

Override via the adapter config block (above).

### Obsidian

Default vault locations checked:

1. `~/Documents/Obsidian Vault`
2. `~/Obsidian`

Override in `config.json`:

```jsonc
{
  "adapters": {
    "obsidian": {
      "vault_paths": [
        "~/Documents/Obsidian Vault",
        "~/work/second-vault"
      ],
      "exclude_folders": [".obsidian", "Templates"],
      "min_content_chars": 100
    }
  }
}
```

Files smaller than `min_content_chars` are skipped (mostly empty notes).

### Codex CLI

**v0.1 stub.** The adapter imports and registers but does not yet parse records. Configuration will land in v0.2.

## Changing the theme

Theme colours live in `llmwiki/build.py` inside the `CSS` string constant, under the `:root` block. The main tokens:

```css
--accent: #7C3AED;     /* primary accent (purple) */
--accent-light: #a78bfa;
--accent-bg: #f5f3ff;
```

Change these and rebuild. The dark-mode variants auto-derive unless you override them too.
