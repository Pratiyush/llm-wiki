# Configuration Reference

Complete reference for all CLI subcommands, flags, environment variables, and configuration options.

## CLI subcommands

### `llmwiki init`

Scaffold the `raw/`, `wiki/`, `site/` directory structure and seed initial wiki files.

```bash
python3 -m llmwiki init
```

No options. Creates directories and seeds `wiki/index.md`, `wiki/log.md`, `wiki/overview.md` if they don't already exist.

### `llmwiki sync`

Convert agent session transcripts (`.jsonl`) into markdown under `raw/sessions/`.

```bash
python3 -m llmwiki sync [options]
```

| Flag | Type | Default | Description |
|---|---|---|---|
| `--adapter` | `name...` | all available | Only run the named adapter(s) |
| `--since` | `YYYY-MM-DD` | none | Only sessions on or after this date |
| `--project` | `substring` | none | Only sync projects whose slug contains this |
| `--include-current` | flag | off | Don't skip live sessions (< 60 min old) |
| `--force` | flag | off | Ignore state file, reconvert everything |
| `--dry-run` | flag | off | Preview what would be written |
| `--download-images` | flag | off | Download remote images in `.md` files to `raw/assets/` |

### `llmwiki build`

Compile the static HTML site from `raw/` and `wiki/`.

```bash
python3 -m llmwiki build [options]
```

| Flag | Type | Default | Description |
|---|---|---|---|
| `--out` | `path` | `./site` | Output directory |
| `--synthesize` | flag | off | Call `claude` CLI to generate an Overview synthesis |
| `--claude` | `path` | `/usr/local/bin/claude` | Path to the claude binary |

### `llmwiki serve`

Start a local HTTP server for the built site.

```bash
python3 -m llmwiki serve [options]
```

| Flag | Type | Default | Description |
|---|---|---|---|
| `--dir` | `path` | `./site` | Directory to serve |
| `--port` | `int` | `8765` | Port number |
| `--host` | `string` | `127.0.0.1` | Host to bind (use `0.0.0.0` to expose to network) |
| `--open` | flag | off | Open browser after starting |

### `llmwiki adapters`

List every registered adapter and whether its session store is present.

```bash
python3 -m llmwiki adapters
```

No options.

### `llmwiki graph`

Build the knowledge graph from `wiki/` wikilinks.

```bash
python3 -m llmwiki graph [options]
```

| Flag | Type | Default | Description |
|---|---|---|---|
| `--format` | `json\|html\|both` | `both` | Output format |

### `llmwiki export`

Export AI-consumable formats from the built site.

```bash
python3 -m llmwiki export <format> [options]
```

| Positional | Values |
|---|---|
| `format` | `llms-txt`, `llms-full-txt`, `jsonld`, `sitemap`, `rss`, `robots`, `ai-readme`, `marp`, `all` |

| Flag | Type | Default | Description |
|---|---|---|---|
| `--out` | `path` | `./site` | Output directory |
| `--topic` | `string` | none | Topic filter (used by `marp` format) |

### `llmwiki all` (v1.2)

Run the full pipeline: build → graph → export all → lint.

```bash
python3 -m llmwiki all [options]
```

| Flag | Type | Default | Description |
|---|---|---|---|
| `--out` | `path` | `./site` | Output directory |
| `--search-mode` | `auto/tree/flat` | `auto` | Forwarded to build |
| `--graph-engine` | `builtin/graphify` | `graphify` | Forwarded to graph |
| `--skip-graph` | flag | off | Skip the graph step |
| `--strict` | flag | off | Exit 2 on any lint error or warning (CI gate) |
| `--fail-fast` | flag | off | Stop at first non-zero step |

### `llmwiki version`

Print the current version.

```bash
python3 -m llmwiki version
```

## Config file (`config.json`)

Copy the example and edit:

```bash
cp examples/sessions_config.json config.json
```

`config.json` is gitignored. The converter auto-loads it if present at the repo root.

### Full schema

```jsonc
{
  "filters": {
    "live_session_minutes": 60,
    "include_projects": [],
    "exclude_projects": [],
    "drop_record_types": ["queue-operation", "file-history-snapshot", "progress"]
  },

  "redaction": {
    "real_username": "",
    "replacement_username": "USER",
    "extra_patterns": [
      "(?i)(api[_-]?key|secret|token|bearer|password)[\"'\\s:=]+[\\w\\-\\.]{8,}",
      "sk-[A-Za-z0-9]{20,}",
      "[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\\.[a-zA-Z0-9-.]+"
    ]
  },

  "truncation": {
    "tool_result_chars": 500,
    "bash_stdout_lines": 5,
    "write_content_preview_lines": 5,
    "user_prompt_chars": 4000,
    "assistant_text_chars": 8000
  },

  "drop_thinking_blocks": true,

  "adapters": {
    "obsidian": {
      "vault_paths": ["~/Documents/Obsidian Vault"],
      "exclude_folders": [".obsidian", "Templates"],
      "min_content_chars": 50
    },
    "codex_cli": {
      "roots": ["~/.codex/sessions", "~/.codex/projects"]
    },
    "gemini_cli": {
      "roots": ["~/.gemini"]
    }
  }
}
```

### Section reference

