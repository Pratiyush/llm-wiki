# llmwiki — Open Source Project Progress

**Project:** llmwiki
**Type:** Developer Tool / Python CLI + Static Site Generator
**Framework:** [[00 - Framework - Open Source]] v4.0
**Started:** 2026-04-08
**Owner:** Pratiyush

## User Preferences (ASK answers)

| Question | Answer |
|---|---|
| Push strategy | Direct to `master` for initial setup; PRs for future changes |
| Default branch | `master` |
| Auto-create repo | Yes (via `gh repo create` — authenticated as Pratiyush) |
| Signed commits | No (for initial commit); set up GPG + branch protection later |
| git user | `Pratiyush` / `pratiyush1@gmail.com` |
| AI co-author lines | **Never** |
| License | MIT |
| Package registry | None initially (pip-installable from git later) |

## Phase Progress

| Phase | Name | Status | Deliverable | Date |
|---|---|---|---|---|
| 0 | Capture | [x] Done | `idea-brief.md` | 2026-04-08 |
| 1 | Validate | [x] Done | Scorecard /25 → **22/25 BUILD** | 2026-04-08 |
| 1.5 | Project Steering | [x] Done | Technical constraints + contribution philosophy | 2026-04-08 |
| 2 | Brand | [x] Done | Name, tagline, README, LICENSE | 2026-04-08 |
| 3 | Structure | [x] Done | Repo layout, file schema | 2026-04-08 |
| 4 | Content | [x] Done | Python package, HTML generator, adapters, scripts | 2026-04-08 |
| 5 | Contribution | [x] Done | CONTRIBUTING.md, CI workflow, issue templates | 2026-04-08 |
| 5.5 | Pre-Launch QA | [/] In progress | Test runs, adversarial review | 2026-04-08 |
| 6 | Launch | [ ] Pending | git push + GitHub release | |
| 7 | Grow | [ ] Pending | Reddit/HN/X/Dev.to posts | |
| 8 | Maintain | [ ] Pending | Monthly verification | |

## Key Decisions

1. **Stdlib-first**: the converter and HTML generator use only Python stdlib + `markdown`. Syntax highlighting uses highlight.js loaded from a CDN at view time. No npm, no database, no daemons.
2. **Adapter pattern**: separate adapters per agent (`claude_code.py`, `codex_cli.py`) so adding a new agent is adding one file.
3. **Follow Karpathy's LLM Wiki spec**: `raw/` → `wiki/` → schema (CLAUDE.md / AGENTS.md).
4. **Click-to-run scripts**: `setup.sh` / `setup.bat` / `build.sh` / etc. — no pre-requisites beyond Python 3.9+.
5. **Framework files only in git**: all user-specific data (`raw/sessions/`, `site-html/`, `.ingestion-state.json`) is `.gitignore`d.
6. **Single source of truth for UI**: `llmwiki/build.py` contains CSS + JS inline so the whole generator is one file.
