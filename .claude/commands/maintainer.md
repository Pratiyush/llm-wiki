Meta-skill that loads all llmwiki governance docs and exposes the three maintainer slash commands.

Usage: /maintainer

Run this once at the start of a maintainer session. It loads every
doc in `docs/maintainers/` plus the top-level governance files
(`CONTRIBUTING.md`, `CODE_OF_CONDUCT.md`, `SECURITY.md`) as context,
so every subsequent action in the session has the full bar in mind.

## Workflow

1. **Load the governance scaffold** — read all of these, in order:
   - `CONTRIBUTING.md` (short rules for contributors)
   - `SECURITY.md` (privacy + disclosure process)
   - `CODE_OF_CONDUCT.md` (behavioral standards)
   - `docs/maintainers/README.md` (index of maintainer docs)
   - `docs/maintainers/ARCHITECTURE.md` (layer boundaries + what NOT to add)
   - `docs/maintainers/REVIEW_CHECKLIST.md` (canonical review bar)
   - `docs/maintainers/RELEASE_PROCESS.md` (version bump flow)
   - `docs/maintainers/TRIAGE.md` (label taxonomy + stale policy)
   - `docs/maintainers/ROADMAP.md` (near-term plan)
   - `docs/maintainers/DECLINED.md` (prior rejections)

2. **Check current state** — run these in parallel so you know what
   the queue looks like:
   ```bash
   gh pr list --state open --limit 20
   gh issue list --state open --limit 50
   gh run list --branch master --limit 5
   ```

3. **Report a status summary** — for the user:
   - Number of open PRs + their authors + ages
   - Number of untriaged issues (no `enhancement`/`bug`/`chore` label)
   - Number of open `priority:must` items
   - Master CI status (last 3 runs)
   - Any red CI runs that need attention
   - Any PR stuck > 7 days (escalation triggers per TRIAGE.md)

4. **Offer the three sub-commands** — remind the user that they can:
   - Run `/review-pr <N>` to review a specific PR against the
     canonical checklist
   - Run `/triage-issue <N>` to apply the label taxonomy to an
     untriaged issue
   - Run `/release <version>` to walk the release process for a
     new version bump

5. **Recommend the next action** — based on the status:
   - If there's a stuck PR, recommend `/review-pr`
   - If there's an untriaged issue, recommend `/triage-issue`
   - If the CHANGELOG has a coherent batch of `## [Unreleased]`
     entries and no blockers, recommend `/release`
   - If none of the above, say "queue is clean" and stop.

## Session rules

- **Respect layer boundaries** — any suggestion that crosses layers
  needs a note pointing to `docs/maintainers/ARCHITECTURE.md`
- **Refer to DECLINED.md before proposing refactors** — a surprising
  number of "obvious improvements" have already been considered
- **Always append to the log** — every maintainer action ends with
  an entry in `wiki/log.md` in the format
  `## [YYYY-MM-DD] <op> | <summary>`
- **Never force-push master** — rollback by rolling forward
- **Never commit real session data** — CI greps for the maintainer's
  real username; if that grep fails on a committed file, revert
  immediately

## Example session

```
> /maintainer

Loading governance docs... done (6 docs loaded).

Current state:
- 3 open PRs: #91 (3 days), #92 (1 day), #93 (12 hours)
- 7 untriaged issues
- 2 open priority:must items (#45, #64)
- Master CI: 3/3 green

Recommended next action:
  1. `/review-pr 91` — stuck for 3 days, above the 7-day escalation
     threshold? No, but it's the oldest open PR
  2. `/triage-issue 87` — first of 7 untriaged issues

> /review-pr 91
```