| Section | Key | Type | Default | Description |
|---|---|---|---|---|
| `filters` | `live_session_minutes` | int | 60 | Skip sessions younger than this (prevents reading mid-write) |
| `filters` | `include_projects` | list | [] | If non-empty, only sync matching project slugs |
| `filters` | `exclude_projects` | list | [] | Skip projects containing these substrings |
| `filters` | `drop_record_types` | list | [3 types] | JSONL record types to discard |
| `redaction` | `real_username` | string | `$USER` | Your OS username (auto-detected if empty) |
| `redaction` | `replacement_username` | string | `USER` | Replacement in path redaction |
| `redaction` | `extra_patterns` | list | [3 regexes] | Additional Python regex patterns to redact |
| `truncation` | `tool_result_chars` | int | 500 | Max chars per tool result |
| `truncation` | `bash_stdout_lines` | int | 5 | Max lines from bash output |
| `truncation` | `write_content_preview_lines` | int | 5 | Max lines from Write tool preview |
| `truncation` | `user_prompt_chars` | int | 4000 | Max chars per user prompt |
| `truncation` | `assistant_text_chars` | int | 8000 | Max chars of assistant text |
| root | `drop_thinking_blocks` | bool | true | Drop `<thinking>` blocks from output |
| `adapters` | per-adapter | object | varies | Override adapter-specific settings |
| `schedule` | `build` | enum | `"on-sync"` | When `/wiki-build` runs. `on-sync` / `daily` / `weekly` / `manual` / `never`. |
| `schedule` | `lint` | enum | `"manual"` | When `/wiki-lint` runs. Same enum. |
| `synthesis` | `backend` | enum | `"dummy"` | Which synthesizer: `"dummy"` / `"ollama"`. The Claude API backend ships with #315. |
| `synthesis.ollama` | `model` | string | `"llama3.1:8b"` | Ollama model name (pull via `ollama pull`) |
| `synthesis.ollama` | `base_url` | string | `"http://127.0.0.1:11434"` | Ollama HTTP endpoint |
| `synthesis.ollama` | `timeout` | int (s) | 60 | Per-request timeout |
| `synthesis.ollama` | `max_retries` | int | 3 | Exponential-backoff retry count on 5xx / timeout |
| `pdf` | `enabled` | bool | false | Opt-in; non-AI adapter (#326) |
| `pdf` | `source_dirs` | list | `["~/Documents/PDFs"]` | Directories to scan |
| `pdf` | `min_pages` | int | 1 | Skip PDFs with fewer pages |
| `pdf` | `max_pages` | int | 500 | Skip PDFs with more pages (cost guard) |
| `meeting` | `enabled` | bool | false | Opt-in; non-AI adapter |
| `meeting` | `source_dirs` | list | `["~/Meetings"]` | Directories to scan |
| `meeting` | `extensions` | list | `[".vtt", ".srt"]` | File extensions to consider |
| `jira` | `enabled` | bool | false | Opt-in; non-AI adapter |
| `jira` | `server` | string | — | Jira Cloud/Server URL |
| `jira` | `email` | string | — | Account email |
| `jira` | `api_token` | string | `""` | Prefer `api_token_env` + `.env` |
| `jira` | `jql` | string | sensible default | Query for tickets to sync |
| `jira` | `max_results` | int | 50 | Pagination cap |
| `chatgpt` | `enabled` | bool | false | Opt-in; requires explicit `conversations_json` |
| `chatgpt` | `conversations_json` | string | — | Path to export file |
| `web_clipper` | `enabled` | bool | false | Obsidian Web Clipper intake path |
| `web_clipper` | `watch_dir` | string | `"raw/web"` | Directory to watch |
| `web_clipper` | `extensions` | list | `[".md"]` | File extensions to pick up |
| `web_clipper` | `auto_queue` | bool | true | Auto-add to `.llmwiki-queue.json` |

## Environment variables

| Variable | Description | Default |
|---|---|---|
| `LLMWIKI_HOME` | Override the repo root directory | Auto-detected from script location |
| `LLMWIKI_CONFIG` | Override the config file path | `./config.json`, then `examples/sessions_config.json` |
| `COPILOT_HOME` | Override the Copilot CLI base directory | `~/.copilot` |

## `.llmwikiignore`

Gitignore-style file at the repo root. One pattern per line. Sessions matching any pattern are skipped during sync.

```
# Skip a whole project
confidential-client/*

# Skip anything before a date
*2025-11-*

# Skip a specific session
ai-newsletter/2026-04-04-*secret*

# Comments start with #
# Blank lines are ignored
```

## Per-adapter configuration

Each adapter can be configured in the `adapters` section of `config.json`. The key must match the adapter's registry name.

| Adapter | Config key | AI session? | Configurable fields |
|---|---|---|---|
| Claude Code | `claude_code` | yes (default on) | `roots` |
| Codex CLI | `codex_cli` | yes (default on) | `roots` |
| Copilot Chat | `copilot-chat` | yes (default on) | `roots` |
| Copilot CLI | `copilot-cli` | yes (default on) | `roots` |
| Cursor | `cursor` | yes (default on) | `roots` |
| Gemini CLI | `gemini_cli` | yes (default on) | `roots` |
| OpenCode / OpenClaw | `opencode` | yes (default on) | `roots` |
| ChatGPT | `chatgpt` | yes (opt-in) | `enabled`, `conversations_json` |
| Obsidian | `obsidian` | **no** (opt-in) | `vault_paths`, `exclude_folders`, `min_content_chars` |
| Jira | `jira` | **no** (opt-in) | `server`, `email`, `api_token` / `api_token_env`, `jql`, `max_results` |
| Meeting transcripts | `meeting` | **no** (opt-in) | `source_dirs`, `extensions` |
| PDF | `pdf` | **no** (opt-in) | `source_dirs`, `min_pages`, `max_pages` |

Non-AI-session adapters are opt-in only (#326) — set `{name}.enabled: true` in this config to have them fire on `sync`.

Example:

```json
{
  "adapters": {
    "copilot-chat": {
      "roots": ["/custom/path/to/vscode/workspaceStorage"]
    }
  }
}
```
