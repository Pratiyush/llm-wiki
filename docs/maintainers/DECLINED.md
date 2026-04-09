# Declined ideas

> **Audience:** maintainers and contributors about to re-propose
> something. Check this file before filing an issue — we may have
> already considered and rejected your idea, and the reason is here.

The project has a scope. Not every cool idea fits. This file is the
graveyard where declined ideas rest, with a date and a one-sentence
rationale. If you disagree with a decline, open a new issue and link
to the entry — explain what's changed since the rejection.

## Format

```markdown
## <Date> — <Title>

**Reason:** one-sentence rationale.

**Context (optional):** link to the issue, PR, or discussion. Any
nuance about *when* this might be reconsidered.
```

---

## 2026-04-09 — N-way comparisons on vs-comparison pages

**Reason:** 2-way side-by-side comparisons (#58) are a clean,
queryable format. N-way comparisons degenerate into an info table
with N columns, which loses the "at-a-glance diff" that makes the
2-way format useful. Users who want N-way can run N-choose-2 pair
navigation from the index.

**Context:** #58 non-goal. Reconsider if a genuine user request
demands it.

## 2026-04-09 — Automatic benchmark scraping from provider websites

**Reason:** Scraping is fragile, violates most providers' ToS, and
creates a hidden data pipeline that can silently break. Users add
benchmarks manually for v1. Structured community contributions are
welcome via PR.

**Context:** #55 non-goal. Reconsider if a provider ships an
official machine-readable benchmark API.

## 2026-04-09 — USD cost estimates in token usage cards

**Reason:** Requires a pricing table that's correct at the moment
of rendering, which means either an external API call (bad —
kills offline mode) or a stale hardcoded table (bad — wrong
numbers are worse than no numbers). Will revisit after the v0.7
structured model schema (#55) landed, so cost can be computed
from the same pricing block users already maintain.

**Context:** #66 non-goal. #55 shipped; revisit in v0.10.

## 2026-04-09 — Rollback for append-only changelog entries

**Reason:** Append-only by design. If an entry is wrong, add a
correcting entry rather than deleting the original — preserves the
audit trail. Same rule as the wiki log.

**Context:** #56 non-goal.

## 2026-04-09 — Per-turn tool timelines

**Reason:** Would need turn-level structured data in every session
frontmatter (beyond the per-session aggregates in #63), which is a
5× larger converter output and bloats the search index. The
per-session bar chart from #65 covers the 90% use case.

**Context:** #65 non-goal. Reconsider if users start asking for it.

## 2026-04-09 — Success/failure counts per tool

**Reason:** The raw JSONL has `toolUseResult.isError` on every tool
result block, but wiring it through the converter aggregates
doubles the state-machine complexity. Defer until users ask.

**Context:** #65 non-goal.

## 2026-04-09 — Replicating qmd's hybrid search inside llmwiki

**Reason:** qmd already does hybrid BM25 + vector + LLM rerank.
llmwiki's built-in search is a deliberate "works offline, zero
deps, client-side fuzzy" design. Users who need hybrid search run
`llmwiki export-qmd` and point qmd at the output. Two tools, one
source of truth, no competing stacks.

**Context:** #59 non-goal. Reconsider only if qmd becomes
unmaintained.

## 2026-04-09 — Shipping qmd as a dependency

**Reason:** qmd is TypeScript/Node. llmwiki is stdlib Python plus
`markdown`. Adding a Node runtime as a dep would destroy the
"works on any 3.9+ Python, no other dependencies" promise.

**Context:** #59 non-goal.

## 2026-04-09 — Forcing users to create `_context.md` files

**Reason:** Folder-level context files are an optional navigation
hint. Making them mandatory turns them into busywork for sparse
folders and obscures their value for large ones. The `/wiki-lint`
warning (#60) nags at >10-file folders without a stub, which is
enough social pressure without blocking a build.

**Context:** #60 non-goal.

## 2026-04-09 — Auto-generating `_context.md` via LLM on sync

**Reason:** The whole point of `_context.md` is a human (or LLM
during `/wiki-query`) having a stable, reviewable description of
the folder's purpose. Auto-generating it on sync would make the
file drift every time the converter runs, which defeats the
caching benefit. A separate `/wiki-write-contexts` slash command
that takes user approval is acceptable — just not in the sync
pipeline.

**Context:** #60 follow-up, not a non-goal.

## 2026-04-09 — SEO schema.org markup on vs-comparison pages

**Reason:** Every session and model page already ships `Article`
microdata (v0.4). Vs-comparison pages are aggregations, not
articles — schema.org doesn't have a clean "comparison" type.
Adding half-correct schema is worse than no schema.

**Context:** #58 non-goal. Follow up if Google adds a comparison
type.

## 2026-04-09 — CLAs or DCO sign-off for contributions

**Reason:** llmwiki is MIT. The added bureaucracy deters small
PRs and buys nothing the license doesn't already cover.

**Context:** #62 non-goal.

## 2026-04-09 — Enforcing governance retroactively on old issues

**Reason:** Issues #1–#61 were filed before the governance scaffold
existed. Re-triaging them would churn for no user benefit. New
rules apply to new issues.

**Context:** #62 non-goal.

## 2026-04-09 — Bots for automated triage

**Reason:** Manual triage via `/triage-issue <number>` is enough
for the current queue size (<60 open issues). Automated bots
create labeling noise and false positives. Revisit if the queue
grows past 300.

**Context:** #62 non-goal.

---

*Want to propose something that's on this list? File an issue with
a link to the entry and explain what's changed since the rejection.
Maintainers read proposals with an open mind, but "the idea is
cool" isn't a new argument.*
