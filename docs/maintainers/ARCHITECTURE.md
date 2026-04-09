# Maintainer architecture one-pager

> **Audience:** code reviewers and new maintainers. If you're a user,
> read [`../architecture.md`](../architecture.md) instead — that one is
> written for contributors. This page is the 5-minute "what can land
> where, and what should never land anywhere" version.

## The three layers (Karpathy)

```
┌─────────────────────────────────────────────────┐
│  raw/sessions/             IMMUTABLE            │
│    • converted .jsonl → .md                     │
│    • gitignored — never lands in a PR          │
│    • owned by llmwiki/convert.py + adapters    │
└───────────────────┬─────────────────────────────┘
                    ▼ reads
┌─────────────────────────────────────────────────┐
│  wiki/                     LLM-MAINTAINED       │
│    • sources/ entities/ concepts/ syntheses/   │
│      projects/ vs/                              │
│    • gitignored EXCEPT seed files listed in    │
│      .gitignore `!wiki/...` exceptions          │
│    • owned by Claude Code slash commands       │
└───────────────────┬─────────────────────────────┘
                    ▼ reads
┌─────────────────────────────────────────────────┐
│  site/                     GENERATED            │
│    • static HTML + AI exports                   │
│    • gitignored                                 │
│    • owned by llmwiki/build.py                  │
└─────────────────────────────────────────────────┘
```

## The eight build layers (details in `docs/architecture.md`)

| Layer | What lives here | PR surface |
|---|---|---|
| L0 Raw | Converters + adapters | `llmwiki/convert.py`, `llmwiki/adapters/` |
| L1 Wiki | Slash commands + conventions | `CLAUDE.md`, `.claude/commands/`, seed files |
| L2 Site | HTML builder + CSS/JS strings | `llmwiki/build.py`, `llmwiki/viz_*.py` |
| L3 Viewer | Browser-side JS baked into `build.py` | inline JS string inside `build.py` |
| L4 Distribution | Setup scripts, packaging | `setup.sh`, `setup.bat`, `pyproject.toml` |
| L5 Schema | Steering + schemas + reference docs | `docs/`, `AGENTS.md`, `.kiro/` |
| L6 Adapters | Session-store parsers | `llmwiki/adapters/<agent>.py` |
| L7 CI/Ops | Workflows + tests + release automation | `.github/workflows/`, `tests/` |

## What must NEVER land in a PR

- **Real session data** under `raw/sessions/` — always gitignored
- **Machine-specific paths** — no `/Users/<yourname>/...`
- **The maintainer's real username** — CI greps for it
- **New runtime dependencies** — stdlib + `markdown` only. Viewer may
  load from a CDN (highlight.js). Anything else gets rejected.
- **Auth walls** — the tool is localhost-first. No login screens, no
  telemetry, no cloud.
- **`wiki/sources/`, `wiki/entities/`, `wiki/concepts/`, `wiki/syntheses/`
  pages** other than the explicitly allow-listed seed files in
  `.gitignore`. These are LLM-maintained, not hand-written.
- **`.claude/settings.local.json`**, **`.ingestion-state.json`**,
  **`.framework/`**, **`.temp/`**, **`.research/`** — user-local state

## What maintainers CAN accept

Read [`REVIEW_CHECKLIST.md`](REVIEW_CHECKLIST.md) for the full bar.
TL;DR:

- New feature behind a clear issue (link in PR body)
- One concern per PR (don't mix a fix with a feature)
- Conventional-commit prefix in title (`feat:` / `fix:` / `docs:` /
  `chore:` / `test:`)
- Tests added or updated — CI matrix (Python 3.9 + 3.12) must pass
- CHANGELOG.md entry under `## [Unreleased]`
- Works offline — no new network calls from the build or converter

## Decision log pointer

Declined ideas go in [`DECLINED.md`](DECLINED.md). Before proposing
a big refactor, grep DECLINED.md for it first — we may have
considered and rejected it already.
