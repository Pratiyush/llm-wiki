# Issue triage

> **Audience:** maintainers working through the inbox. Run
> `/triage-issue <number>` for a guided pass that applies the rules
> below automatically.

Triage runs at most once a day when the queue is active. The goal is
to give every new issue a label, a milestone, and a priority within
24 hours — not to fully resolve it.

## Label taxonomy

### Type (required, pick one)

- `enhancement` — new feature or expansion of an existing one
- `bug` — something is broken
- `docs` — documentation only
- `chore` — refactor, dep bump, CI, build tooling
- `epic` — top-level umbrella for a batch of sub-items
- `question` — not actionable without a reply
- `wontfix` — closed with a reason; link to DECLINED.md if relevant

### Priority (required, pick one — MoSCoW)

- `priority:must` — v0.1 ships without this → the product fails
- `priority:should` — strong user value but the current release can
  survive without it
- `priority:could` — nice to have; ship when a contributor or issue
  demands it
- `priority:wont` — considered and rejected for scope / philosophy
  reasons; add to DECLINED.md

### Layer (required — see `docs/maintainers/ARCHITECTURE.md`)

- `layer-0` — Raw (converters, adapters)
- `layer-1` — Wiki (LLM-maintained, slash commands, conventions)
- `layer-2` — Site (HTML builder, CSS, JS)
- `layer-3` — Viewer (browser JS, search, shortcuts)
- `layer-4` — Distribution (setup, packaging)
- `layer-5` — Schema (docs, AGENTS.md, steering)
- `layer-6` — Adapters (one per agent)
- `layer-7` — CI/ops (workflows, tests, release)

### Supporting (optional)

- `good first issue` — well-scoped, low-risk, one-file
- `help wanted` — maintainer doesn't have bandwidth; open for anyone
- `blocked` — waiting on external decision or upstream fix
- `stale` — no activity in 90 days; candidate for auto-close
- `adapter` — session-store adapter work
- `ui` — front-end/styling concerns

## Rules

### 1. Every issue gets a type label within 24h

If an issue has no type label, it's untriaged. Run the triage pass.

### 2. No issue without a priority

Even `priority:wont` is better than nothing — it means "we looked,
we declined, go to DECLINED.md for the reason." Contributors
shouldn't wonder whether their idea was read.

### 3. Layer is required for anything actionable

The only exceptions are `question` and `epic`. Even `bug` needs a
layer so the right person picks it up.

### 4. Link to DECLINED.md when closing as `wontfix`

Copy the summary into `docs/maintainers/DECLINED.md` with a date and
a one-sentence rationale. This prevents the same idea being
re-proposed in six months.

### 5. Duplicate detection before triage

Before labeling, search for duplicates:

```bash
gh issue list --search "<keywords from title>" --state all --limit 20
```

If it's a duplicate, close with a comment linking to the original.

## Stale policy

- After **90 days** of no activity → add `stale` label + comment
  asking if the issue is still relevant
- After an additional **30 days** with no reply → close as stale
  (the reporter can reopen anytime)
- Issues labeled `epic`, `priority:must`, or `priority:should` are
  exempt from stale auto-close

## Milestone assignment

- `v0.X.0` milestones hold `priority:must` + `priority:should` items
  targeted for that release
- Milestones move as reality shifts — don't treat them as commitments
- Issues labeled `priority:could` usually stay unmilestoned until a
  contributor picks them up

## Escalation

If an issue involves any of the following, flag it for maintainer
attention immediately (don't wait for the next triage pass):

- Security vulnerability (→ SECURITY.md)
- User data loss (e.g. a bad converter that mangles `raw/` files)
- CI is red and staying red
- A contributor's PR has been waiting > 7 days for review
