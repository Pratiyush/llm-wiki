# Getting started

5-minute quickstart. By the end you'll have a browsable wiki of every Claude Code session you've ever run.

## Prerequisites

- Python ≥ 3.9 (macOS ships 3.9+ by default; most Linux distros do too)
- `git`
- A few Claude Code or Codex CLI sessions already on disk — llmwiki reads them from your agent's default session store

That's it. No `npm`, no `brew`, no database, no account.

## Install

### macOS / Linux

```bash
git clone https://github.com/Pratiyush/llm-wiki.git
cd llm-wiki
./setup.sh
```

### Windows

```cmd
git clone https://github.com/Pratiyush/llm-wiki.git
cd llm-wiki
setup.bat
```

`setup.sh` / `setup.bat` does the following, idempotently:

1. Installs `markdown` (the only runtime dep) via `pip install --user`. Syntax highlighting runs in the browser via highlight.js loaded from a CDN, so the build stays stdlib-only.
2. Scaffolds `raw/`, `wiki/`, `site/` directories
3. Runs `llmwiki adapters` to show which agents are detected
4. Does a dry-run of the first sync so you see what *would* be converted

## Three commands after install

```bash
./sync.sh        # pull new sessions from your agent store → raw/sessions/<project>/*.md
./build.sh       # compile raw/ + wiki/ → site/
./serve.sh       # serve site/ at http://127.0.0.1:8765/
```

Open [http://127.0.0.1:8765/](http://127.0.0.1:8765/) and click around. Try:

- **⌘K** or **Ctrl+K** — command palette
- **/** — focus the search bar
- **g h / g p / g s** — jump to home / projects / sessions
- **j / k** — navigate sessions table
- **?** — keyboard shortcut help

## Where your data ends up

```
llm-wiki/
├── raw/sessions/             # [gitignored] converted transcripts
│   ├── ai-newsletter/
│   │   ├── 2026-04-04-<slug>.md
│   │   └── ...
│   └── <other-project>/
├── wiki/                     # [gitignored] LLM-maintained wiki pages
│   ├── index.md
│   ├── log.md
│   ├── overview.md
│   ├── sources/
│   ├── entities/
│   └── concepts/
└── site/                     # [gitignored] generated static HTML
    ├── index.html
    ├── style.css
    ├── script.js
    ├── search-index.json
    ├── projects/
    └── sessions/
```

Everything under `raw/`, `wiki/`, and `site/` stays **local**. It is never committed and never sent anywhere.

## Building the wiki (Karpathy layer 2)

The `sync` step populates `raw/sessions/` with markdown. To build the actual **wiki** on top of that — `wiki/sources/`, `wiki/entities/`, `wiki/concepts/`, linked by `[[wikilinks]]` — you need an LLM in the loop. That's where Claude Code (or Codex CLI) comes in.

Inside a Claude Code session at the llm-wiki repo root:

```
/wiki-ingest raw/sessions/ai-newsletter/
```

The agent reads the source markdowns, writes summary pages, cross-links entities, and updates `wiki/index.md`. See [CLAUDE.md](../CLAUDE.md) for the full Ingest Workflow.

Then re-run `./build.sh` to get the compiled wiki into the HTML site.

## Auto-sync on session start (optional)

To make sync happen automatically every time you start Claude Code, add a `SessionStart` hook to `~/.claude/settings.json`:

```json
{
  "hooks": {
    "SessionStart": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "(python3 /absolute/path/to/llm-wiki/llmwiki/convert.py > /tmp/llmwiki-sync.log 2>&1 &) ; exit 0"
          }
        ]
      }
    ]
  }
}
```

The `( ... &) ; exit 0` pattern backgrounds the sync and makes sure it never blocks Claude Code starting.

## Next steps

- [architecture.md](architecture.md) — the 3-layer Karpathy + 8-layer build breakdown
- [configuration.md](configuration.md) — every tuning knob
- [privacy.md](privacy.md) — redaction + `.llmwikiignore` + localhost-only binding
- [adapters/claude-code.md](adapters/claude-code.md) — Claude Code adapter details
- [adapters/obsidian.md](adapters/obsidian.md) — use an Obsidian vault as an additional source
