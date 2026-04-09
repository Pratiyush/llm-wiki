# Maintainer guide

This directory is the governance scaffold for llmwiki maintainers.
Contributors should read [`../../CONTRIBUTING.md`](../../CONTRIBUTING.md)
first — it has the short version of what this folder covers in detail.

## Docs at a glance

| File | What it's for |
|---|---|
| [`ARCHITECTURE.md`](ARCHITECTURE.md) | One-page system diagram + layer boundaries + what NOT to add |
| [`REVIEW_CHECKLIST.md`](REVIEW_CHECKLIST.md) | Canonical code-review criteria — apply to every incoming PR |
| [`RELEASE_PROCESS.md`](RELEASE_PROCESS.md) | Version bump → CHANGELOG → tag → build → publish checklist |
| [`TRIAGE.md`](TRIAGE.md) | Label taxonomy + triage rules + stale-issue policy |
| [`ROADMAP.md`](ROADMAP.md) | Living near-term plan + release theme table |
| [`DECLINED.md`](DECLINED.md) | Graveyard of declined ideas with dates + reasons |

## Slash commands

Four Claude Code slash commands automate the common maintainer ops.
Each command loads the relevant governance doc as context and runs a
guided pass:

- `/review-pr <pr-number-or-url>` — applies `REVIEW_CHECKLIST.md`
  and posts findings inline
- `/triage-issue <issue-number>` — applies `TRIAGE.md` label
  taxonomy to a new issue
- `/release <version>` — walks `RELEASE_PROCESS.md` step by step
- `/maintainer` — meta-skill that loads every doc in this folder
  and makes the other three commands available

See `.claude/commands/` in the repo root for the source of each
command.

## When things go wrong

- **CI red on master** → see `ROADMAP.md` "Stability pass" section
  for the contract. Fix-first, roll forward, never force-push
- **Security issue reported** → see `SECURITY.md` in the repo root
- **Contributor PR stuck > 7 days** → escalate via the triage pass
  (there's a rule in `TRIAGE.md`)
- **Someone re-proposes a declined idea** → link them to the
  entry in `DECLINED.md`

## Why a dedicated maintainer folder?

Because maintainer docs have a different audience than user docs.
User docs go in `docs/` (rendered on the site). Maintainer docs
stay here — they're less polished, more operational, and they
change with the team rather than with releases.

Keep this folder short. When a doc is over one screen, prune.
