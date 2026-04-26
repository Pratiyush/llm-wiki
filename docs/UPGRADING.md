---
title: "Upgrade guide"
type: navigation
docs_shell: true
---

# Upgrade guide

How to upgrade between `llmwiki` releases.  Most releases are drop-in
(`pip install -U llmwiki` or `brew upgrade llmwiki`) — this page
documents the exceptions: schema migrations, config changes, and
behaviour flips that affect what happens on your next `sync`.

The canonical per-release detail is
[CHANGELOG.md](https://github.com/Pratiyush/llm-wiki/blob/master/CHANGELOG.md)
— this guide focuses on "what might break".

## v1.3.0 — consolidated 1.2.x patch roll-up

**Released: 2026-04-26.**

### Summary

Drop-in upgrade from any 1.2.x. v1.3.0 consolidates 38 in-tree
patch versions (1.2.1 → 1.2.38) under one minor release tag — no
breaking API changes, no schema migrations, no config changes.

```bash
pip install -U llm-notebook   # → 1.3.0
llmwiki --version             # → 1.3.0
```

### What's in it

The full per-fix detail is preserved under the [1.2.x] entries in
`CHANGELOG.md`. Two themes:

1. **Opus 4.7 deep code-review backlog (#403, ~26 issues)** — every
   correctness, perf, and observability finding got a one-issue-one-PR
   fix. Headliners: `is_subagent` strict path check (#406),
   `derive_session_slug` UUID-prefix collision (#424), tilde-fence
   counting in `_close_open_fence` (#419), `wiki_query` ranking
   length normalisation (#418), `wiki_search` cap (#413), per-vault
   synth state (#420), `--force` sync persisting `_meta`/`_counters`
   (#426), subprocess `claude_path` resolved via `shutil.which`
   (#421).

2. **Performance + features** — `DuplicateDetection` lint rule
   rewritten with bucket+fingerprint+SequenceMatcher (1s vs minutes
   on 500 pages, #412), perf-budget test suite (`-m slow`, #429),
   `md_to_plain_text` cache (#417), auto-seeded project stubs
   pre-populated from session metadata (#425), 2 new lint rules
   (`frontmatter_count_consistency`, `tools_consistency`, #378),
   `wiki-all` slash command, `_context.md` folder convention (#60).

### Breaking — none

Same CLI surface, same config schema, same on-disk state format.
The only thing that changed is that the next plain `sync` after a
forced re-sync will now correctly identify already-processed files
as unchanged (was: re-processed every time, #426).

### Schema migrations — none

State files written by 1.2.x are read verbatim by 1.3.0.

## v1.2.0 — first stable on the 1.x line

**Released: 2026-04-25.**

### Install changes

- **PyPI distribution name is `llm-notebook`** — the `llmwiki` name was
  taken on PyPI. The Python module + CLI command stay `llmwiki`, only
  the `pip install` line changes:
  ```bash
  pip install llm-notebook        # was: pip install llmwiki
  llmwiki --version               # → 1.2.0  (CLI name unchanged)
  python3 -c "import llmwiki"     # still works (import name unchanged)
  ```

### Removed CLI subcommands

The CLI was slimmed in #362. If you scripted any of these, replace as
noted:

- `llmwiki schedule` — removed. Schedule `llmwiki sync` directly via
  your OS's job runner (launchd / systemd / Task Scheduler).
- `llmwiki install-skills` — removed. Manually copy
  `.claude/commands/wiki-*.md` into `~/.claude/commands/` for global
  availability.
- `llmwiki check-links` — removed. Use the GitHub Actions link-check
  workflow instead.
- `llmwiki watch`, `llmwiki manifest`, `llmwiki link-obsidian`,
  `llmwiki export-obsidian`, `llmwiki export-marp`, `llmwiki export-qmd`,
  `llmwiki eval` — also removed.
- `llmwiki export marp` is the new path for Marp slide export.

### Removed adapters

`jira_adapter`, `meeting`, `pdf` were removed in #363. If you depended
on any of them, pin v1.1.0-rc8 until you migrate.

### Demo data correctness

`user_messages` / `tool_calls` counts on the 8 demo session files were
2–10× higher than the body actually contained. The values are now
recomputed from body content. Two new lint rules (`#16
frontmatter_count_consistency`, `#17 tools_consistency`) prevent
regression.

### `sync --force` no longer drops colliding sessions

If you ran `sync --force` against a corpus where two sources had the
same canonical filename (rare but real on large corpora), one of them
was silently overwritten. Fix: per-run filename tracking now
disambiguates regardless of `--force`. Affected ~200 of 495 sessions
on a real corpus we tested.

### New: `llmwiki all`

One-shot pipeline runner for CI:

```bash
llmwiki all                  # build → graph → export → lint
llmwiki all --strict         # exit 2 on any lint warning
```

### Schema migrations

None. JSON sibling files now correctly emit `int` and `bool` types for
`user_messages` / `tool_calls` / `is_subagent` (were strings); any
downstream that string-compared `is_subagent == "false"` now needs
`is_subagent is False`.

## v1.1.0-rc5

**Released: 2026-04-21.**

### New behaviour

- **Session transcripts strip project-local file refs.** Anchors
  pointing at `tasks.md`, `user_profile.md`, `settings.gradle.kts`,
  `.kiro/…`, `/Users/…`, etc. are unwrapped into inline
  `<span class="session-ref dead-link">` — the filename stays visible
  but the anchor doesn't 404. No action required.

- **`README.md` and `CONTRIBUTING.md` now compile as site pages.**
  `site/README.html` and `site/CONTRIBUTING.html` ship alongside
  `changelog.html`. Link rewriter routes to the compiled page instead
  of GitHub for these two files.

- **`/wiki-synthesize` slash command** — wraps `llmwiki synthesize`
  with natural-language flags ("estimate cost", "dry run", "force").
  Copy `.claude/commands/wiki-synthesize.md` into `~/.claude/commands/`
  for global availability. (`llmwiki install-skills` was removed in
  v1.2.0; manual copy is the supported path.)

- **Dual-mode docs landing pages.** `docs/modes/api/` and
  `docs/modes/agent/` exist as skeletons; the actual API / Agent
  backends ship with #315 / #316.

### Schema migrations

None. Fully backwards-compatible with rc4 state files.

### Breaking

None.

## v1.1.0-rc4

**Released: 2026-04-20.**

### New behaviour

- **Obsidian is opt-in now.** Past versions fired the Obsidian adapter
  on every `sync` by default. If your workflow relied on that, add
  this to `sessions_config.json`:

  ```json
  { "obsidian": { "enabled": true } }
  ```

  Context: [#326](https://github.com/Pratiyush/llm-wiki/issues/326).
  Runs as of rc3; surfaced in `llmwiki adapters` column `will_fire`.

- **Graph clicks respect compiled-site existence.** Nodes whose
  corresponding page wasn't rendered to HTML show a tooltip instead
  of opening a 404. No action needed — if you see the tooltip on
  entity / concept / nav pages that's the new design.

- **Backlinks now propagate.** Run `llmwiki backlinks` once to inject
  managed `## Referenced by` sections into every linked-to page.
  Idempotent, dry-runnable, prune-able:

  ```bash
  llmwiki backlinks --dry-run --verbose   # preview
  llmwiki backlinks                       # commit writes
  llmwiki backlinks --prune               # strip every block
  ```

### Schema migrations

- `.llmwiki-state.json` keys rewrite from absolute paths to
  `<adapter>::<home-relative-path>` on first load under rc3+. Migration
  is automatic and idempotent. If you moved your repo to a new machine,
  old state will be preserved verbatim — re-sync to reindex.

- `.llmwiki-quarantine.json` is a new local file (gitignored). First
  appears when a convert error happens. Inspect with
  `llmwiki quarantine list`.

- Frontmatter `tags:` / `topics:` convention is lint-enforced (rule
  #14 `tags_topics_convention`) — projects use `topics:`, everything
  else uses `tags:`. Run `llmwiki tag convention` to see violations.
  `llmwiki tag rename <old> <new>` rewrites across every page.

### Breaking — none

No breaking CLI or config changes. Every test pre-upgrade keeps
passing post-upgrade.

## v1.1.0-rc3

See the [release notes](https://github.com/Pratiyush/llm-wiki/releases/tag/v1.1.0-rc3)
for the full rc3 gap-sweep bundle. No migration required.

## v1.0.0 → v1.1.0-rc1

Config: `synthesis.backend` now accepts `"ollama"` in addition to the
default `"dummy"`. See `docs/reference/prompt-caching.md` for the
ollama setup.

`wiki/candidates/` directory is new — created automatically by ingest
when it sees a brand-new entity/concept. Triage with `/wiki-candidates`
(renamed from `/wiki-review` in rc3).

## Older versions

Pre-v1.0 milestones shipped under internal sprint tags. Upgrade from
v0.9.x to v1.0.0 in one step — no intermediate migration required. If
you're on a pre-0.9 build, start fresh: `llmwiki init` in a new tree
and re-run `sync`.
