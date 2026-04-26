# Changelog

All notable changes to **llmwiki** will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

Versions below 1.0 are pre-production — API and file formats may change.

## [Unreleased]

## [1.3.9] — 2026-04-26

Hotfix release fixing Windows lint exemptions broken by POSIX-only path splitting (#490).

### Fixed

- **Lint exemptions broke on Windows backslash paths** (#490) — `lint/rules.py:FrontmatterCompleteness`, `_page_slug`, and `IndexSync` all derived basenames via `rel.rsplit('/', 1)[-1]`. On Windows the page-key paths use native `\\` separators (from `Path.parts`), so the split produced the *whole* string, every navigation file (`wiki\\index.md`, `wiki\\overview.md`, etc.) failed exemption matching, and every Windows install lit up with spurious lint errors. Fix: new `_basename(rel)` helper that normalises both separators before splitting; all 3 sites route through it. Adds `tests/test_lint_windows_paths.py` (5 cases) covering the helper directly + each fixed callsite, with parametrised POSIX vs Windows path inputs.

## [1.3.8] — 2026-04-26

Hotfix release fixing the auto-detected `real_username` falsely matching `root` / short paths in containers and Windows (#489).

### Fixed

- **Auto-detected `real_username` over-matched on Windows + stripped containers** (#489) — `convert.py:load_config` previously fell back to `os.environ["USER"] or Path.home().name`. Two failure modes hit users in the wild: (a) **Windows** uses `USERNAME` not `USER` → env lookup empty → fallback to `Path.home().name` returns the actual short name, which the redactor then substring-matched into unrelated path tokens; (b) **stripped Docker / CI images** have `USER` unset and `Path.home()` = `/root` → fallback returns `"root"` → every `/Users/root/`, `/home/root/` path got mass-rewritten to `/Users/USER/` even when the actual transcript author had a totally different username. Fix: prefer `USER` → `USERNAME` → `Path.home().name`, but only trust the home-dir name when it's ≥3 chars AND not in the generic-container set (`root`, `user`, `users`, `home`, `ubuntu`). Otherwise leave the field empty so the redactor stays a no-op until the user opts in via config. Adds `tests/test_username_autodetect.py` (8 cases) covering Unix USER, Windows USERNAME, generic-container blocklist, short-name floor, explicit config wins, all-empty graceful fallback, and a regression vs the bug pattern.

## [1.3.7] — 2026-04-26

Hotfix release routing `parse_jsonl` I/O errors through the quarantine instead of silently swallowing them (#487).

### Fixed

- **`parse_jsonl` swallowed OSError silently** (#487) — `convert.py:parse_jsonl` previously had a top-level `try: … except OSError: pass` returning an empty list. A permission error or read failure on a single jsonl produced zero records → downstream `convert_all` classified the file as 'filtered' (legitimate empty session) instead of 'errored' (something wrong, look at it). The file became invisible to `llmwiki sync --status` and the quarantine. Fix: `parse_jsonl` now re-raises OSError; `convert_all` wraps the call in `try/except OSError` that routes the failure through `_quarantine_add` + the 'errored' counter, matching every other I/O write path. Per-line `json.JSONDecodeError` is still skipped (JSONL allows partial writes; one bad line shouldn't abandon the whole file). Adds `tests/test_parse_jsonl_oserror.py` (5 cases) covering the OSError re-raise, JSONDecodeError still tolerated, partial line tolerance, file-level fail bubbles up, and an end-to-end `convert_all` integration check that a permission-denied file appears in the quarantine + 'errored' counter.

## [1.3.6] — 2026-04-26

Hotfix release closing the renderer-side half of the `is_subagent` regression that #406 fixed at the adapter level (#492). Sub-agent classification was correct in the frontmatter but wrong in the rendered UI for any project with "subagent" in a session filename.

### Fixed

- **Renderer used the broken substring rule across 5 sites** (#492) — PR #406 fixed `is_subagent` at the adapter layer (strict canonical-path check, writes correct `is_subagent: true|false` into frontmatter). But `build.py` never read the frontmatter field; it re-implemented the old `'subagent' in p.name` substring check in 5 separate places (`render_project_page`, `render_projects_index`, `render_index`, project-card stats, JSON schema emit). Result: any session in any project with "subagent" in its filename was demoted from main-session counts in the UI even though the adapter classified it correctly. Fix: new `_is_subagent(meta, path)` helper that prefers the frontmatter field (`true`/`false` bool, plus `"true"/"false"` string coerce for legacy parsers), falls back to the substring check only when the field is missing (pre-#406 raw files). All 5 sites now route through the helper. Adds `tests/test_render_is_subagent.py` (8 cases) covering the frontmatter precedence, all 6 string-bool variants, the substring fallback for missing field, and a regression vs the bug pattern (project named `subagent-runner` whose sessions were misclassified).

## [1.3.5] — 2026-04-26

Hotfix release scrubbing stale references to `llmwiki watch` and `llmwiki export-obsidian` from the README + docs (#494). Both subcommands were removed in v1.2.0 (see UPGRADING.md) but the README CLI table + 2 docs still advertised them, breaking new-user trust on first try.

### Removed (docs only)

- **README CLI table** dropped the `llmwiki watch` + `llmwiki export-obsidian` rows
- **`docs/multi-agent-setup.md`** replaced "Use `llmwiki watch`" with the documented `launchd`/`systemd`/Task Scheduler path
- **`docs/modes/api/index.md`** same replacement
- **`llmwiki/watch.py`** docstring updated to reflect that the CLI subcommand is gone; the helper functions (`scan_mtimes`, `run_sync`) survive as a small library so `tests/test_v02.py` keeps working

Adds `tests/test_cli_doc_parity.py` (1 case) — a CI guard that asserts every `llmwiki <subcommand>` line in the README CLI table corresponds to an actual subparser in `cli.py:build_parser()`. Future stale entries fail CI before they reach a release.

## [1.3.4] — 2026-04-26

Hotfix release renaming `llmwiki/queue.py` → `llmwiki/ingest_queue.py` to stop shadowing the Python stdlib `queue` module (#491).

### Changed

- **Renamed `llmwiki.queue` → `llmwiki.ingest_queue`** (#491) — naming a module `queue.py` shadows Python's stdlib `queue`, breaking any future code inside `llmwiki/` that wants `queue.Queue` for thread-safe primitives. Pylint/ruff also flag this anti-pattern. Renamed the module to `ingest_queue` (matches the actual purpose — pending-source ingest queue, not a generic queue). Old `llmwiki/queue.py` becomes a back-compat shim that re-exports the public API and emits a `DeprecationWarning` so any third-party code keeps working through one minor cycle. Will be removed in v1.5. Adds `tests/test_ingest_queue_shim.py` (3 cases) covering the rename, the shim's deprecation warning, and the stdlib `queue` import inside `llmwiki/` working correctly.

## [1.3.3] — 2026-04-26

Hotfix release fixing yellow chip contrast failure flagged by the Opus UI/UX audit (#480).

### Fixed

- **`.fresh-yellow` and `.token-ratio-value.tier-yellow` failed WCAG AA contrast** (#480) — light-mode chips used `color: #b45309` on `background: #fef3c7` = **4.49:1 contrast ratio**. Fails AA (4.5:1) for the rendered 0.72rem text. Bumped to `#92400e` (5.85:1). Dark-mode variants (`#fcd34d` on `#3a2a06`) already pass and are unchanged. Adds `tests/test_chip_contrast.py` (4 cases) computing the ratio against a hand-coded W3C luminance formula.

## [1.3.2] — 2026-04-26

Hotfix release adding `viewport-fit=cover` so iOS Safari exposes safe-area insets, fixing the mobile bottom nav overlap with the iPhone home indicator (#481).

### Fixed

- **Mobile bottom nav `env(safe-area-inset-bottom)` returned 0 on iOS** (#481) — `render/css.py:673` mobile bottom nav padded with `calc(6px + env(safe-area-inset-bottom, 0px))` to clear the iPhone home indicator. But the `<meta name="viewport">` in `build.py:622, 659` was missing `viewport-fit=cover`, so Safari iOS reported the inset as 0. The bottom nav rendered flush against the home indicator, and the system swipe-up gesture intercepted taps on the rightmost Theme + Search buttons. Fix: add `viewport-fit=cover` to both `page_head` and `page_head_article` viewport meta tags. Adds `tests/test_viewport_meta.py` (3 cases) asserting both meta tags carry the directive.

## [1.3.1] — 2026-04-26

Hotfix release fixing the localStorage theme key mismatch between site and graph (#477). One-line correctness fix; graph page now correctly inherits the user's site theme on every visit.

### Fixed

- **Graph page used `localStorage["theme"]`, rest of site used `localStorage["llmwiki-theme"]`** (#477) — the graph viewer never inherited the user's site theme. Toggling theme on the graph also had no effect anywhere else. Compounded by `<html data-theme="dark">` hardcoded in the graph template, so light-mode users always saw a dark graph regardless of preference. Fix: standardise on `llmwiki-theme` in graph.py (read + write); drop the hardcoded `data-theme` attribute and replace with a pre-paint inline script that reads localStorage (then `prefers-color-scheme` fallback, then dark) before first paint to avoid a flash of wrong theme. Adds `tests/test_graph_theme_sync.py` (4 cases) covering both keys removed/standardised, pre-paint script present, and template structure.

## [1.3.0] — 2026-04-26

Consolidated minor release rolling up every patch since v1.2.0 — 38 in-tree version bumps across the Opus 4.7 deep code-review backlog (#403), perf budgets, observability, and a handful of new features. No breaking API changes; all of v1.2.x is byte-identical with v1.3.0 at the code level. Per-fix detail is preserved under the [1.2.x] entries below for grep-ability.

### Highlights

**Code review (#403, ~26 issues, all closed)** — every finding from the Opus 4.7 deep review of llmwiki/build.py, convert.py, MCP server, lint rules, and adapters got its own one-issue-one-PR fix with edge-case + e2e test checklists. Headliners:

- `is_subagent` heuristic stopped mis-classifying any project whose name contains "subagent" (#406)
- `derive_session_slug` UUID-prefix collision fixed — two distinct UUIDs in the same project no longer collapse to the same canonical filename (#424)
- `_close_open_fence` now counts both `\`\`\`` and `~~~` fences independently — Quarto-style transcripts no longer leak past the truncation point (#419)
- `wiki_query` MCP ranking gained log-length normalisation — 1MB log pages no longer dominate over relevant 1-paragraph entity pages (#418)
- `wiki_search` MCP cap (`_SEARCH_HIT_CAP`) prevents pathological-query response blow-ups (#413)
- Synth-pipeline state file now per-vault — multi-vault overlays no longer cross-contaminate idempotency state (#420)
- `--force` sync now persists `_meta` / `_counters` / per-key state — `sync --status` audit trail no longer silently lost across forced re-syncs (#426)
- Subprocess `claude_path` resolution moved to `shutil.which("claude")` with shell-metacharacter rejection — works on every platform, not just brew installs (#421)

**Performance**

- `DuplicateDetection` lint rule rewritten with bucket+fingerprint+SequenceMatcher — 500-page corpus now lints in <1s instead of minutes (#412)
- New perf-budget test suite (`tests/test_lint_perf.py`, opt-in via `-m slow`) pins wall-clock budgets per rule (#429)
- `md_to_html` cache key + new `md_to_plain_text` cache (#417)
- `cmd_all` builds the argparse tree once instead of per-step (#422)

**Features**

- `wiki-all` slash command to invoke the full `sync → synth → build → lint` chain
- Auto-seeded project stubs (`wiki/projects/<slug>.md`) now pre-populated with `topics:` from session tags/tools and `description:` from the latest session — fresh projects light up the moment the first session lands (#387 · #425)
- 2 new lint rules: `frontmatter_count_consistency` + `tools_consistency` (#378)
- New `_context.md` folder convention for cheaper deep queries (#60)

**Quality + observability**

- 23 new test files added across the v1.2.x cycle (`test_force_counters.py`, `test_subprocess_paths.py`, `test_slug_fallback.py`, `test_cmd_all_parser.py`, `test_mcp_safety.py`, `test_vault.py`, `test_lint_perf.py`, `test_path_traversal.py`, `test_is_subagent.py`, …)
- Unified frontmatter parser with BOM strip + CRLF support (#409 · #423)
- Strict `is_subagent` checks across every adapter (#406)
- `sync --force` now refuses silent overwrites; failures land in `.llmwiki-quarantine.json` (#326)
- Demo-data fidelity audit + `wiki-all` command (#378)

### Detailed changelog
The 1.2.x entries below document each incremental fix in full. Future minor releases will follow the same pattern: ship patches under `1.x.y` as we go, then consolidate under a clean `1.x+1.0` cut.

## [1.2.38] — 2026-04-26

Patch release fixing the `--force` sync silently discarding observability metadata + per-key state flagged by the Opus 4.7 code review (#403). Pure correctness fix — default behaviour unchanged; users who run `sync --force` no longer lose their `last_sync` audit trail or get every file re-processed on the next plain sync.

### Fixed

- **`sync --force` discarded `_meta` / `_counters` / per-key state** (#426) — `convert.py:convert_all`'s state-write block was guarded by `if not dry_run and not force`. With `--force`, every per-key `state[key] = mtime` update made during the loop *and* the observability snapshot (`_meta.last_sync`, `_counters`) were thrown away. Two user-visible consequences: (a) `llmwiki sync --status` after a `sync --force` showed the *previous* run's `last_sync` timestamp, silently losing the audit trail; (b) the next plain `sync` re-processed every file from scratch because no state was recorded for the just-completed forced run, defeating the idempotency guarantee. Fix: lift the `not force` half of the guard. `--force` is meant to ignore *prior* state on read (re-process even unchanged files), not to skip recording the *new* run on write. Sister fix at the dry-run print path: mirror the existing defensive `is_relative_to(REPO_ROOT)` check from the verbatim-text branch so dry-run on out-of-repo `out_dir` (vault overlays, test fixtures) doesn't crash on `relative_to`. Adds `tests/test_force_counters.py` (12 cases) covering default writes meta/counters/per-key, `--force` writes meta/counters/per-key (the regression), `--force` followed by plain sync correctly identifies unchanged, dry-run never writes (with or without `--force`), corrupt state file recovers cleanly, first-ever sync populates from scratch, all 7 counter buckets present, and prior `_meta` overwritten not appended.

## [1.2.37] — 2026-04-26

Patch release pre-populating auto-seeded project stubs with topics + description from session metadata (#425). Fresh projects now light up the moment their first session lands; the user only needs to fill in `homepage:` to get the full hero rendering. Hand-authored stubs are still never overwritten.

### Fixed

- **Auto-seeded project stubs started with empty defaults** (#425) — `build.py:ensure_project_stubs` wrote `topics: []`, `description: ""`, `homepage: ""` even when session metadata could populate the first two for free. Real corpora rendered a bare hero per project until a human intervened. Fix: `_derive_stub_topics()` aggregates session `tags:` (via the existing `extract_session_topics` noise filter) and falls back to `tools_used` so projects without distinctive tags still surface meaningful chips, capped at 6. `_derive_stub_description()` walks the most-recent session first, preferring `summary:` (truncated to ~140 chars with a "..." tail), then a humanised slug (`my-cool-project` → `My Cool Project`), then empty. Embedded double-quotes are escaped so YAML stays valid. Existing files remain untouched — only the absence of a stub triggers a write. Adds 13 new tests to `tests/test_project_stubs.py` covering humanise edge cases, tag pre-population, noise filter, tools-used fallback, 6-topic cap, summary > slug > empty preference, truncation, quote escaping, homepage preserved empty, hand-authored stub preserved, and round-trip via `load_project_profile`.

## [1.2.36] — 2026-04-26

Patch release fixing the `derive_session_slug` UUID-prefix collision flagged by the Opus 4.7 code review (#403). Pure correctness fix — non-UUID filenames behave identically.

### Fixed

- **`derive_session_slug` 12-char filename fallback collided per-project on UUID stems** (#424) — when no `slug` field was present in any record, the fallback was `jsonl_path.stem[:12]`. Claude Code emits UUID-named transcripts (`b7f0e3c4-2189-4f8e-9e4f-...jsonl`); two distinct UUIDs in the same project + same minute both collapsed to `b7f0e3c4-21` (the same 12-char prefix), so the canonical filename collided and we leaned on the disambig pass (#339) to save us. Correctness was coupled to the disambig pass — if the renderer ever moved first, this regressed silently. Fix: detect UUID-shaped stems with `_UUID_LIKE` regex and fall back to the same stable 8-char source-path hash that disambig already uses (`_source_hash8`). Two distinct UUIDs always produce distinct hashes, so the canonical slug is unique without leaning on disambig. Non-UUID stems keep the historical 12-char prefix to preserve human-readable slugs. Adds `tests/test_slug_fallback.py` (14 cases) covering explicit slug field, multiple records, normal stem prefix, UUID hash fallback, two-UUID distinct slugs, uppercase UUIDs, UUID with extra suffix, short stems, special chars, partial-UUID stems (NOT detected as UUID), record-slug-takes-precedence, end-to-end no-disambig-needed via `flat_output_name`, and hash stability across calls.

## [1.2.35] — 2026-04-26

Patch release fixing `cmd_all` rebuilding the argparse tree once per step flagged by the Opus 4.7 code review (#403). Pure perf + decoupling fix — same external behaviour, just one parser construction per `llmwiki all` instead of four.

### Fixed

- **`cmd_all` re-parses argv per step** (#422) — the orchestrator called `build_parser()` inside the per-step loop, rebuilding the entire argparse tree 4× per `llmwiki all` invocation. Apart from being wasteful, every subcommand's flag set leaked into the cmd_all contract via the shared parser — exactly the coupling cmd_all was supposed to avoid. Fix: lift the `build_parser()` call out of the loop so the parser is built once and re-used. Adds `tests/test_cmd_all_parser.py` (10 cases) covering the parser-build-once invariant, default exit code, fail-fast vs no-fail-fast propagation, --skip-graph behaviour, --strict propagation to lint argv, --out and --search-mode round-trips through to the build step, and the full `build → graph → export → lint` ordering.

## [1.2.34] — 2026-04-26

Patch release tightening the claude-CLI subprocess hygiene flagged by the Opus 4.7 code review (#403). No functional change for users with claude on PATH; users who relied on the hardcoded `/usr/local/bin/claude` fallback now get `shutil.which("claude")` instead, which works on Linux package installs, NixOS, Windows, brew, asdf, nvm, and pyenv.

### Fixed

- **Subprocess `claude_path` hardcoded to `/usr/local/bin/claude`** (#421) — `build.py:synthesize_overview` defaulted the path to a fixed string, accepted any `--claude` value, and shelled out without sanitisation. Two hygiene gaps: (a) the default doesn't exist outside macOS-with-brew installs, so users on every other platform had to pass `--claude` explicitly even though `shutil.which("claude")` would Just Work; (b) accepting arbitrary `--claude` values isn't a security boundary today (argv is list-form, never shell-interpreted), but the same path ends up in user-facing logs and could leak into future code paths that *do* interpolate. Fix: new `_resolve_claude_path()` helper. Empty value → falls back to `shutil.which("claude")`. Explicit value → checked for shell metacharacters (`;`, `&`, `|`, `$`, backtick, `<`, `>`, newline) and rejected loudly when present. The CLI default changes from `/usr/local/bin/claude` to `""` so the resolver always wins. Adds `tests/test_subprocess_paths.py` (18 cases) covering PATH lookup, all 7 metacharacter classes, valid Unix/Windows/spaces paths, the synthesize_overview wrapper, and the CLI default round-trip.

## [1.2.33] — 2026-04-26

Patch release fixing the `is_subagent` mis-classification flagged by the Opus 4.7 code review (#403). Pure correctness fix — no API change.

### Fixed

- **`is_subagent` heuristic mis-tagged top-level sessions whose path contains 'subagent'** (#406) — `BaseAdapter.is_subagent` returned True for any path with `"subagent"` in any segment. Combined with the renderer renaming the slug to `<slug>-subagent-<id>`, every session in any user project named e.g. `subagent-runner` was demoted to sub-agent on the project page and excluded from main-session counts. Fix: `BaseAdapter.is_subagent` now returns False (no adapter has the concept by default); `ClaudeCodeAdapter` overrides with a strict canonical-path check (parent directory must be literally named `subagents` AND filename must start with `agent-`). Same conservative fix applied to `CodexCliAdapter`. Adds `tests/test_is_subagent.py` (18 cases including a cross-product matrix of project-name × path × adapter) closing test-gap #430.

## [1.2.32] — 2026-04-26

Patch release fixing the `DuplicateDetection` lint rule's O(n²) blowup flagged by the Opus 4.7 code review (#403). Pure perf fix — no API change. The rule produces the same warnings as before; it just no longer takes minutes on a 500-page corpus.

### Fixed

- **`DuplicateDetection` O(n²) on large wikis** (#412) — `lint/rules.py:DuplicateDetection.run` did a full pairwise scan with `SequenceMatcher` over every page (~500² ≈ 250k comparisons on a real wiki). The `_same_bucket` filter ran *inside* the loop, so cross-bucket pairs paid the iteration cost even though they could never match. Combined with `SequenceMatcher` being instantiated fresh per pair (cold junk-heuristic cache), lint became the slowest stage of `llmwiki all`. Fix: bucket pages first by `(type, project)`, fingerprint bodies (whitespace-normalised md5 of first 4 KB), and only run `SequenceMatcher` for pairs whose fingerprints collide *or* whose titles already match. Same-fingerprint pairs flag immediately (body 1.00). Closes #412.

### Added

- **Perf-budget tests for lint rules** (#429) — new `tests/test_lint_perf.py` synthesises a 500-page corpus and pins wall-clock budgets per rule (`DuplicateDetection` < 1 s, `LinkIntegrity` < 500 ms, `OrphanDetection` < 200 ms, full pass < 3 s). Marked `@pytest.mark.slow` so default `pytest` skips them; CI runs them on a separate job. Includes correctness regression tests for the perf rewrite (identical pages still flagged, CRLF vs LF still flagged via whitespace-normalised fingerprint, same-title-different-body still not flagged) plus scaling guards (5× pages → < 40× wall-clock; shared-prefix worst case under 2 s; no leak across 5 sequential runs). Closes #429.

## [1.2.31] — 2026-04-26

Patch release fixing the synth-pipeline state-file collision across vault overlays flagged by the Opus 4.7 code review (#403). Pure correctness fix — single-vault and no-vault users see no behaviour change; multi-vault users no longer have one vault's run mark another vault's files unchanged.

### Fixed

- **Synth pipeline state file collided across vault overlays** (#420) — `synth/pipeline.py:STATE_FILE` was hardcoded to `REPO_ROOT / ".llmwiki-synth-state.json"`. Vault-overlay mode (`--vault`) plumbed the new root through `convert_all` but `synthesize_new_sessions` still wrote to the *repo* state file. Two vaults synthesised against the same repo silently shared idempotency state; running synth on vault B marked vault A's already-processed files as unchanged on the next run, leaving vault A drifting silently. Fix: `synthesize_new_sessions(state_file=...)` now accepts an explicit state path; `_load_state` and `_save_state` route through a new `_resolve_state_file` helper. The `synthesize` CLI subcommand exposes `--vault PATH` mirroring `build` and `sync` — when set, state lives at `<vault>/.llmwiki-synth-state.json`. Default no-vault behaviour unchanged.

### Added

- **11 new tests** (`tests/test_vault.py`) covering default vs vault state-file paths, load/save round-trip with explicit path, end-to-end isolation between two vaults, corrupted-file fallback to empty state, missing-file fallback, unicode + spaces in vault paths, the new CLI flag round-trip, default `args.vault is None`, and `cmd_synthesize` exit-2 on non-existent vault path.

## [1.2.30] — 2026-04-26

Patch release fixing the tilde-fence blind spot in truncate-time fence balancing flagged by the Opus 4.7 code review (#403). Pure correctness fix — markdown allows both ` ``` ` and `~~~` fence styles, and Quarto-flavoured docs use the latter.

### Fixed

- **`_close_open_fence` only counted backtick fences** (#419) — `convert.py:_close_open_fence` summed lines starting with `\`\`\`` and ignored `~~~` entirely. Truncated tool results that opened a tilde fence (Quarto, some pretty-printers) left the rest of the page consumed by the build's `fenced_code` extension. Fix: count both fence styles independently and append the matching close for each. Mixed-fence inputs (one `\`\`\`` open + one `~~~` open) now get both closes. Added a regression test that exercises the previous bug pattern (one fence type can't accidentally mask the other's odd count). 10 new tests covering tilde-fence opener+autoclose via `truncate_chars` and `truncate_lines`, balanced-fence preservation, mixed-fence handling, indented fences (inside list items), and direct unit tests for the helper.

## [1.2.29] — 2026-04-26

Patch release fixing the `wiki_query` MCP-tool ranking quality regression flagged by the Opus 4.7 code review (#403). Pure ranking fix — no API change beyond floats appearing in the score field.

### Fixed

- **`wiki_query` ranking had no length normalisation** (#418) — the formula was `score = 50·full_match + 10·tokens_in_body + 100·title_match + 20·title_token_match`. A 1-MB log page that contains every query token *anywhere* always beat a perfectly relevant 1-paragraph entity page. As LLM clients lean on `wiki_query`, that quality regression was user-visible. Fix: divide the body component by `log2(max(len(content), 256))` before summing — long pages still rank but no longer dominate, short pages don't get an artificial boost (the 256-byte floor caps it). Title matches are unchanged since titles are already short and high-signal. Empty bodies and frontmatter-only pages now ranked safely (no division-by-zero, no NaN). Adds 8 regression tests covering short-vs-long, title precedence, empty query, no-matches, frontmatter-only, unicode tokenisation, finite-score guarantee, and short-page floor.

## [1.2.26] — 2026-04-26

Patch release fixing the markdown render-cache hot-path perf flagged by the Opus 4.7 code review (#403). Pure perf — no API change beyond `md_to_html_cache_stats()` exposing additional `plain_*` counters.

### Fixed

- **`md_to_html` cache key allocation** (#417) — used `hashlib.sha256(body).hexdigest()` per call, allocating a 64-byte hex string. On a 5000-page build this dominated the cache-lookup path. Switched to `hashlib.blake2b(body, digest_size=8).digest()` — ~3× faster and 8× less allocation per key. New `_content_key(body)` helper centralises the choice so the html and plain caches stay in sync. Birthday-collision bound at the 8-byte digest is ~4×10^9 entries, well above the 4096-entry cap.
- **`md_to_plain_text` re-parsed cached bodies** (#417) — `build.py` calls `md_to_html` and `md_to_plain_text` on the same body in multiple places (per-page render + search-index extract + RSS summary + `.txt` sibling). The plain-text path was uncached, so every body was re-parsed 2-4× per build. New `_PLAIN_CACHE` keyed off the same `_content_key` makes the second + third + … calls free. `md_to_html_cache_stats()` now exposes `plain_hits` / `plain_misses` / `plain_size` for observability. `md_to_html_cache_clear()` resets both. Adds 9 regression tests covering the new cache (correctness, hit/miss counters, FIFO eviction, content-keyed independence from the html cache, blake2b 8-byte digest pinning, one-byte-diff distinguishability).

## [1.2.21] — 2026-04-26

Patch release fixing the `Redactor`'s Windows/WSL blind spot and adding default credential-token redaction flagged by the Opus 4.7 code review (#403). The CLAUDE.md security promise — redaction "before anything hits disk" — now holds across every supported platform.

### Fixed

- **Redactor missed Windows + WSL home-directory paths** (#416) — username substitution was hardcoded to `/Users/{user}` (macOS) and `/home/{user}` (Linux) via plain `str.replace`. Windows (`C:\Users\<u>`), Windows-with-mixed-separators (`C:/Users/<u>` from copy-paste between shells), and WSL (`/mnt/c/Users/<u>`, `/mnt/d/Users/<u>`, etc.) silently skipped redaction — meaning a Windows-authored session transcript shipped real usernames to disk. Fix: single regex with prefix alternation covering all 5 path styles, plus a `(?=$|[/\\])` lookahead so `alice` doesn't match `aliceandbob`. Usernames with hyphens, underscores, and unicode characters all round-trip.

### Added

- **Default credential-token redaction** (#416) — new `_DEFAULT_TOKEN_PATTERNS` runs unconditionally regardless of user `extra_patterns` config, so users who never configured redaction are still protected. Covers GitHub PATs (`ghp_*`, `gho_*`, `ghs_*`, `ghu_*`, `github_pat_*`), AWS access key IDs (`AKIA*`), and Slack tokens (`xoxb-*`, `xoxp-*`, `xoxa-*`, `xoxr-*`, `xoxs-*`). Length thresholds (≥20 chars after the prefix; AKIA-style requires exactly 16 trailing chars) prevent false positives on docs and short example strings. Adds 21 regression tests covering the full path/token matrix.

## [1.2.19] — 2026-04-26

Patch release fixing the `build` CI-surprise commit issue flagged by the Opus 4.7 code review (#403). `llmwiki build` is now read-only on `wiki/` by default — stub seeding moves to opt-in.

### Fixed

- **`build` mutated `wiki/projects/` (CI surprise)** (#414) — `build_site` is documented as "regenerate the static HTML site" and was supposed to be read-only on `wiki/`. As a side effect of #378, `ensure_project_stubs` was wired into the build path and wrote `wiki/projects/<slug>.md` for any newly-discovered project. Users running `llmwiki build` from CI on a curated checkout discovered surprise files in their working tree (and committed-by-CI changes if the workflow auto-pushed). Fix: `build_site()` now takes `seed_project_stubs: bool = False`; the `build` CLI subcommand exposes `--seed-project-stubs` for explicit opt-in. `cmd_sync` (which the user has already opted into mutation for) passes `seed_project_stubs=True` so routine `sync` keeps seeding. Default `build` is now pure. Adds 4 regression tests covering the read-only default, the explicit flag, hand-authored stub preservation, and the CLI flag round-trip.

## [1.2.14] — 2026-04-26

Patch release fixing the `ToolsConsistency` lint rule's silent `TypeError` on list-typed `tools_used` flagged by the Opus 4.7 code review (#403). Pure correctness fix — no API change; the rule now actually runs on every page instead of aborting after the first list-typed value.

### Fixed

- **`ToolsConsistency` raised `TypeError` on list-typed `tools_used`** (#410) — `lint/rules.py:754` did `re.search(_TOOLS_USED_RE, tools_used_raw)` directly. Frontmatter parsed by `_frontmatter.py`'s inline-list path returns `tools_used` as a real Python `list`, not a string, so `re.search(regex, list)` raised `TypeError` and silently aborted the whole rule (16 → 15 effective rules). One source page with parsed-list `tools_used` was enough to take the rule out. Fix: new `_normalise_tools_used(value)` and `_normalise_tool_counts_keys(value)` helpers coerce list / str / dict / None / number / bool into a consistent `set[str]` before the comparison runs. Adds 7 regression tests covering the type matrix (list, quoted-list, empty list, str, missing, dict tool_counts, hostile types).

## [1.2.12] — 2026-04-26

Patch release fixing the `IndexSync` lint rule's false-positive flood on relative href prefixes flagged by the Opus 4.7 code review (#403). No API change; the rule now correctly resolves `./`, `..`, `#anchor`, and `?query` instead of treating each as a dead link.

### Fixed

- **`IndexSync` false positives on relative href prefixes** (#411) — `lint/rules.py` did `if href not in pages and not href.lstrip("./") in pages`, which is an operator-precedence quirk that *happens* to handle bare `./` and false-positive'd on every other shape: `../entities/Foo.md`, `entities/Foo.md#section`, `entities/Foo.md?v=2`, `entities/Foo.md?v=2#section`. The first time someone built a wiki with realistic links to anchors or query-versioned pages, the rule reported a wave of dead links that weren't dead. Fix: new `_resolve_index_href(href)` helper strips `#anchor` and `?query`, drops `./` prefixes, and collapses `..` segments via `PurePosixPath`. Hrefs that escape the wiki root (more `..` than parent dirs) return `""` and are silently dropped — the missing-page check still catches them via the inverse direction. External links (`http://`, `https://`, `mailto:`) skip the resolver entirely. Adds 9 regression tests covering the full href shape matrix plus a direct unit test for the resolver.

## [1.2.8] — 2026-04-26

Patch release unifying the frontmatter parsers and fixing two correctness bugs surfaced by the Opus 4.7 code review (#403). Windows-authored files (CRLF, BOM-prefixed) now parse identically to LF input. No user-visible behaviour change beyond formerly-dropped frontmatter now landing.

### Fixed

- **Two divergent frontmatter parsers unified** (#409) — `build.py` shipped its own regex (`^---\n(.*?)\n---\n`) and a simpler list parser that disagreed with `_frontmatter.py` on CRLF input and quoted list elements. A Windows-authored `wiki/projects/<slug>.md` silently produced an empty meta dict on the build path while every other consumer saw the populated dict. Fix: delete the duplicate parser; `build.py` re-exports `parse_frontmatter` from `_frontmatter.py`. The canonical regex now accepts LF, CRLF, and CR after each fence.
- **UTF-8 BOM dropped frontmatter silently** (#423) — files saved by Notepad on Windows ship with `\ufeff` at offset 0; the `^---` regex never matched, so the page was treated as headerless. Fix: `_strip_bom()` runs before the regex in every public entry point (`parse_frontmatter`, `parse_frontmatter_dict`, `parse_frontmatter_or_none`).

### Added

- **14 new tests** covering CRLF, CR-only, mixed line-endings, UTF-8 BOM, BOM+CRLF combination, and end-to-end `discover_sources` paths for Windows-authored files. `tests/test_frontmatter_shared.py` is now 43 cases.

## [1.2.7] — 2026-04-26

Patch release fixing the `wiki_search` MCP-tool hit cap and pinning the project-filter substring contract flagged by the Opus 4.7 code review (#403). No API change; same response shape, correct cap.

### Fixed

- **`wiki_search` 200-cap was per-root, not total** (#413) — the search loop had three nested `for` loops (root → file → line) but only the inner two had a `break` on the cap. `include_raw=True` could return up to 400 hits when the schema implies 200, and the entire `raw/sessions/` tree got scanned even after `wiki/` had already capped — doubling the work on a 500 MB corpus. Fix: hoist the cap to a single `truncated` flag checked at every loop boundary so the search terminates atomically when 200 is reached. Lowercase the search term once (was being re-lowercased per line). The `truncated` field in the response now reflects the actual cap state instead of a `>=` heuristic.

### Added

- **`wiki_list_sources` `project=` filter regression tests** (#431) — the filter is unsanitized substring match by design, but no test pinned that contract. Added `tests/test_mcp_safety.py` with 13 hostile-input cases (`../`, `../../etc`, `..\\`, `/etc/passwd`, URL-encoded traversal, command-injection patterns, backtick + `$()` substitution) confirming none escape `raw/sessions/`. Plus 12 cap-correctness tests for `wiki_search` (cap fires across roots, single file with 1000 hits caps at 200, case-insensitive match preserved, regex metacharacters treated literally, unicode/emoji terms work, empty + whitespace-only term rejected). Closes test-gap #431.

## [1.2.3] — 2026-04-26

Patch release fixing 2 critical URL-correctness bugs surfaced by the Opus 4.7 code review (#403). No behaviour change beyond the fixed URLs; safe to upgrade.

### Fixed

- **`source_file:` frontmatter now matches disambiguated filenames** (#404) — `render_session_markdown` rendered the canonical `source_file:` line *before* the collision disambiguator decided the actual on-disk filename. Disambiguated sessions (e.g. `<canonical>--<hash>.md`) silently shipped with a `source_file:` field that resolved to a sibling file (or a 404 in the graph viewer). Fix: rewrite `source_file:` to match the disambiguated filename whenever disambig fires. Adds a regression test (`tests/test_collision_retry.py::test_disambiguated_source_file_matches_disk`).
- **JSON-LD / sitemap / RSS / per-page `.json` exporters URL drift** (#415) — exporters composed URLs as `sessions/<project>/<meta.slug>.html` while `build.py` writes HTML to `sessions/<project>/<path.stem>.html`. The two stems differ by the date prefix and any `--<hash>` disambiguator suffix → every URL emitted in `sitemap.xml`, `rss.xml`, `graph.jsonld`, and per-session `.json` siblings was wrong. Fix: unify on `path.stem` for URL composition; reserve `meta["slug"]` for display fields (titles, JSON-LD `name`).
- **Claude Code CI actions now use Opus 4.7** (#401) — both `claude-code-review.yml` (auto-fires on every PR) and `claude.yml` (`@claude` mention) now pass `--model claude-opus-4-7` via `claude_args`. Was the action's default Sonnet.
- **Stale `pip install llmwiki[graph]` reference in `graphify_bridge.py` docstring** (#402) — corrected to `pip install llm-notebook[graph]` after the PyPI distribution rename in #398.

## [1.2.2] — 2026-04-26

Patch release closing the path-traversal vector flagged by the Opus 4.7 code review (#403). No user-visible behaviour change beyond rejecting poisoned slugs.

### Fixed

- **Path-traversal via attacker-controlled `project:` / `slug:` frontmatter** (#405) — `project_slug = str(meta.get("project") or path.parent.name)` was used verbatim in `out_dir / "sessions" / project_slug / ...`. A hand-crafted `raw/sessions/*.md` with `project: ../../../etc/passwd` would have written under `out_dir/../../...`. Fix: new `_safe_slug()` helper at `llmwiki/build.py` rejects non-`[A-Za-z0-9._-]` values, traversal segments, absolute paths, and null bytes — falling back to a clearly abnormal slug rather than escaping `out_dir`. Sanitization happens at the discovery boundary so every downstream consumer (project page, session page, search index, exporters) sees a safe value. Adds `tests/test_path_traversal.py` (35 cases) closing test-gap #428.

## [1.2.0] — 2026-04-25

First stable release on the 1.x line. Promotes the eight rc1-rc8 prereleases into one stable tag and bundles the post-rc8 audit fixes, the new `wiki-all` one-shot pipeline runner, the Playwright/axe-core E2E suite, and ten UX-critique items into a single shippable cut.

### Added

- **`llmwiki all` one-shot pipeline runner** (#378) — new CLI subcommand and `/wiki-all` slash command that runs `build → graph → export all → lint` in sequence. `--strict` escalates any lint warning into a non-zero exit (suitable for CI gating); `--fail-fast` stops at the first non-zero step; `--skip-graph` / `--graph-engine builtin` for environments without the optional Graphify dep. Closes the last gap where users had to chain four slash commands manually after a sync.
- **Auto-seeded project stubs** (#378) — `build.py:ensure_project_stubs()` runs after `group_by_project()` and creates an empty `wiki/projects/<slug>.md` for every newly-discovered project. Hand-authored files are never overwritten. Closes the gap where real-data project pages were bare while demo projects rendered with hero descriptions, topic chips, and homepages.
- **2 new lint rules** (#378) — `frontmatter_count_consistency` warns when a `type: source` page's `user_messages` / `turn_count` / `tool_calls` frontmatter disagrees with what the body actually contains (catches inflated demo-data counts going forward); `tools_consistency` warns when `tools_used` and `tool_counts.keys()` disagree. Registry now ships 16 rules.
- **6 entity / concept stub pages** (#378) — `wiki/entities/Anthropic.md`, `OpenAI.md`; `wiki/concepts/AgenticWorkloads.md`, `CachePricing.md`, `MultimodalModels.md`, `ARC-AGI-2.md`. Resolves all wikilinks reaching out from the seeded `ClaudeSonnet4` and `GPT-5` model pages.
- **End-to-end test suite** (#384) — Playwright + pytest-bdd Gherkin specs in `tests/e2e/` covering homepage, session detail, command palette, keyboard navigation, mobile bottom nav, theme toggle, copy-as-markdown, responsive layout (9 viewports × 3 pages), edge cases, accessibility (axe-core), and visual regression. Found 3 real bugs while landing the suite (graph.html JS pageerror, WCAG contrast, navigation regression). Opt-in via `[e2e]` extras; default `pytest tests/` excludes `tests/e2e/`.
- **Sticky table of contents on the docs hub** (#387 U9) — the docs hub at `site/docs/index.html` enumerates ~80 editorial pages and was scrolling to ~5000 px without in-page navigation. The build now emits a `tutorial-toc` block on the hub the same way it does on tutorials, and on viewports ≥ 1024 px the TOC sticks to the top so users always have a way to jump.
- **Branded 404 page** (#387 U8) — `llmwiki build` now emits `site/404.html` with the standard nav + footer + a "try one of these" panel linking back to home / projects / sessions / changelog. `llmwiki serve` overrides `SimpleHTTPRequestHandler.send_error` to use the branded body for any 404 response (status code stays 404 — this is the response body, not a redirect). Dead wikilinks now land users on something they can navigate from instead of the stdlib's plain-text default.
- **Graphify integration** (#364) — `pip install llm-notebook[graph]` adds the `graphify` package as an optional dependency. New `graphify_bridge.py` module provides AI-powered knowledge graph building via tree-sitter AST extraction, Leiden community detection, and confidence-scored edges. Run with `llmwiki graph --engine graphify`.

### Fixed

- **AI-consumable exports preserve code** (#378 / issues.md #1) — `_plain_text` in `llmwiki/exporters.py` used to replace every fenced code block with a single space, deleting the most valuable content from `.txt` siblings, `.json` `body_text`, `llms.txt`, `llms-full.txt`, search chunks, and RSS summaries. Code is now preserved (only the fences are stripped).
- **JSON sibling type fidelity** (#378 / issues.md #3) — frontmatter values were being passed verbatim into the per-page JSON, so `user_messages: 6` became `"6"` (string), `is_subagent: false` became `"false"` (a truthy string in both JS and Python). New `_as_int` / `_as_bool` helpers coerce on write.
- **`sync --force` no longer silently drops colliding sessions** (#378 / issues.md #339-followup) — collision disambiguator was gated on `not force`, and `--force` wipes the state file, so two sessions with the same canonical filename overwrote each other. On a real 494-session corpus this cost ~200 sessions. Fix: per-run `names_written_this_run` set tracks claimed filenames independent of `--force`.
- **8 demo session frontmatter counts** (#378 / issues.md #2) — `user_messages` / `turn_count` / `tool_calls` in `examples/demo-sessions/**/*.md` were 2–10× higher than the body actually contained; rewritten from body content. The new `frontmatter_count_consistency` lint rule prevents regression.
- **Demo project page broken wikilinks** (#378 / issues.md #5) — un-wikilinked `[[Python]]`, `[[Rust]]`, `[[FastAPI]]`, etc. references that had no target page. The 22 broken-wikilink lint warnings are now zero.
- **`sync --force` collision data loss across multiple sources** (#378) — added `tests/test_collision_retry.py::test_force_sync_does_not_drop_colliding_sources` plus 2 more regression tests (three-way collision under no-force, disambig-name stability across incremental syncs).
- **`graphifyy` typo** (#378 / issues-commands.md I-4b) — global `graphifyy` → `graphify` in `cli.py` + `graphify_bridge.py` (7 occurrences in user-facing help and error strings). The PyPI package name is `graphify`.
- **`setup.sh --dry-run` referenced a flag that doesn't exist** (#378 / issues-commands.md I-2a) — swapped to `sync --status` which prints adapter counts without converting files. Fresh-install onboarding step no longer silently fails behind `|| true`.
- **`CRITICAL_FACTS.md` seed shipped a broken `[[wikilinks]]` reference** (#378 / issues-commands.md I-1a) — the seed in `cli.py` and the live file under `wiki/` both reworded to plain prose so a fresh `init` no longer fails lint on its own seed.
- **Non-hermetic graphify test** (#378 / issues.md #6) — `tests/test_graphify_bridge.py::test_is_available_true_when_graphify_installed` asserted `graphify` was pre-installed in dev. Now skipped via `@pytest.mark.skipif` when the optional package is absent.
- **Broken adapter doc paths after the contrib/ move** (#381) — five `docs/adapters/*.md` files (chatgpt, cursor, gemini-cli, obsidian, opencode, copilot) referenced `llmwiki/adapters/<name>.py` paths that moved to `llmwiki/adapters/contrib/<name>.py` in #363. Three docs (jira.md, meeting.md, pdf.md) referenced source files removed in #363; deleted those docs and removed them from the `docs/index.md` adapter reference list. Closes #367, #379.
- **JS pageerror in graph.html** (#386) — `Cannot read properties of null (reading 'addEventListener')` fired during cross-page navigation when the graph viewer's chrome controls (`#theme-toggle`, `#ctx-menu`, `#search-input`, `#cluster-toggle`) were missing or rendered in a minimal layout. Added defensive null-guards on every `getElementById` → `addEventListener` chain in `llmwiki/graph.py`. The `test_full_navigation_journey` E2E test now passes (xfail marker removed).
- **WCAG color-contrast violations on session pages and dark-mode chrome** (#385) — axe-core flagged 7 hljs token classes (`hljs-built_in`, `hljs-number`, `hljs-literal`, `hljs-attr`, `hljs-title`, `hljs-symbol`, `hljs-bullet`) for failing 4.5:1 contrast against `--bg-code` in light mode, plus the dark-mode active nav link + breadcrumb on the dark navbar at 4.63:1. Fix: explicit darker overrides for the offending hljs tokens in `llmwiki/render/css.py` (light mode), bumped `--accent` from `#7C3AED` to `#a78bfa` (8.5:1 on `#0c0a1d`) in dark mode, and added `text-decoration: underline` on `.nav-links a.active` so the active state doesn't rely on color alone (WCAG 1.4.1).

### Changed

- **Simplify adapters — core vs contrib split** (#363) — 3 core adapters auto-discovered (claude_code, codex_cli, obsidian). 6 adapters moved to `adapters/contrib/` (chatgpt, copilot, cursor, gemini, opencode). 3 non-session adapters deleted (jira, meeting, pdf).
- **Slim CLI from 25 to 11 subcommands** (#362) — removed quarantine, backlinks, references, tag, log, watch, export-obsidian, export-marp/jupyter/qmd, check-links, manifest, install-skills, link-obsidian, completion.
- **Live adoption of `cache_tier` + `reader_shell` on seeded wiki pages** (#285) — 6 committed wiki pages now carry explicit `cache_tier` (4× L2, 2× L1) and 2 have `reader_shell: true`. The `cache_tier_consistency` lint rule now runs against real data and correctly flags the 2 L1 pages as needing inbound wikilinks (which is useful, actionable info). `docs/reference/cache-tiers.md` + `docs/reference/reader-shell.md` gain "Live adopters" sections listing the opt-in pages + why each tier was picked. Closes the loop on two features that shipped scaffolds + tests + docs but had zero real adoption.
- **`wiki/index.md` section headings carry a `(count)`** (#387 U6) — past ~50 pages the flat bullet lists per section became hard to scan at a glance. Each section heading now reads `## Entities (4)` / `## Projects (4)` etc., so a reader can see the size of each bucket without scrolling. The seed in `cmd_init` and the documented format in `CLAUDE.md` both updated so future ingest agents preserve the format. Closes the last open item in #387.
- **`llmwiki export` help text** (#387 U1) — the help string for the `export` subcommand previously listed three formats and trailed off with `...`. Now spells out the full set: `llms-txt`, `llms-full-txt`, `jsonld`, `sitemap`, `rss`, `robots`, `ai-readme`, `marp` (or `all`).
- **`llmwiki sync --auto-build` / `--auto-lint` help text** (#387 U3) — the wording "if schedule allows" sounded calendar-based; updated to point explicitly at the `examples/sessions_config.json` `schedule.build` / `schedule.lint` config keys with the `on-sync` value that triggers them.
- **`llmwiki synthesize --estimate` row label** (#387 U4) — renamed the second row from `Synthesized (history):` to `Already synthesized:`. Plain English without the parenthetical aside.
- **Copy-as-markdown button** (#387 U5) — added an explicit `aria-label="Copy session content as markdown"` + `title` so a future icon-only variant doesn't lose its accessible name.
- **`llmwiki adapters` column names** (#387 U2) — renamed `default` → `present`, `configured` → `enabled`, `will_fire` → `active`. The new names are immediately legible without consulting the legend below the table. The legend itself was tightened. No behavioural change.
- **Hero-subtitle plural inflection** (#387 U7) — count strings on the homepage, projects index, and sessions index use the new `_pluralize(n, singular)` helper so users no longer see `"1 sessions"` / `"1 projects"`. Examples: `"1 main session · 0 sub-agent runs · 1 project"`, `"1 session total"`.
- **Dependency bumps** — `pytest >=8.4.2` (#375), `pytest-playwright >=0.7.1` (#374), `ruff >=0.15.11` (#373), `pytest-bdd >=8.1.0` (#372). GitHub Actions: `docker/build-push-action 5→7` (#371), `peter-evans/create-issue-from-file 5→6` (#370), `actions/github-script 8→9` (#369).

### Removed

- **9 dead-weight modules** (#360) — prototypes, auto_dream, visual_baselines, cache_tiers, eval, web_clipper, scheduled_sync, reader_shell, image_pipeline (~5K lines).
- **3 niche exporters** (#361) — export_marp, export_jupyter, export_qmd (~800 lines).
- **3 non-session adapters** — jira_adapter, meeting, pdf (~600 lines).
- **14 CLI subcommands** — replaced by core commands or deferred to skills.
- **89 stale git branches** cleaned up.

## [1.1.0-rc8] — 2026-04-21

rc8 batch.  Completes Mode B end-to-end with CLI + slash-command plumbing on top of the agent-delegate backend from rc8.

### Added

- **`llmwiki synthesize --list-pending`** (#316 follow-up) — prints every pending agent-synthesis prompt as a table (`UUID  SLUG · PROJECT · DATE`).  Returns exit 0 even when empty so the slash-command layer can use "no pending prompts" as a success signal.  Zero-cost read of `.llmwiki-pending-prompts/*.md`.
- **`llmwiki synthesize --complete <uuid> --page <path>`** (#316 follow-up) — the agent-side counterpart of the backend's placeholder-writing step.  Reads the synthesized body from `--body <file>` or stdin, verifies the target page carries the matching `<!-- llmwiki-pending: <uuid> -->` sentinel, rewrites the placeholder in place (preserving frontmatter), and deletes the pending prompt file.  Non-zero exit on: missing `--page`, empty body, missing target file, missing sentinel, uuid mismatch.  9 tests in `tests/test_synthesize_cli_pending.py`.
- **`/wiki-sync` step 6** — slash command now scans for pending agent-delegate prompts after ingest.  For each pending uuid: reads the prompt file, synthesizes inside the current agent turn (including the `<!-- suggested-tags: ... -->` block from #351), writes a scratch body, calls `llmwiki synthesize --complete` to rewrite the placeholder.  Serial loop — the agent is single-conversation.
- **`/wiki-synthesize` two new natural-language variants** — "list pending agent prompts" → `--list-pending`; "complete pending synthesis <uuid>" → `--complete <uuid> --page <path>`.

### Changed

- **`docs/modes/agent/backend.md`** — expanded with the real CLI surface + exit-code table + `/wiki-sync` step-6 walkthrough.

- **Mode B agent-delegate synthesis backend** (#316) — a new `agent` value for `synthesis.backend` in `sessions_config.json` that defers the LLM call to the user's running Claude Code / Codex CLI session instead of making an HTTP API call.  The backend (`llmwiki/synth/agent_delegate.py`) writes the rendered prompt to `.llmwiki-pending-prompts/<uuid>.md` and returns a placeholder page whose first line is the machine-readable sentinel `<!-- llmwiki-pending: <uuid> -->`.  The slash-command layer reads pending prompts on the next agent turn, synthesizes the content inside the existing session, and calls `complete_pending(uuid, body, page)` to rewrite the placeholder in place.  Zero incremental API cost (piggybacks on the agent subscription).  Zero bytes of session content leave the laptop.  Works when `ANTHROPIC_API_KEY` is unset.  `is_available()` auto-detects the agent runtime via `LLMWIKI_AGENT_MODE` / `CLAUDE_CODE` / `CODEX_CLI` / `CURSOR_AGENT` env vars; returns `False` outside an agent so the pipeline falls back to `dummy` instead of silently producing placeholders forever.  29 tests in `tests/test_agent_delegate.py` cover runtime detection, prompt writing, sentinel round-trip, uuid reuse for re-synthesize, `complete_pending` + `list_pending`, `resolve_backend` wiring for `agent` / `agent-delegate` / `agent_delegate` / case-insensitive names, and a hard network-isolation guard (neutralised `socket.socket` during synthesis — the call still succeeds because no HTTP path exists).  New docs: `docs/modes/agent/backend.md`.

## [1.1.0-rc7] — 2026-04-21

rc7 batch.  Closes 4 issues: #351 (AI auto-tags), #348/#350/#353 (recurring broken-link reports).

### Fixed

- **Recurring broken-link reports** (#348, #350, #353) — the `lychee` workflow kept opening the same "Broken external links detected" issue every Sunday because two URLs always failed on CI runners: (a) `https://github.com/Pratiyush/llm-wiki/settings/environments` is auth-gated (admin only), and (b) `docs/index.md` pointed at `../changelog.html` which only exists inside the compiled `site/`, not at repo root where lychee resolves relative links.  Fix: added `^https://github\.com/Pratiyush/llm-wiki/settings` to `lychee.toml`'s exclude list, and repointed the `docs/index.md` changelog link at the canonical `CHANGELOG.md` on master (stopped bitrotting the "latest release" text too — was frozen at rc2, now rc6).

### Added

- **Automatic AI-suggested tags during synthesis** (#351) — before rc6 every wiki source page shipped with a deterministic-only tag list (`[<adapter>, session-transcript, <project>, <model-family>]`).  Readers got no *topical* signal — a session about prompt caching looked the same as a session about SQLite FTS.  Now the synthesizer's own call (Anthropic API in API mode, Ollama in Agent mode) emits a `<!-- suggested-tags: prompt-caching, anthropic-api, token-budget -->` block as the first line of its response, which `_extract_suggested_tags` parses and strips before the body hits disk.  `_merge_tags` then folds those topical tags into the deterministic baseline with (a) maintainer-curated tags preserved first (re-synthesize never overwrites hand edits), (b) stop-word filter so the LLM can't re-add `claude-code` / `session` / `summary`, (c) hard cap of 5 AI tags per page, (d) near-duplicate rejection at threshold 0.80 + prefix-containment check so `prompt-cache` gets blocked when `prompt-caching` already exists.  Zero extra API round-trips — rides the existing synthesis call.  22 new tests in `tests/test_ai_suggested_tags.py` cover parsing, merging, de-dup, stop-words, caps, re-synthesize preservation, and malformed-input graceful fallback.

## [1.1.0-rc6] — 2026-04-21

rc6 batch.  Closes 4 open issues: #346 (adapter tag fix), #282 (tutorial UX), #277 (palette indexes), #283 (md cache).

### Fixed

- **Frontmatter `tags:` was hardcoded to `claude-code` for every adapter** (#346, reported by @fengguanghuai) — `render_session_markdown` emitted `tags: [claude-code, session-transcript]` regardless of which adapter (`claude_code`, `codex_cli`, `cursor`, `copilot-chat`, `gemini_cli`, `opencode`, `chatgpt`) produced the session.  Result: every session grouped under the Claude chip on the compiled site even when the user was on Codex or Cursor.  Fix: new `_adapter_tag()` helper normalises the registry name (`claude_code` → `claude-code`, `codex_cli` → `codex-cli`, `copilot-chat` → `copilot-chat`), and `render_session_markdown` now takes an `adapter_name` kwarg propagated from `convert_all`.  Back-compat default of `claude-code` for callers that don't pass the kwarg so no silent regression on existing tests.  22 new parametrized tests in `tests/test_adapter_tag.py`.

### Added

- **Tutorial UX polish** (#282) — every numbered tutorial under `docs/tutorials/` now ships with (a) an in-page table of contents built from `##` / `###` headings (collapsed `<details>` block, click to jump), (b) a prev/next footer showing the adjacent tutorials with their titles, (c) an "Edit on GitHub ↗" link pointing at the raw `.md` source so readers can file PRs from the rendered page.  Styled via new CSS rules under `.docs-shell .tutorial-toc`, `.tutorial-footer`, `.tutorial-edit` — all tokens inherited from the brand-system CSS, no hard-coded hex.  Mobile: prev/next cards stack vertically below 760 px.  15 new tests cover sequence building, TOC emission thresholds, footer placement, edit-link shape, and passthrough-page exclusion.

- **Command palette indexes every doc page + every slash command** (#277) — the `⌘K` / `/` palette used to only match sessions, projects, and 3 hard-coded pages (home / projects / sessions).  Now it includes 107 `docs/**/*.md` pages (every tutorial, reference, adapter guide, deploy guide) and 17 `.claude/commands/*.md` slashes.  Docs entries use their frontmatter `title` + first paragraph as the body for matching; slash entries show `/wiki-<name>` and copy the command to clipboard on Enter (instead of trying to navigate — slashes aren't URLs).  11 new tests in `tests/test_palette_indexes.py` pin coverage for cheatsheet, upgrade guide, tutorials, references, and known `/wiki-*` wrappers.

- **Content-hash cache for `md_to_html`** (#283) — SHA-256-keyed in-memory cache in front of the markdown renderer.  Deterministic output + boilerplate sections (`## Connections`, `## Raw Mentions`) called hundreds of times per build means a ~60-80 % hit rate on real corpora.  Bounded at 4096 entries with FIFO eviction to cap memory.  New `md_to_html_cache_stats()` / `md_to_html_cache_clear()` helpers for tests + observability.  Semantics unchanged: `_md_to_html_uncached` runs on every miss and the cached result is byte-for-byte identical.  11 tests cover hit/miss counters, eviction, clear, round-trip, empty body, unicode, and cached-vs-uncached equivalence.

## [1.1.0-rc5] — 2026-04-21

Site audit + 5 closed batches.  Closes 12 open issues in one pass:
session-local ref stripping, cheatsheet, README+CONTRIBUTING compile,
expanded Playwright E2E, slash-CLI parity test, 4 adapter docs, Ollama
tutorial, dual-mode docs skeleton, `/wiki-synthesize` slash, and the
shared frontmatter parser.

### Added

- **Dual-mode docs skeleton** (#317) — new `docs/modes/` tree with a top-level comparison + two coloured-banner landing pages: `docs/modes/api/` (purple banner, "API MODE — uses your Anthropic API key") and `docs/modes/agent/` (teal banner, "AGENT MODE — uses your existing Claude Code / Codex CLI session"). The docs hub now leads with a "Pick your mode" comparison table before the tutorials. Prepares the info architecture for the actual backends that ship with #315 (API) and #316 (Agent).

- **`/wiki-synthesize` slash command** (#281) — wraps `python3 -m llmwiki synthesize` with natural-language flag translation. Users say "just show me what it would cost" → `--estimate`; "preview without writing" → `--dry-run`; "re-synthesize everything" → `--force`. Makes the synthesize CLI accessible from inside Claude Code without remembering flags. Documented in `docs/reference/slash-commands.md` + passes the slash-CLI parity guardrail.

- **Tutorial 08 — Synthesize with Ollama** (#276) — step-by-step walkthrough from Ollama install → model pull → config → first synthesize. Covers cost estimation (still $0), troubleshooting (connection refused, 404, slow synthesize, hallucinations), and the path forward to API mode. 6 sections per the mandatory tutorial skeleton.

- **Four missing adapter docs + eval-vs-lint decision tree** (#274, #280) — new adapter pages: `docs/adapters/chatgpt.md`, `docs/adapters/jira.md`, `docs/adapters/meeting.md`, `docs/adapters/opencode.md`. Each covers the source format, enable instructions, output layout, gotchas, and code pointers. `docs/reference/slash-commands.md` gains a "Decision tree: which tool runs when?" section distinguishing CLI-vs-slash and lint-vs-eval — the two confusion points users hit most often.

- **Configuration reference — ~20 missing keys added** (#275) — `schedule.{build,lint}`, `synthesis.{backend,ollama.*}`, `pdf.{enabled,source_dirs,min_pages,max_pages}`, `meeting.{enabled,source_dirs,extensions}`, `jira.{enabled,server,email,api_token,jql,max_results}`, `chatgpt.{enabled,conversations_json}`, `web_clipper.{enabled,watch_dir,extensions,auto_queue}`, `scheduled_sync.{enabled,cadence,hour,minute,weekday,working_dir,llmwiki_bin}`. Per-adapter table also grew an "AI session?" column showing which adapters fire by default vs which require `enabled: true`.

- **Canonical frontmatter parser** (#273 partial) — new `llmwiki/_frontmatter.py` ships `parse_frontmatter()`, `parse_frontmatter_dict()`, `parse_frontmatter_or_none()` covering the three return-shape conventions scattered across 8 existing copies. Existing call sites can migrate incrementally; new code should use the shared helper. Parses inline lists, quoted scalars, bools, ints, floats without a YAML dependency. 29 tests.

- **Expanded E2E coverage** (#278) — `features/keyboard_nav.feature` grew from 4 to 9 scenarios: added `/` palette open, Escape closes palette + help dialog, lone-`g` no-op guard, palette input doesn't trigger shortcuts. New `features/graph_viewer.feature` with 3 scenarios (graph renders, back-to-site link, `site_url` in payload). New `tests/test_serve_smoke.py` with 3 tests (server starts + serves index.html, rejects missing `--dir`, `--help` mentions all flags). Total Playwright + pytest-bdd coverage: ~75 scenarios, up from ~62.

- **Slash-CLI parity guardrail** (#279) — new `tests/test_slash_cli_parity.py` (7 tests) keeps slash wrappers aligned with the CLI. Every `wiki-<name>.md` that wraps a real CLI subcommand must: (a) reference it via `python3 -m llmwiki <sub>`, (b) share the same name (`/wiki-candidates` wraps `candidates`), (c) carry at least one bash example. Prompt-driven slashes (`/wiki-ingest`, `/wiki-query`, `/wiki-reflect`, `/wiki-sync`, `/wiki-update`, `/wiki-lint`) are listed explicitly so authors can't accidentally skip the parity check.

- **Command cheatsheet** (#269) — new `docs/cheatsheet.md` fits every slash command, CLI subcommand, and flag onto one page. Grouped by daily-flow, observability, tag curation, backlinks, adapters, flags, config, and see-also. Linked from the docs hub Operate section between the upgrade guide and FAQ. First thing a returning user looks for.

- **README + CONTRIBUTING compile to site pages** (#284) — `site/README.html` and `site/CONTRIBUTING.html` now ship alongside `site/changelog.html`. Visitors reading tutorials no longer get bounced to GitHub for the README; the compiled page uses the same editorial shell as the rest of the site. New `_render_root_md_page()` helper + `render_readme_page()` / `render_contributing_page()` wired into the main build step. The `.md → .html` link rewriter now correctly routes `README.md` / `CONTRIBUTING.md` in-site (they were previously in the GitHub-only list). Session bodies also pass through `rewrite_md_links_to_html` now so `../../CONTRIBUTING.md` inside a transcript resolves to the compiled page.

### Fixed

- **Session transcripts leaked 100+ broken local-project links** (#336) — new `strip_dead_session_refs()` in `llmwiki/docs_pages.py` unwraps anchors that point at session-local files the compiled site can't resolve: known basenames (`tasks.md`, `CHANGELOG.md`, `_progress.md`, `user_profile.md`, `TODO.md`, `roadmap.md`, etc.), wiki-layer wikilinks (`../../sources/`, `../../wiki/`, `../../entities/`), IDE config dirs (`.kiro/`, `.cursor/`, `.vscode/`, `.claude/`), build files (`settings.gradle.kts`, `gradlew`, `CODEOWNERS`, `.env`), absolute home paths (`/Users/…`, `/home/…`), and bare single-filename `.md` / `.txt` / `.json` / `.yaml` references. The filename stays visible as `<span class="session-ref dead-link">` with the original href in the `title` attribute so the user can still see what was referenced, but the compiled site stops reporting 404s. Applied to session rendering in `build.py` after the GitHub rewriter. Before: 351 broken internal links. After: 247 (-30%). 54 new tests in `tests/test_session_ref_stripper.py` covering every category.

- **Link checker truncated broken list at 100** (#336 follow-up) — the list was capped to 100 entries even though `broken_count` reported the true total. That hid real-world improvements when a fix drained one category (tasks.md, 7 entries) but the tail of long-tail hrefs reshuffled (99 unique targets still in the head of the list). Removed the cap; `broken` now matches `broken_count`.

- **raw/sessions filename collisions quarantined 9 sources per real-corpus sync** (#339) — two distinct jsonls produced the same `YYYY-MM-DDTHH-MM-project-slug.md` filename when: (1) subagent jsonls (`~/.claude/projects/<proj>/<uuid>/subagents/agent-*.jsonl`) inherit the parent session's start-time + slug → identical canonical name as the parent, (2) two top-level sessions start in the same minute inside the same project. The raw-immutability guardrail (#326) correctly refused to overwrite, but the result was that sub-conversations + same-minute siblings got silently quarantined instead of stored. Fix: `convert_all` now detects canonical-name collision (file exists AND the state key's mtime doesn't match this source) and retries with a stable 8-char hash of the source path appended (`<ts>-<proj>-<slug>--<hash8>.md`). Parent session keeps its canonical filename; siblings land side by side. New `flat_output_name(..., disambiguator=...)` kwarg + `_source_hash8()` helper. Re-sync of the same source is still idempotent (state-key mtime match short-circuits the retry). 5 new parametrized tests in `tests/test_flat_naming.py` + 3 integration tests in `tests/test_collision_retry.py` (subagent collision, two top-level sources with pinned slug, re-sync idempotency).

- **E2E keyboard-nav test flaked on `g s → sessions`** — the step `the URL path contains "sessions/index.html"` used `page.evaluate("() => window.location.pathname")` which races the in-flight navigation from the `g`-prefix chord: evaluate's execution context tears down while post-processing the keypress, producing `Error: Page.evaluate: Execution context was destroyed, most likely because of a navigation` ~5% of the time in CI. Fix: new `_current_path(page)` helper reads `page.url` (synchronous property, populated by the frame-navigated event without running JS) and parses the path out of it. No more evaluate race.

## [1.1.0-rc4] — 2026-04-20

Navigation + quality release. Fixed two high-impact usability bugs the
user surfaced end-to-end: graph clicks went nowhere (99.7% 404) and
95% of wiki pages were orphans with no backlinks. Plus source-code /
root-file link routing through GitHub, verify-before-fixing
contribution rule, and an upgrade guide.

### Fixed

- **Source-code + root-file links in docs + sessions dead-ended on the compiled site** (#270) — docs pages and session transcripts routinely reference files like `../../llmwiki/convert.py`, `../CLAUDE.html`, or `CONTRIBUTING.md` that aren't compiled as standalone HTML in `site/`. Build step used to rewrite `.md` → `.html` unconditionally, turning valid source-code references into 404s. New `rewrite_source_code_links_to_github()` runs **before** the generic `.md → .html` pass and routes these categories to absolute GitHub URLs instead: source code extensions (`.py`, `.js`, `.ts`, `.tsx`, `.jsx`, `.go`, `.rs`, `.rb`, `.java`, `.kt`, `.swift`, `.sh`, `.toml`, `.yaml`, `.yml`, `.json`, `.cfg`, `.ini`, `.Dockerfile`, `.env`); repo-root files (README.md, CONTRIBUTING.md, CODE_OF_CONDUCT.md, CLAUDE.md, AGENTS.md, SECURITY.md, RELEASE-NOTES.md, LICENSE, `.gitignore`, `.editorconfig`); AND the previously-rewritten `.html` versions of root-only files flip back to `.md` on GitHub (`../CLAUDE.html` → `https://github.com/Pratiyush/llm-wiki/blob/master/CLAUDE.md`). Applied to both docs compilation AND session rendering. Before: 471 broken internal links reported (unique targets: 25,733 scanned). After: 100. The remaining 100 are user-content references from session transcripts that point at files unique to the user's local project (tasks.md, _progress.md, user_profile.md) — tracked separately since they require session-scoped rewriting logic. 40 new tests in `tests/test_github_link_rewriter.py` (every extension, every repo-root file, `.html` flip-back, external URL passthrough, mailto passthrough, anchor passthrough, docs .md left alone, multi-rewrite in one body, HTML attribute preservation).

- **Graph navigation: 99.7% of clicks used to 404** (#331) — the interactive knowledge graph's click handler rewrote `wiki/entities/Foo.md` → `entities/Foo.html`, but `site/entities/` doesn't exist (wiki-layer pages aren't compiled as standalone HTML), and source pages live at `site/sessions/<proj>/<date-stem>.html` not `site/sources/<proj>/<bare-stem>.html`. Measured on a 622-node corpus: 620 clicks → 404. New `_compute_site_url()` maps each wiki page to its real site URL at graph-build time; for source pages it reads the `source_file:` frontmatter and derives the date-prefixed session path. Entities / concepts / syntheses / nav files get `site_url = None` (no compiled page exists). The click handler + context-menu "Open page" respect this — `null` triggers a transient tooltip (`"X — no compiled page (see ## Connections)"`) instead of opening a dead link. New `build_graph(verify_site_dir=…)` kwarg validates URLs against the actual compiled site and nulls missing targets. Integrated into `copy_to_site()` so the shipped graph only offers links that exist. Full suite now 264 valid URLs + 358 graceful-null, 0 broken.

- **Wiki had 589 orphan pages because backlinks never propagated** (#331) — `entities/Pratiyush.md` was referenced from 12 session pages but its own page had no `## Referenced by` section, so the graph was a collection of disconnected islands (575 / 596 source pages with zero inbound). New `llmwiki/backlinks.py` module + `llmwiki backlinks` CLI builds the reverse-reference index and injects a managed `## Referenced by` section bounded by `<!-- BACKLINKS:START --> … <!-- BACKLINKS:END -->` sentinels. Idempotent rerun (only the block changes, every other line stays exact), `--dry-run` preview, `--prune` inverse, `--max-entries` cap (default 50) with a "…and N more — run `llmwiki references <slug>`" footer. Sort by date desc when referrers have `date:` field, alphabetical otherwise. Skips `archive/` and `_context.md` stubs. Safe on pages with pre-existing content (the block gets appended below, not mid-file). 38 new tests in `tests/test_backlinks.py` (sentinel handling, reverse-index correctness, render + sort, file-system integration with dry-run / prune / idempotency, CLI subprocess coverage).

### Changed

- **New contribution rule #7: verify before fixing stale issues** — issues accumulate; some are resolved as a side-effect of unrelated PRs, some describe problems that no longer reproduce on current `master`. Rule codified in `CONTRIBUTING.md` rule #7 and the plan-file rule #14: before shipping a fix for any old issue, (a) reproduce the problem on current master — shell command / click-path / failing test; (b) re-read the referenced code paths to confirm they still exist; (c) if already fixed, close with a comment citing the resolving commit; if the description is wrong but there's a real bug nearby, file a new precise issue. Never ship a speculative fix — if you can't reproduce, say so in the PR body.

- **Contribution rule made explicit: every PR ships docs + CHANGELOG + release-note bullet** — previously the rule lived only in the plan file. Now codified in `CONTRIBUTING.md` rule #6 (the "seven rules" intro) and the PR template's pre-merge checklist. PRs adding a new CLI subcommand, slash command, config key, or lint rule MUST update the matching `docs/reference/*.md` table in the same PR. CI already blocks merges missing a CHANGELOG diff; this codifies the expectation so first-time contributors don't discover it at merge time.

### Fixed

- **`raw/` immutability guardrail + AI-sessions-only default** (#326) — `CLAUDE.md` rule 1 was documentation-only. Now runtime-enforced: `_raw_write_guard()` refuses to overwrite any existing `raw/` file unless `llmwiki sync --force` is passed explicitly. Overwrite attempts are recorded in `.llmwiki-quarantine.json` (shipped in #300) with a clear reason, so the operator sees exactly what would have been clobbered. New `is_ai_session` class attribute on `BaseAdapter` classifies adapters; `obsidian`, `jira`, `meeting`, and `pdf` are marked `is_ai_session = False` and are now **opt-in only** — `llmwiki sync` with no flags no longer silently walks a user's personal Obsidian vault. `llmwiki adapters` column `will_fire` now reflects the classification (Obsidian: `auto no` unless explicitly enabled). 10 new tests in `tests/test_raw_immutability.py`: guard passes / raises / force-bypasses / error message formatting, every AI adapter marked, every non-AI adapter marked, default selection skips non-AI, explicit-enable includes non-AI.

- **Dead-end pages get a Back-to-site link** (#268) — `site/graph.html` and every page under `site/prototypes/` used to be navigation dead ends — once you landed on one, the only way back was the browser back button. Graph viewer now has a `← Home` link in its header next to the search box (uses the existing `.control` button style so it fits the palette). Prototype state pages now ship a `← Back to site · All prototypes` sub-nav under the identification stripe. Both use `var(--text-muted)` so they don't compete with primary content. Two guardrail tests (`tests/test_prototypes_hub.py`, `tests/test_graph_viewer.py`) lock this in so future template refactors can't regress.

- **Slash-command rename: `/wiki-review` → `/wiki-candidates`** (#272) — the slash-command name now matches its CLI sibling (`llmwiki candidates …`). File moved via `git mv` so history is preserved; all 11 docs + test references updated; existing guardrail test `test_wiki_candidates_slash_command_exists` also asserts the old name is gone so docs can't regress. Skills registry picks up the new filename automatically on next session load.

- **Stale counts in user-facing docs** (#271) — README badge was stuck at `tests-1549 passing`; bumped to `tests-2162 passing`. `Version: v1.1.0-rc2` → `v1.1.0-rc3`. `__version__` in `llmwiki/__init__.py` and `pyproject.toml` synced to `1.1.0rc3`. CLI `lint` help text used to hard-code "11 lint rules"; now reads `len(REGISTRY)` at argparse-build time so the help always prints the live count (currently 15). Docstrings in `llmwiki/lint/__init__.py` and `llmwiki/lint/rules.py` no longer claim "11 rules"; they point callers at `len(REGISTRY)` as the source of truth. New guardrail test `test_no_stale_lint_rule_counts_in_user_docs` scans README / CLAUDE.md / slash-commands.md / docker.md for hard-coded "11 lint rules" / "13 lint rules" strings and flags any without a nearby historical-release citation. Regex accepts both `v0.9.0` and `v0.9.x`-style release references.

- **Synthesized pages never ship with empty `tags: []`** (#271 follow-up) — new `_derive_baseline_tags()` helper in `llmwiki/synth/pipeline.py` guarantees every synthesize output has at least one meaningful tag. Preserves raw-session tags; adds the project slug (when != "unknown"), a `session-transcript` / `claude-code` marker when missing, and a model-family bucket (`claude` / `gpt` / `gemini` / `llama`). Idempotent + dedup-safe. Seed entity pages `ClaudeSonnet4.md` and `GPT5.md` — the two public model pages shipped with the repo — gained explicit `tags:` lists (`ai-model, anthropic, claude, llm, frontier-model` / `ai-model, openai, gpt, llm, multimodal, frontier-model`) so the site's filter chips + graph viewer don't show them bare. 7 new tests in `tests/test_synth_pipeline.py` cover every branch.

### Added

- **Graph-viewer node context menu** (#305 · G-19) — right-click (or long-tap) any node in the interactive knowledge graph opens a keyboard-accessible context menu with five active actions: **Open page** (same as left-click), **Find neighbours (1-hop)** which dims every non-neighbour, **Copy slug**, **Copy wiki path**, **View references (CLI hint)** which copies `llmwiki references "<slug>"` to the clipboard. Two more actions — **Mark stale** and **Archive** — are present but disabled with a tooltip pointing at the future `llmwiki serve --edit` mode so the UI surface is visible without yet shipping the edit-mode server. Keyboard shortcuts while the menu is open: `Enter` → Open, `N` → neighbours, `C` → copy slug, `Escape` → close. Menu position clamps to the viewport (no off-screen). Clipboard API uses `navigator.clipboard.writeText` with a `document.execCommand('copy')` fallback for older browsers + private-mode. CSS inherits the existing theme palette (`var(--g-panel)` / `var(--g-border)` / `var(--g-text)`) so light + dark sync without hard-coded hex. ARIA: `role="menu"` on the container, `role="menuitem"` on each button, `aria-label="Node actions"`. Outside-click + Escape key close the menu. 19 tests in `tests/test_graph_context_menu.py`: all seven actions present, edit-only actions disabled, `role="menuitem"` count, `oncontext` handler wired, outside-click + Escape close, keyboard shortcut map, viewport clamping, neighbour-set algorithm, clipboard-fallback present, quote-escape for CLI hint, CSS theme-token inheritance, disabled-button style, rendered HTML contains the menu, `__GRAPH_JSON__` injection + existing handlers still work, 60 KB template-size budget.

- **Stale-reference detection + `llmwiki references` CLI + 15th lint rule** (#303 · G-17) — new `llmwiki/references.py` module builds a reverse-reference index over the wiki (who links to each target). New `llmwiki references <slug>` CLI enumerates referrers sorted by source path; `--with-dated-claims` flag also prints the offending "as of 2026-01-01" / "since v4.6" prose. New `stale_reference_detection` lint rule (rule #15) fires when (a) a source page has `last_updated` older than its target's `last_updated` AND (b) the source body contains at least one dated claim. The dated-claim guard keeps the rule from flooding the report with every old→new link (it only cares about links that commit to a specific moment in time). Regex matches `as of <date>`, `since <semver>`, `since <year>`, `(last checked <date>)`, `current as of <date>`, `through <year>` — both numeric (`2026-03-15`, `2026-03`) and spelled-out (`March 2026`). Broken wikilinks are never stale (target doesn't exist), and unparseable `last_updated` values are gracefully skipped rather than crashing. 49 tests in `tests/test_references.py`: regex branches (12 parametrized + multi-hit + context window), `_parse_date` edge cases (7 parametrized), `build_index` (target resolution, broken links, dedup, anchors, empty bodies, dated-claim preservation), `find_references_to`, `find_stale_references` (every required condition + broken link + malformed date), `format_references_table` (empty + sort order), lint rule wiring + fires/silent, CLI subprocess (help, prints referrers, empty result, missing wiki errors). Docs: `docs/reference/cli.md` documents the new `references` subcommand.

- **Tag-space curation — `llmwiki tag` family + 14th lint rule** (#301 · G-15, #302 · G-16) — new stdlib-only `llmwiki/tags.py` module + `llmwiki tag` CLI (five subcommands). `list` prints a sort-by-count table of every tag across `wiki/` (walks all pages except underscore-prefixed and `archive/`). `add <tag> <page>` appends to a page's frontmatter; idempotent (adding an existing tag is a no-op); can seed a brand-new frontmatter block on a raw markdown page. `rename <old> <new>` rewrites across every page with substring safety (`obs` → `observability` doesn't clobber `obsidian`) and a `--dry-run` that tells the caller what *would* happen without touching disk. `check` uses case-insensitive SequenceMatcher to flag near-duplicate tags (threshold defaults to 0.85, tuneable); identical tags in different cases (e.g. `Obsidian` vs `obsidian`) always surface at similarity 1.0. `convention` reports G-16 violations — projects using `tags:` or sources/entities/concepts/syntheses using `topics:`. Both inline list (`tags: [a, b]`) and block list (`tags:\n  - a\n  - b`) frontmatter forms are parsed + rewritten. New `TagsTopicsConvention` lint rule (14th overall) wires the same convention check into `llmwiki lint` so CI catches drift on every run. Depends on no new external deps. 45 tests across frontmatter parsing, discovery (skip archive/underscore), add/rename/check/convention, CLI subprocess, lint-rule registration + behaviour. Docs: `docs/reference/cli.md` now documents the full subcommand + flag table.

- **`llmwiki synthesize --estimate` now prints an incremental-vs-full-force breakdown** (#293 · G-07) — old output was a single dollar number that left users unsure whether it covered the whole corpus or just the delta since last run. New output reads state from `.llmwiki-synth-state.json` and shows four clear lines:

  ```
  Corpus:                785 sessions in raw/sessions/
  Synthesized (history): 314 already in wiki/sources/
  New since last run:    471

  Prefix: 3,944 tok  Model: claude-sonnet-4-6

  Incremental sync:  $15.96  (synthesize the 471 new session(s))
  Full re-synth:     $26.92  (--force — 785 session(s), 1 cache write + 784 hits)
  ```

  New `synthesize_estimate_report()` helper returns a plain dict so tests + downstream tooling can consume the numbers without parsing stdout. State-key matching tries bare-name, rel-path, full-str, and endswith-fallback so it survives the multiple keying conventions in the repo (the synth state uses `<project>/<file>.md` while some tests inject simpler keys). Invariant: `full_force_usd ≥ incremental_usd ≥ 0` — the CLI regression test parses both numbers out of stdout and asserts this. Custom model + output-tokens-per-call are pluggable via kwargs. Empty corpus prints `nothing new — this is a no-op` instead of silently returning. 18 new tests in `tests/test_synthesize_estimate.py` cover every bucket + CLI smoke + invariants. The two pre-existing cache tests updated to match the new output shape.

- **`llmwiki log` — structured query over `wiki/log.md`** (#299 · G-13) — new top-level CLI subcommand that parses the append-only operation log into structured events so you can ask "show me every sync from last week" without eyeballing the file. Flags: `--since YYYY-MM-DD`, `--operation sync,synthesize,lint,ingest,query,build` (comma-separated), `--limit N` (0 = unlimited), `--format {text,json}`. Builds on the existing `llmwiki/log_reader.py` module shipped in #308 for G-18, so no new parser plumbing. Output is newest-first by date (stable sort preserves same-day append order). Missing log returns rc=1 with a helpful message; invalid `--since` returns rc=2; empty filter result prints "No log entries match the filters." 9 new tests in `tests/test_cli_observability.py` cover missing file, text output ordering, operation filter, date filter, invalid-date error, JSON structure, limit clamp, empty-match message, end-to-end CLI.

- **`llmwiki sync --status` — observability reporter** (#289 · G-03) — non-destructive status flag on the existing `sync` subcommand. Prints last-sync timestamp (with "Nh ago" human delta), per-adapter counters table (`discovered / converted / unchanged / live / filtered / errored`), orphan state entries, and quarantine counts. `--recent N` adds the last N sync/synthesize log entries as a bonus view. Counters are now persisted into `.llmwiki-state.json` under `_meta` (with `last_sync` + schema version) and `_counters` (per-adapter dict) — written by every non-dry-run `convert_all` call. The `_`-prefix namespace guarantees these metadata keys never collide with portable adapter state keys (which are lowercase identifiers). State migration now preserves underscore-prefixed keys through legacy-to-portable rewrites so an existing `_meta` survives a version upgrade. 7 new tests: empty state, counter table rendering, quarantine integration, --recent surfaces log events, corrupt-state-file tolerated, short-circuit doesn't run a real sync, `_meta` preservation during migration.

- **Convert-error quarantine** (#300 · G-14) — new `llmwiki/quarantine.py` module (stdlib-only, ~220 lines). Every converter exception (`stat` failure, markdown read, PDF extract, jsonl render) is now recorded in `.llmwiki-quarantine.json` with `{adapter, source, error, first_seen, last_seen, attempts, extra}`. Key is `(adapter, source)` — re-running sync bumps `attempts` and updates `last_seen` + `error` without creating duplicate rows. Schema is versioned (`"version": 1`) and output is deterministically sorted for stable diffs. New CLI subcommand `llmwiki quarantine {list|clear|retry}` — `list --adapter NAME` filters, `clear --all` wipes everything, `clear <source>` clears one row (adapter-scoped with `--adapter NAME`), `retry` prints a re-sync plan without actually re-running. File is gitignored alongside `.llmwiki-state.json`. 38 tests (`tests/test_quarantine.py`) cover: schema version pin, load on missing/malformed/wrong-shape files, per-row malformed-entry tolerance, add/dedup/attempt-bump, extra-dict merging, empty-argument rejection, save determinism + version metadata + parent-dir creation, round-trip, clear_entry (single + adapter-scoped + missing is noop), clear_all (empty returns 0), list_entries sort + adapter filter, format_table (empty + long-error truncation + basename-only source), count_by_adapter aggregate, entry equality/hash by `(adapter, source)`, CLI subprocess tests (list empty/filter, clear without args errors, --help surfaces subcommands).

### Fixed

- **`llmwiki adapters` `configured` column was ambiguous** (#287 · G-01) — column values used to be `-` / `enabled` / `disabled`, which read as "adapter can't see anything" even when the adapter was finding 471 files on the next line. Renamed to `auto` (default — no explicit config), `explicit` (user set `enabled: true`), `off` (user set `enabled: false`). New `will_fire` column (`yes`/`no`) says at a glance whether the next `sync` will pick the adapter up. Footer drops the old "Adapters marked 'disabled' or '-'…" preamble in favour of a three-line column legend. New `_adapter_status()` helper is the single source of truth and is testable in isolation. 8 new tests cover every branch (auto, explicit, off, unavailable, malformed-config-row, legacy labels absent, new column headers present, `--wide` still works).

- **Converter silently dropped sub-agent sessions with non-int tool args** (#291 · G-05) — `summarize_tool_use` for the `Read` tool did `(offset or 0) + (limit or 0)` but sub-agent transcripts sometimes emit `offset` / `limit` as strings (`"10"`), triggering `TypeError: can only concatenate str (not "int") to str` and silently dropping the whole session (reproducible failure: `agent-ace0e851c84aaba7c.jsonl`). New `_coerce_int()` helper at the convert boundary accepts int/str/float, rejects bool (explicit — `True + 0` is a footgun) + None + garbage, handles unicode digits + overflow + whitespace. 24 parametrized + scenario tests in `tests/test_convert_state_and_coerce.py` pin the behaviour across every edge case. Fix is boundary-coerce only — the arithmetic downstream now always sees clean ints.

- **State-file portability** (#290 · G-04) — `.llmwiki-state.json` keys used to be absolute filesystem paths (`/Users/<name>/.claude/projects/…`), which meant moving the repo between machines invalidated every state entry and leaked the operator's home directory if the file were ever accidentally committed. New format is `<adapter>::<home-relative-path>` (e.g. `claude_code::.claude/projects/-Users-…/session.jsonl`). The `<adapter>::` prefix disambiguates between two adapters that can both see the same file. One-shot migration in `load_state()`: absolute-path keys get rewritten in place the first time a post-upgrade sync runs, using per-adapter path-signature hints (`.claude/projects/` → claude_code, `.codex/sessions/` → codex_cli, `Obsidian` → obsidian, etc.). Keys we can't confidently re-map are kept verbatim so no session gets accidentally re-processed. The migration persists to disk so subsequent loads are pure pass-throughs. Paths outside `$HOME` also pass through with their absolute form. 14 tests cover: home-relative formatting, POSIX separators on every platform, outside-home fallback, adapter-name scoping, unicode paths, legacy→portable migration for every known adapter, hint-miss passthrough, type coercion for malformed rows, idempotent re-migration, load on missing/corrupt/non-dict payloads, save determinism.

- **Gap sweep — 9 P0/P1/P2 bugs surfaced by end-to-end QA** (#288, #292, #294, #295, #296, #297, #298, #304, #306, #307) — single fix PR off `fix/gap-sweep-p0-p1` lands the quick-wins logged in the local `gaps.md` QA pass:

- **Gap sweep — 9 P0/P1/P2 bugs surfaced by end-to-end QA** (#288, #292, #294, #295, #296, #297, #298, #304, #306, #307) — single fix PR off `fix/gap-sweep-p0-p1` lands the quick-wins logged in the local `gaps.md` QA pass:
  - **G-06 · silent data loss from slug collisions** (#292) — `llmwiki/synth/pipeline.py` now writes `wiki/sources/<project>/<YYYY-MM-DD>-<slug>.md` instead of `<slug>.md`. Claude Code's auto-generated 3-word session slugs collide often (12× `flickering-orbiting-fern` in a real 797-session corpus) and the date-free output path silently overwrote earlier sessions — 63 pages vanished on one run. The date prefix preserves every session and keeps the filename stable across re-synthesizes. Regression test (`test_synthesize_date_prefix_prevents_slug_collisions`) seeds two same-slug-different-date sessions and asserts both land on disk.
  - **G-09 · `synthesize` didn't rebuild `wiki/index.md`** (#295) — new `_rebuild_index()` helper walks `wiki/sources/**/*.md` after each synth run and rewrites the `## Sources` section of `wiki/index.md` while **preserving every other hand-curated section** (Overview, Entities, Concepts, free-text). Previously a fresh synthesize left the index stale and `index_sync` lint flagged 703 errors per run. Test covers both "index exists with curated content" and "index missing — seed fresh" paths.
  - **G-10 · log-archive rotation produced frontmatter-less files** (#296) — `_auto_archive_log()` now seeds `---\ntitle: … / type: navigation / auto_generated: true / last_updated: …\n---\n` on the first write, so `frontmatter_completeness` lint stays green after rotation.
  - **G-11 · `duplicate_detection` emitted 76,963 pair warnings on a 714-page corpus** (#297) — rule rewritten to require **both** title similarity ≥ 0.95 **and** body overlap ≥ 0.80, and to scope source-page comparisons by `project` (two `CHANGELOG.md` files in different projects are no longer flagged). Cross-type pairs (source vs entity) are skipped entirely. The two existing unit tests (`test_exact_duplicates`, `test_similar_titles`) were updated to supply matching bodies; four new tests in `test_gap_fixes.py` pin the tuned behaviour.
  - **G-12 · `DummySynthesizer` fabricated 371 broken wikilinks** (#298) — every `[[mention]]` in the raw body used to be copied verbatim into `## Connections`, but those targets rarely existed as wiki pages. The dummy now emits one guaranteed-real connection (the project entity page, e.g. `[[AiNewsletter]]`) and surfaces raw mentions as plain text under a new `## Raw Mentions` section. Existing tests updated; `check-links` drops from 460 broken → baseline.
  - **G-18 · home "Recently updated" card was always empty without model pages** (#304) — new `llmwiki/log_reader.py` module (stdlib-only, 140 lines) parses `wiki/log.md` into structured `LogEvent` records with `parse_log()` + `recent_events(limit=10, operations={...})`. New `render_recent_activity()` in `changelog_timeline.py` renders the card from log events; `build.py` falls back to it when no model-changelog activity is available. Eight tests across `test_log_reader.py` + `test_gap_fixes.py`.
  - **G-20 · synthesize appended one log entry per page** (#306) — replaced with **one batched summary entry per invocation**: `## [date] synthesize | N sessions across M projects` + `- Processed/Created/Errors` bullets. Old behaviour produced 60+ lines per run and drowned `grep "^## \["` output.
  - **G-21 · slug normalisation leaked spaces + unsafe chars to disk** (#307) — new `_normalise_slug()` helper replaces `[\s/\\:*?"<>|]+` with `-` and collapses consecutive dashes (`"00 - Master Framework Index"` → `00-Master-Framework-Index`). Empty input returns the literal `"unknown"` rather than an empty filename. Unicode is preserved.
  - **G-02 · `llmwiki adapters` description column truncated to 40 chars** (#288) — new `--wide` flag disables the cap; default mode now auto-fits the description width to the terminal (min 40 cols) and drops a one-line `Pass --wide to see untruncated descriptions.` hint. `argparse` help string + `tests/test_gap_fixes.py` subprocess tests keep the flag discoverable.
  - **G-08 · log parse-ability when slugs contain spaces** (#294) — per-page stdout lines now use `synthesized: <project> → <filename>` (arrow separator) so `awk '{print $NF}'` doesn't truncate at the first space.

  9 net-new modules/tests, 1 refactored (`duplicate_detection`), 0 breaking changes. Full suite: **1931 passed, 10 skipped**.

### Added

- **Production documentation overhaul — editorial hub, 7 tutorials, 3 reference pages, docs-shell CSS, guardrail tests** (#265) — `docs/` goes from a fragmented pile to a single editorial entry point at `docs/index.md` (hub) with a seven-tutorial path (installation → first sync → Claude Code → Codex CLI → query → bring your vault → example workflows) plus three complete-coverage references (`docs/reference/cli.md` — every CLI subcommand + every flag + realistic examples, `docs/reference/slash-commands.md` — all 16 `/wiki-*` + governance commands, `docs/reference/ui.md` — every nav tab, palette shortcut, and site surface). New `docs/style-guide.md` locks the voice (minimalism + trust & authority, evidence-first, no marketing prose) and the mandatory tutorial skeleton (Time / You'll need / Result → Why → numbered Steps → Verify → Troubleshooting → Next). New `llmwiki/render/docs_css.py` (editorial CSS scoped under `.docs-shell` — 760 px column, 2.75 rem tutorial h1 / 3.5 rem hub hero, grid-based meta-strip with code-rendered values, hairline horizontal rules, zero drop shadows on content, inherits all brand-system tokens from #115, no hard-coded hex) and new `llmwiki/docs_pages.py` compiler that walks `docs/**/*.md` during `llmwiki build`: pages with `docs_shell: true` get the full editorial layout, everything else (adapter guides, deploy guides, reference docs) compiles as passthrough so every internal link resolves. `.md`-to-`.html` link rewriter runs post-conversion (`rewrite_md_links_to_html`) — markdown source keeps `.md` for GitHub rendering, compiled output has `.html`. Meta-strip renders inline backticks + links via `_inline_markdown`. New **Docs** tab in the main site nav between Graph and Prototypes. `README.md` surfaces the hub + per-tutorial quick-start table. Guardrails: `tests/test_docs_structure.py` (28 tests — mandatory sections, filename ↔ h1 number match, internal-link resolution, no raw `<script>`, CSS namespacing, no hard-coded hex) and `tests/test_reference_coverage.py` (9 tests — every CLI subcommand from `build_parser` must have a `## \`name\` — …` heading + a fenced-bash example, every `.claude/commands/*.md` file must have an `### \`/name\`` heading, the slash-count summary must match reality, every build-py nav key must appear in `ui.md`, the palette + keyboard shortcuts must stay documented). 97 editorial pages compile into `site/docs/`; preview at `http://127.0.0.1:8765/docs/index.html` after `llmwiki build && llmwiki serve`.

- **Vault-overlay mode** (#54) — new `llmwiki/vault.py` module lets the pipeline compile an existing Obsidian / Logseq vault **in place**, so users with hundreds of existing notes don't need to migrate to a fresh `raw/` + `wiki/` tree. `llmwiki sync --vault <path>` and `llmwiki build --vault <path>` resolve the vault, detect its format (Logseq wins on marker overlap so opening a Logseq vault in Obsidian once doesn't flip detection), and route all new entity/concept/source/synthesis/candidate writes inside the vault at the configured subpaths (default `Wiki/Entities/`, `Wiki/Concepts/`, etc.). `VaultLayout` is a frozen dataclass that teams override to match their existing convention (`Knowledge/People/`, `LLM/`, etc.). `vault_page_path()` splits on format: Obsidian/Plain use nested folders + bare-slug wikilinks (`[[RAG]]`), Logseq uses `pages/` with triple-underscore namespace filenames (`wiki___entities___RAG.md`) + namespace-aware wikilinks (`[[wiki/entities/RAG]]`). Non-destructive by default: `write_vault_page()` raises `FileExistsError` on a pre-existing page unless the caller passes `overwrite=True` (CLI `--allow-overwrite`); `append_section()` folds new info into a user-owned page under a `## Connections` heading and is idempotent (case-insensitive heading check so re-runs are no-ops). Slugs with unsafe filesystem characters (`<>:"|?*/\`) get sanitized to `-`; unicode slugs (`日本語`) pass through unchanged; empty / whitespace-only slugs raise ValueError. CLI validates the vault path up front and exits 2 with a readable error on missing / non-directory paths. `docs/guides/existing-vault.md` walks through the quick-start, format detection, write paths per format, layout overrides, round-trip edit-then-resync safety, Python API, and troubleshooting for the common failure modes. 52 tests.

- **Visual-regression baselines via SHA-256 hashing** (#113) — stdlib-only pixel-identical drift detection for approved UI surfaces. New `llmwiki/visual_baselines.py` module: `hash_png()` (SHA-256 in 64 KiB chunks, raises on missing file), `load_baselines()` / `save_baselines()` (diff-friendly indented + sorted JSON, accepts legacy `{filename: sha256}` string shape and the full `{sha256, size}` shape), `generate_baselines()` (walks every `.png` under a directory, uses relative paths so manifests are portable across clones, skips non-PNG files), `compare_against_baselines()` returning four disjoint buckets (`match` / `drift` / `new` / `missing`), `format_comparison()` for human-readable CLI output with per-bucket hints ("regenerate after review" for new, "prune or restore" for missing), `is_clean()` shortcut, plus the `BaselineStatus` + `ComparisonResult` + `BaselineEntry` TypedDicts. New `scripts/update-visual-baselines.sh` regenerates the committed manifest after a maintainer reviews drift. Docs in `docs/testing/visual-regression.md` explain why hashing beats perceptual diff (no runtime deps, forces deliberate baseline updates), the four-bucket verdict, the refresh workflow, CI wiring, and non-goals (no cross-browser / sub-pixel / animation-frame baselines). 36 tests.

- **Reader-first article shell** (#112) — Wikipedia-style encyclopedia layout scaffold for session pages (browse drawer + article header + utility bar + body + right rail with infobox / revisions / see-also / references). **Fully opt-in** per page via `reader_shell: true` frontmatter so existing 647 session pages render byte-identical today; gradual adoption happens in follow-up PRs. New `llmwiki/reader_shell.py` ships: `SHELL_FLAG_FIELD` constant + `is_reader_shell_enabled()` (accepts `True` / `1` / `"true"` / `"yes"` / `"on"` / `"1"` case-insensitively, every other value falls to existing path); `ShellSlots` dataclass where every field is optional so empty sections collapse cleanly; `extract_infobox_fields()` that auto-pulls known frontmatter (type, entity_type, project, model, lifecycle, cache_tier, confidence, last_updated, date) with human labels, formats confidence floats to 2 decimals, stringifies lists as comma-separated; `build_slots()` convenience factory; `render_article_shell()` emits a single `<div class="reader-shell">` block with fully HTML-escaped title / breadcrumbs / infobox / see-also / references / revisions (body_html stays trusted pipeline output); `ReaderShellCSS` class of namespaced classnames that tests + external CSS callers can reference. New `READER_SHELL_CSS` stylesheet appended to `llmwiki/render/css.py` — every selector scoped under `.reader-shell` so no existing selectors are redefined; three-column grid (240 drawer / body / 280 rail) with responsive breakpoints at 1100 px (drop drawer) and 760 px (stack rail). Inherits every color/font/radius/shadow token from the brand system (#115) rather than inventing new ones — a guardrail test confirms every `var(--…)` the shell uses is defined in the main stylesheet. Accessibility: breadcrumbs + infobox + utility bar + rail sections all carry proper `aria-label` / `aria-current`; empty drawer shows explanatory text instead of blank region. Docs in `docs/reference/reader-shell.md` cover the layout, every slot's source, the Python API, CSS namespacing rules, responsive behaviour, XSS safety guarantee, and non-goals (no revision-tracking pipeline yet, no auto-parse of `## Connections` for see-also, no bulk conversion of existing pages). 50 tests (`tests/test_reader_shell.py`): opt-in truthy/falsy/missing paths, infobox extraction for every supported field including list → comma-separated / bool → yes-no / float → two-decimal formatting, `build_slots` auto-extraction + caller-list passthrough, render with empty / escaped-title / malicious-infobox / trusted-body / breadcrumbs-with-aria-current / utility-bar-present-or-hidden / empty-sections-collapse / infobox-as-dl / see-also-and-references / revisions-with-time-tag / drawer-empty-placeholder-vs-links / subtitle / single-wrap-block; CSS guardrails (non-empty, selectors namespaced, variables defined in main CSS, main CSS contains the append, 1100+760 breakpoints present); doc guardrail; non-regression (default path unchanged, CSS append is additive).


- **Tree-aware search routing** (#53) — new `llmwiki/search_tree.py` module computes per-page heading-depth stats at build time and flips the client-side search palette between flat and tree modes based on the corpus. `heading_depths()` regex-scans each body for `^#{1,10}[ \t]+\S` (guards against `#hashtag` / newline-spanning matches) and returns `(max_depth, count_by_depth)` bucketed up to h6. `annotate_entry_headings()` mutates the search-index entry in place with JSON-safe string-keyed counts so the chunks stay plain JSON. `decide_search_mode(entries, override)` applies the TreeSearch-paper heuristic: flip to tree iff ≥ 30 % of pages have heading depth ≥ 3 (the eligibility threshold). Override takes three values via the new `llmwiki build --search-mode {auto,tree,flat}` CLI flag — `auto` runs the heuristic, `tree` / `flat` force the mode even on shallow / deep corpora, unknown values fall back to auto with no crash. `search_index_footer_badge()` produces a short "tree mode · 64% deep pages" label the palette footer shows so users can see why their corpus picked the mode it did. `build_search_index()` now writes `_mode`, `_tree_eligible_ratio`, `_mode_badge` at the top level of `search-index.json` and stamps `heading_max_depth` + `heading_count_by_depth` on every session chunk entry (no full heading text — the client reads the page HTML when the user expands a tree hit, keeping chunks small). Build log now prints e.g. `wrote search-index.json (7 KB meta) + 30 chunks (904 KB total) · tree mode · 64% deep pages`. On the live repo corpus this flips to tree. 36 tests (`tests/test_search_tree.py`): every heading_depths branch (empty / no headings / shallow / deep / hash-tag noise / bucket cap), annotate preserves existing keys + is JSON-safe, all decide_search_mode branches (empty / below / at / above threshold, every override including invalid + case-insensitive, missing-key entries), footer badge rendering, build-site + build_search_index signatures expose `search_mode`, CLI rejects unknown values, chunks carry the stats, top-level `_mode` is stamped.

- **Static prototype hub** (#114) — new `llmwiki/prototypes.py` publishes `site/prototypes/` during every `llmwiki build` with six reviewable UI states for UX iteration: `page-shell` (layout audit skeleton), `article-anatomy` (annotated session page showing every slot with orange callouts on each landmark), `drawer-browse` (faceted project browse drawer), `search-results` (command palette mid-query with 10+ results), `empty-search` (no-match state with fallback copy + escape hatches), `references-rail` (article with sticky right-hand `## Connections` rail populated from inbound/outbound wikilinks + related pages). Every state ships as a standalone HTML file that inherits the live site's stylesheet so visual fidelity is 1:1, and carries a 4 px `#7C3AED` identification stripe + "Prototype — not a live page" meta block so reviewers can't mistake them for real pages. Main site nav gains a **Prototypes** tab between Graph and Changelog. XSS-defensive: `render_state()` HTML-escapes the title and description slots. 26 tests (`tests/test_prototypes_hub.py`): exactly six states ship; frozen-dataclass invariant; URL-safe kebab slugs unique + non-empty descriptions > 20 chars; every expected slug present; every rendered state carries DOCTYPE + head + body + `../style.css` link + purple stripe + meta block; title XSS-escape; hub index lists every state + back-link to site; `build_prototype_hub()` writes all files idempotently; raises when `site_dir` missing; build.py wires `build_prototype_hub()` into `build_site()` and adds the nav link.

- **L1/L2/L3/L4 cache-tier frontmatter** (#52) — pages can now carry an optional `cache_tier:` field that tells `/wiki-query` how eagerly to load them during context build. L1 (always loaded, ≤ 5 k-token budget) for index/overview/CRITICAL_FACTS, L2 (summary pre-load, ≤ 20 k) for hot entities, **L3 (on-demand, default)** for the vast majority — behavior-identical to today when the field is absent, L4 (archive) for deprecated pages `/wiki-query` should skip unless explicitly named. New `llmwiki/cache_tiers.py` module: `parse_cache_tier()` with graceful fallback to L3 on missing/invalid input, `is_preloaded()`, `summary_excerpt()` that pulls the `## Summary` section (regex, case-insensitive, falls back to first N chars of body), `estimate_tier_tokens()` for aggregate budget checks, `tier_badge_class()` for site UI, `conflicting_tier_reason()` for lint hints, `TIER_METADATA` + `PRELOADED_TIERS` constants. 13th lint rule `CacheTierConsistency` flags invalid tier values, L1 pages with zero inbound links (wasted preload), L4 pages with ≥ 3 inbound links (archived-but-hot), `status: archived` pages whose `cache_tier` isn't L4, and L1 pools that blow past the 5 k token budget. Docs in `docs/reference/cache-tiers.md` explain the four tiers with a how-to-choose table, the loading flow, and the Python API. 38 tests (`tests/test_cache_tiers.py`): constants + metadata invariants, all parse_cache_tier branches, preloaded/badge/budget helpers, summary_excerpt cases (with heading / without / case-insensitive / truncation / empty), estimate_tier_tokens aggregate + L2 summary-only path, conflicting_tier_reason for every trigger, lint rule end-to-end for invalid-tier / wasted-L1 / archived-mismatch / budget-exceeded / healthy-wiki-silent paths, registry registration, rule count bumped from 12 → 13.

- **Editorial brand system documentation** (#115) — new `docs/design/brand-system.md` is the canonical reference for the visual system: typography (Inter + JetBrains Mono, no bundled web fonts, line-height 1.7 for prose), color palette (light + dark variants of the full `--bg-*` / `--text-*` / `--border-*` / `--accent-*` tokens, WCAG 2.1 AA minimum, accent `#7C3AED` is the through-line), elevation (two shadow steps + single 8 px radius + 4/6 px variants for smaller elements), motion (boring-by-design timings, `prefers-reduced-motion` honored, no auto-play / no scroll hijacking), spacing rhythm (2/4/8/12/16/24/32–48 px steps), export consistency (static HTML / graph viewer / future PDF / Marp / QMD / Obsidian all inherit the same tokens), social preview specs, and an explicit do/don't rulebook. 25 tests (`tests/test_brand_system_doc.py`) keep the doc + `llmwiki/render/css.py` aligned: every palette token mentioned in the doc must still be defined in CSS, typefaces + `--radius` + `prefers-reduced-motion` guard must stay in both sides, the `#7C3AED` accent through-line can't drift, and the doc must cover every core section.

- **Reader API contract documentation** (#116) — new `docs/reference/reader-api.md` locks the JSON/HTML/TXT shape the future hosted/SPA reader will meet, freezing it now so refactors of `llmwiki/build.py` can't silently break browser extensions, Raycast plugins, or downstream LLM agents that consume the static site. Catalogues every path `llmwiki build` already writes (`.html` / `.txt` / `.json` per-page siblings, `llms.txt`, `graph.jsonld`, `search-index.json` + chunks, `manifest.json`, `sitemap.xml`, `rss.xml`, `robots.txt`, `ai-readme.md`) and maps each future endpoint (`/api/v1/bootstrap`, `/api/v1/article`, `/api/v1/search`, `/api/v1/sync`) 1:1 to an existing file emission so nothing about the content pipeline needs to change to serve it. Documents the eight data-model invariants (slugs stable across rebuilds, UTC ISO-8601 timestamps, cache_tier enum, lifecycle enum, confidence in [0,1], entity_type enum, wikilinks resolve to slugs not URLs, frontmatter-is-authoritative) and the versioning discipline (additive changes safe, renames are breaking + bump to /v2/ with /v1/ kept alive one minor). 12 tests (`tests/test_reader_api_doc.py`) keep the contract honest: every `Shipped today` path must correspond to a real source emission grep-able in `llmwiki/*.py`, every enum claimed in the invariants section must match the live module (cache_tier, lifecycle, entity_type), every relative doc link must resolve, the four endpoint areas (bootstrap/article/search/sync) must all be present, and the `/sync` endpoint must be flagged as internal-only.

- **Homebrew tap kit** (#102) — polished the existing `homebrew/llmwiki.rb` formula (bumped URL to `v1.0.0`, refreshed comment block), added `scripts/bump-homebrew-formula.sh` to fetch the release tarball and rewrite `url` + `sha256` from any semver tag (macOS `sed -i ''` and Linux `sed -i -E` branches both covered; rejects non-semver input with a clear error), wrote `docs/deploy/homebrew-setup.md` walkthrough (one-time tap-repo creation, first-time install flow, on-every-release flow, optional auto-bump via `HOMEBREW_TAP_TOKEN` secret, troubleshooting for 404 tarball / brew test failures / class-name mismatches / stale SHA after force-push), and shipped `.github/workflows/homebrew-bump.yml` that auto-regenerates the formula on every `v*.*.*` tag push and — if the secret is configured — clones `Pratiyush/homebrew-tap`, commits the new formula, and pushes. Without the secret the workflow still runs the bump and prints the new formula content so you can copy-paste (no red checks on unconfigured repos). 21 tests (`tests/test_homebrew_tap.py`) keep the plumbing aligned: formula must keep the right class name / URL pattern / SHA shape / `test do` block / python@3.12 dependency; bump script must be executable and reject bad input; workflow must trigger on version tags + support manual dispatch + gracefully skip without the secret; doc must cover repo-creation prefix rule, release flow, auto-bump path, troubleshooting, and cross-link the PyPI sibling.

- **PyPI publishing kit** (#101) — new `docs/deploy/pypi-publishing.md` walkthrough covers the one-time manual setup on pypi.org (reserve project name, add GitHub as trusted publisher with `owner=Pratiyush` / `repo=llm-wiki` / `workflow=release.yml` / `env=release`, create the `release` GitHub environment, flip `PYPI_PUBLISHING=true` variable, cut a signed tag, verify `pip install` from a clean venv) plus a troubleshooting section for the three real-world failure modes (`publish` silently skipped, `invalid-publisher`, `403 Forbidden`). New `scripts/check-release-artifacts.sh` runs the `python -m build` + `twine check` sequence locally so metadata errors surface before a tag push. `.github/workflows/release.yml` comment block refreshed to point at the new doc. 14 tests (`tests/test_release_pipeline.py`) keep the plumbing honest: workflow must use OIDC + remain gated on `PYPI_PUBLISHING`, must trigger only on `v*.*.*` tags, environment name must match the doc, `pyproject.toml` must carry PEP 440 version matching `__version__`, doc must document all three failure modes, helper script must be executable and actually run `twine check`.

- **CI badges + demo refresh** (#129) — README badge block now surfaces the four key workflows (`ci.yml`, `link-check.yml`, `wiki-checks.yml`, `docker-publish.yml`) in addition to the existing License / Python / Version / Tests / agent-compatibility shields. Version badge bumped to `v1.1.0-rc2` and test-count badge refreshed to `1549 passing`. Demo recording script (`scripts/demo-record.sh`) extended to showcase v1.1 additions: `synthesize --estimate` (#50) cost preview and `candidates list` (#51) review queue. New `tests/test_readme_badges.py` (10 tests) guards against future rot: every workflow-badge URL must resolve to a real `.github/workflows/*.yml` file; the version badge must match `llmwiki.__version__` (with shields-format vs PEP 440 normalization); the test-count badge must stay above 1,000; the demo GIF must exist and be embedded in the README; the demo script must still cover the v1.1 features.

- **`__version__` bumped to `1.1.0rc2`** — both `llmwiki/__init__.py` and `pyproject.toml` now track the latest shipped tag. Previously stuck at `1.0.0` even after the v1.1.0-rc1 / v1.1.0-rc2 tags shipped.

### Fixed

- **9 broken external links flagged by lychee CI** (#239) — one weekly link-check scan surfaced a batch of dead/missing references:
  - `docs/competitor-landscape.md`: `rewind.ai` domain errors; delinked and noted the Limitless.ai rebrand.
  - `docs/framework.md`: `../.framework/Framework.md` pointed at a gitignored local file; delinked and annotated as a local-only reference.
  - `README.md`: `docs/adapters/copilot-chat.md` and `docs/adapters/copilot-cli.md` collapsed into the existing `docs/adapters/copilot.md` (the combined adapter doc already covers both modes).
  - `README.md`: 5× 404 release tag links (`v0.5.0` / `v0.6.0` / `v0.7.0` / `v0.8.0` / `v0.9.0`) — those standalone releases were never published; work shipped consolidated under `v0.9.x`. Collapsed into one row that explains the gap, and extended the table forward with the actually-shipped `v0.9.5` / `v1.0.0` / `v1.1.0-rc1` / `v1.1.0-rc2` rows so the version history is current.
- **`StaleCandidates` lint rule crashed with `NameError: name 'Path' is not defined`** (#51 follow-up) — the rule used `isinstance(page_path, Path)` without importing `Path`, so the `Lint + build seeded wiki` GH Actions job crashed on every push after #51 landed. Added `from pathlib import Path` inside the method (matching the existing lazy-import pattern). Regression test now exercises the rule against a seeded tmp_path wiki.
- **`tests/test_candidates.py` rejected by Python 3.9** (#51 follow-up) — line 55 nested an f-string with `\n` inside an outer f-string expression; Python 3.9 rejects backslashes inside f-string parts (only 3.12+ permits it), breaking `lint-and-test (3.9)` CI. Extracted the default body into a local variable before interpolation.

### Added

- **Interactive force-directed knowledge graph viewer** (#118) — upgraded `llmwiki/graph.py`'s HTML template into a full interactive viewer per Karpathy's spec. New capabilities on top of the existing vis-network force layout: **live search** input in the header filters nodes by label/id (dims non-matches); **click-to-navigate** opens the wiki page in a new tab, rewriting `wiki/entities/Foo.md` → `entities/Foo.html`; **stats overlay** (bottom-right panel) shows page/edge/orphan counts, average connections, and top-5 hubs; **orphan highlighting** draws a red border (3 px) around nodes with zero inbound links; **cluster toggle** groups nodes by type (sources / entities / concepts / syntheses) and un-clusters on re-click; **dark/light theme toggle** that mirrors the main site's `localStorage.theme` key — both palettes drive the same CSS custom properties so the viewer follows the site without a rebuild; **offline fallback notice** if vis-network CDN fails to load. New `copy_to_site()` helper wires the viewer into the static site build so `python3 -m llmwiki build` now writes `site/graph.html` and the main site nav exposes a "Graph" link between "Compare" and "Changelog". Template is XSS-defensive: stats panel uses `escapeHtml()` on user-supplied labels and `write_html()` escapes literal `</script>` in the embedded JSON payload. 25 tests cover: graph builder edge cases (orphans, broken edges, alias-pipe wikilinks, README exclusion), every interactive feature (search input, click handler, stats overlay ids, cluster toggle, theme-toggle + localStorage, CSS-var theming, orphan highlight, offline notice, legend), `write_html()` JSON injection, `write_html()` `</script>` escaping, `copy_to_site()` (writes, returns None on empty wiki, rebuilds graph when omitted), site-nav integration, and a 25 kB template-size budget guardrail.

- **Prompt caching + batch API scaffold** (#50) — new `llmwiki/cache.py` module lands the plumbing for Anthropic `cache_control: {type: "ephemeral"}` usage on the stable ingest prefix (CLAUDE.md schema + `wiki/index.md` + `wiki/overview.md`). Public surface: `make_cached_block()`, `make_plain_block()`, `CachedPrompt` (frozen dataclass with `stable_prefix` / `dynamic_suffix`), `build_messages()` that emits the Anthropic-shaped message array with the header on the prefix block only. Cost preview: `estimate_tokens()` (char/4 heuristic, stdlib-only — no tokenizer dep), `estimate_cost()` returning a `CostEstimate` with per-bucket (prefix / fresh / output) breakdown, `format_estimate()` for the `--estimate` CLI output, `warn_prefix_too_small()` that flags prefixes below the 1024-token cache floor, `MODEL_PRICING` rate card for Sonnet 4.6 / Haiku 4 / Opus 4 (input, cached_input, cache_write, output USD/MTok). Batch state persistence: `BatchJob`, `BatchState`, `load_batch_state()`, `save_batch_state()`, `add_pending()` (dedup by batch_id), `mark_completed()` — all round-tripped through `.llmwiki-batch-state.json` (gitignored). New `llmwiki synthesize --estimate` CLI flag walks the discovered raw sessions, prices the batch assuming the first call is a cache write and the rest are hits, prints a line-item breakdown plus total. Docs: `docs/reference/prompt-caching.md`. 49 tests cover: cache-block shape, CachedPrompt empty-edge cases, build_messages structure, token/cost math (invariant: cached_input < input for every model, breakdown sums to total, rejects unknown models + negative tokens), batch-state round-trip, `add_pending` dedup, CLI wiring.

- **Ollama backend scaffold for local LLM synthesis** (#35) — new `llmwiki/synth/ollama.py` delivers the `OllamaSynthesizer` backend against the existing `BaseSynthesizer` contract. Stdlib-only HTTP via `urllib` (no new dependency). Configurable through `sessions_config.json` → `synthesis.backend = "ollama"` with `model` / `base_url` / `timeout` / `max_retries` fields (defaults: `llama3.1:8b` at `http://127.0.0.1:11434`, 60s timeout, 3 retries with exponential backoff). Privacy-by-default: loopback host only; a warning logs once if the user points the backend at a non-local host. `is_available()` probes `/api/tags` so callers can branch before long synthesis runs. Graceful error handling: `OllamaUnavailableError` (connection refused / DNS failure — no retries, caller skips), `OllamaHTTPError` (non-2xx after retries), `OllamaError` (non-JSON body, non-string response field). New `resolve_backend()` in `pipeline.py` selects backend from config (`dummy` | `ollama`); unknown names fall back to dummy with a warning. New `llmwiki synthesize [--check | --dry-run | --force]` CLI subcommand surfaces backend status without running synthesis. 43 tests (mocked HTTP — no network in CI): config parsing, URL construction, availability probing, retry + backoff on 5xx and socket timeout, no-retry on 4xx / connection refused, non-JSON response handling, unicode round-trip, curly-brace-safe prompt rendering, CLI registration, resolver fallback.

- **`wiki/candidates/` approval workflow** (#51) — new `llmwiki/candidates.py` module with `list`, `promote`, `merge`, `discard`, and `stale_candidates` primitives. New pages from `/wiki-ingest` that represent brand-new entities/concepts can now land in `wiki/candidates/<kind>/<slug>.md` with `status: candidate` instead of going straight into the trusted wiki. `/wiki-review` slash command (`.claude/commands/wiki-review.md`) + `llmwiki candidates <action>` CLI walk through the queue. Merge folds the candidate's body under a `## Candidate merge — <date>` heading in the target and archives the source. Discard moves to `wiki/archive/candidates/<timestamp>/` with a timestamped `.reason.txt` audit file. New `stale_candidates` lint rule (12th overall) flags candidates sitting idle > 30 days. 34 tests cover: all 4 action paths, frontmatter status rewrite, staleness computation, kind inference, error handling.

### Refactored

- **Split `llmwiki/build.py` (3,378 → 1,799 lines)** (#217) — new `llmwiki/render/` package with `css.py` (682 lines) and `js.py` (937 lines) housing the previously-inline CSS and JS constants. `build.py` re-exports both for backwards compatibility, so external imports `from llmwiki.build import CSS` still work. Build output verified byte-identical to pre-refactor (same HTML hash). 18 new tests verify byte equivalence, re-export, and content integrity (theme vars, dark mode, command palette, search-index loading). Zero behavior change.

### Added

- **Docker container + GHCR publish workflow** (#123) — fully fleshed-out Docker deployment. `Dockerfile` now uses OCI-standard labels, runs as non-root `app` user (UID 1000 for host-volume compat), owns the `/wiki` mount point, and defaults to `serve --host 0.0.0.0 --port 8765 --dir site`. `docker-compose.yml` pulls from `ghcr.io/pratiyush/llm-wiki:latest` by default with a `build: .` fallback, bind-mounts `raw/`, `wiki/`, `site/` on the host and `examples/` read-only, adds a healthcheck and `restart: unless-stopped`. New `.github/workflows/docker-publish.yml` builds multi-arch (amd64 + arm64) on every tag push and publishes to GHCR with cache reuse across builds. `docs/deploy/docker.md` covers quick-start, CLI-in-container usage, volume mapping, image details, and troubleshooting. README deployment-targets section expanded with Docker + Vercel/Netlify entries. 31 tests.

- **OpenCode / OpenClaw adapter** (#43) — new `llmwiki/adapters/opencode.py`. Discovers `.jsonl` sessions under `~/.config/opencode/sessions/` (Linux), `~/Library/Application Support/opencode/sessions/` (macOS), and `%APPDATA%/opencode/sessions/` (Windows), plus the equivalent `openclaw/` paths. `normalize_records()` translates OpenCode's `{role, content}` records into the Claude-style `{type, message: {role, content}}` that the shared renderer expects; `tool` role maps to `user` type while preserving the original role. Project slug derivation handles both nested (`<project>/<session>.jsonl`) and flat (`<project>-<session>.jsonl`) layouts. 23 tests.

- **ChatGPT conversation-export adapter** (#44) — new `llmwiki/adapters/chatgpt.py`. Reads `conversations.json` from a user's ChatGPT export (Settings → Data Controls → Export), linearizes the parent→children mapping to recover the active conversation chain, extracts messages with roles + text, renders as frontmatter-tagged markdown. Disabled by default (opt-in via `chatgpt.enabled: true` in config). 28 tests.

- **Shell completion for bash / zsh / fish** (#216) — new `llmwiki/completion.py` + `llmwiki completion <shell>` CLI command. Walks the argparse tree at runtime to enumerate every subcommand + its top-level flags, emits a working completion script. Stdlib-only (no argcomplete dep). Install: `llmwiki completion bash > ~/.bash_completion.d/llmwiki` (or equivalent for zsh / fish). 17 tests.

- **`.editorconfig` + weekly lychee link checker** (#215) — new `.editorconfig` at repo root enforces consistent indent/line-endings across editors (Python 4-space, YAML/JSON/TOML 2-space, Makefiles tab, Windows `.bat` CRLF). New `lychee.toml` + `.github/workflows/link-check.yml` scans README, CHANGELOG, `docs/`, and `examples/` weekly (Sun 03:00 UTC) for broken external links. Creates/updates a tracking issue on failure instead of blocking CI. Personal `wiki/` and `raw/` paths excluded; `site/` skipped (already handled by `llmwiki check-links`). 22 tests.

### Changed

- **Public seed entities enriched with v1.0 metadata** (#140) — `wiki/entities/ClaudeSonnet4.md` and `wiki/entities/GPT5.md` (the two public AI-model seed entities shipped with the repo) now carry `confidence`, `lifecycle`, `entity_type: tool` fields matching the v1.0 schema. Computed confidence: 0.56 for each (no source_count bump since they're structured schema entities with `sources: []`; quality gets "official" due to `entity_kind: ai-model`, recency is current, cross-refs are 0 since no other public wiki pages link to them).

- **PR template upgraded to 15-box pre-merge checklist** — inspired by the Translately platform's contribution rules. New boxes: one intent, breaking-change flagging, UI verified in light AND dark mode (with screenshots), a11y verified (WCAG 2.1 AA minimum), commits GPG-signed with no AI co-author trailers, reviewer reads every changed line. `CONTRIBUTING.md` updated with matching conventional-commit type table (9 types now vs 5 before), 500-line PR size limit, signed-commit branch protection rule. 21 new tests lock the checklist shape.

### Added

- `llmwiki/tag_utils.py` — shared tag-parsing module. Consolidates the byte-identical `_parse_tags_field()` + `NOISE_TAGS` that were duplicated in `categories.py` and `search_facets.py`. 19 tests covering parsing, noise filtering, deterministic scan order, and backwards-compat re-exports.

### Changed

- `examples/scheduled-sync-templates/` — moved from `docs/scheduled-sync/`. The `llmwiki schedule` CLI (v1.0) generates these dynamically from config; the static files are now kept as reference templates in `examples/` alongside other config samples. README in the new folder explains the preferred generator workflow. README + docs/scheduled-sync.md + docs/content-drafts/blog-tutorial.md updated to point at the new path.
- `docs/i18n/README.md` — added a `!NOTE` admonition calling out that the zh-CN/ja/es translation scaffolds have not been maintained since v0.3. Status column relabeled from "scaffold (v0.3)" to "stale scaffold (v0.3)".

### Removed

- `.github/ISSUE_TEMPLATE/bug_report.md` — superseded by `bug_report.yml`
- `.github/ISSUE_TEMPLATE/feature_request.md` — superseded by `feature_request.yml`
- Duplicated tag-parser code in `categories.py` and `search_facets.py` (now both `from llmwiki.tag_utils import ...`)

## [1.0.0] — 2026-04-16

**Theme:** v1.0 — Production-ready Obsidian integration. llmwiki graduates from a session-archive tool into a full LLM-maintained knowledge base with quality metrics, lifecycle states, Obsidian-native UX, and a 12-tool MCP server.

### Headline features

- **Obsidian-native experience** — `link-obsidian` CLI symlinks the project into an Obsidian vault; 4 Templater templates for creating pages with one keystroke; Dataview dashboard (10 queries); two-way editing verified by tests; integration guide at `docs/obsidian-integration.md`
- **Quality & governance** — 4-factor confidence scoring with Ebbinghaus decay per content-type; 5-state lifecycle machine (draft → reviewed → verified → stale → archived) with 90-day auto-stale; 11 lint rules (8 structural + 3 LLM-powered); Auto Dream MEMORY.md consolidation at 24h+5-session thresholds
- **Multi-agent support** — `llmwiki install-skills` mirrors `.claude/skills/` into `.codex/skills/` and `.agents/skills/`; AGENTS.md with `wiki_path` directive for cross-project reference; 9 navigation files (hints, hot, MEMORY, SOUL, CRITICAL_FACTS + per-project hot caches)
- **12-tool MCP server** — added `wiki_confidence`, `wiki_lifecycle`, `wiki_dashboard`, `wiki_entity_search`, `wiki_category_browse` to the existing 7
- **New adapters** — meeting transcripts (VTT/SRT), Jira REST API, configurable Obsidian Web Clipper intake with pending ingest queue
- **Ops automation** — rich structured log format with 50KB auto-archival; configurable auto-build on sync; configurable scheduled sync (`llmwiki schedule` generates launchd/systemd/Task Scheduler files); CI wiki-checks workflow runs lint + build on every PR; enhanced static search with confidence/entity_type/lifecycle facets
- **Taxonomy & schema** — 7 entity types (person, org, tool, concept, api, library, project); flat raw/ naming `YYYY-MM-DDTHH-MM-project-slug.md`; category index generator (Dataview + static modes); `_context.md` stubs in every wiki subfolder

### Added

- `link-obsidian` CLI command (#132)
- 4-factor confidence scoring module (#135)
- 5-state lifecycle machine with auto-stale (#136)
- `llmbook-reference` bidirectional Claude Code skill (#138)
- 9 navigation files (#134)
- 7 entity types in frontmatter schema (#137)
- Flat raw/ naming — `YYYY-MM-DDTHH-MM-project-slug.md` (#141)
- Pending ingest queue for SessionStart hook (#148)
- `_context.md` stubs for all 6 wiki subfolders (#150)
- Meeting transcript adapter VTT/SRT (#146)
- Jira REST API adapter (#147)
- Configurable Web Clipper intake path (#149)
- Rich structured log format with auto-archival (#133)
- All 11 lint rules — 8 basic + 3 LLM-powered (#155)
- Auto-build on sync + configurable lint schedule (#157)
- Auto Dream for MEMORY.md consolidation (#156)
- Full Dataview dashboard template (#153)
- Category page generator — Dataview + static modes (#154)
- Obsidian Templater templates for all 4 page types (#152)
- Obsidian integration guide (#151)
- 5 new MCP tools: confidence, lifecycle, dashboard, entity search, category browse (#159)
- Adapter config validation (#177)
- Multi-agent skill installer (#160)
- Enhanced static site search with facets (#161)
- Configurable scheduled sync task generator (#162)
- CI wiki-checks workflow (#163)
- End-to-end setup guide tutorial (#120)
- Two-way Obsidian editing verification tests (#158)
- 53 edge case tests for Sprint 1 modules

### Changed

- README refresh (#122) — v0.9.4 → v1.0.0 state, new sections for Quality & Obsidian features, updated roadmap for v1.0/v1.1/v1.2
- Light-mode polish (#119) — darker borders, card shadows, visible heatmap level-0, less saturated tool bars, grounded nav
- Consistency audit — `_context.md` normalized to `type: context`, label hygiene (conventional-commit canonical set), test file rename

### Fixed

- Synthesis pipeline writes to real `wiki/log.md` during tests (#131)
- Personal data removed from tracked wiki navigation files (#173)
- Pipeline robustness — sigstore pinned to @v3.3.0, release-drafter restricted to master pushes, Pages deploy not triggered on tag pushes, PyPI publish gated on `PYPI_PUBLISHING` variable

### Security

- Removed email, paths, and workflow preferences from tracked wiki nav files
- `raw/` + `wiki/*` content directories remain gitignored; `examples/demo-sessions/` is the only data shipped

### Stats

- 23 PRs merged across Sprints 1–4 (PR #166–#210)
- 1206 tests passing on Python 3.9 + 3.12
- 8 signed tags: v0.9.1–v0.9.5 + v1.0.0
- All commits GPG-signed by the maintainer

## [0.4.0] — 2026-04-08

**Theme:** AI + human dual-format. Every page ships both as HTML for humans AND as machine-readable `.txt` + `.json` siblings for AI agents, alongside site-level exports that follow open standards (`llms.txt`, JSON-LD, sitemap, RSS).

### Added

#### Part A — AI-consumable exports (`llmwiki/exporters.py`)

- **`llms.txt`** — short index per the [llmstxt.org spec](https://llmstxt.org) with project list, machine-readable links, and AI-agent entry points
- **`llms-full.txt`** — flattened plain-text dump of every wiki page, ordered project → date, capped at 5 MB for pasteable LLM context
- **`graph.jsonld`** — schema.org JSON-LD `@graph` representation with `CreativeWork` nodes for the wiki, projects, and individual sessions, all linked via `isPartOf` relations
- **`sitemap.xml`** — standard sitemap with `lastmod` timestamps and priority hints
- **`rss.xml`** — RSS 2.0 feed of the newest 50 sessions
- **`robots.txt`** — with explicit `llms.txt` + `sitemap.xml` references for AI-agent-aware crawlers
- **`ai-readme.md`** — AI-specific entry point explaining navigation structure, machine-readable siblings, and MCP tool surface
- **Per-page `.txt` siblings** next to every `sessions/<project>/<slug>.html` — plain text version stripped of all markdown/HTML for fast AI consumption
- **Per-page `.json` siblings** with structured frontmatter + body text + SHA-256 + outbound wikilinks — ideal for RAG or structured-data agents
- **Schema.org microdata** on every session page (`itemscope`/`itemtype="https://schema.org/Article"` + `headline` + `datePublished` + `inLanguage`)
- **`<link rel="canonical">`** on every session page for SEO and duplicate-indexing prevention
- **Open Graph tags** (`og:type`, `og:title`, `og:description`, `article:published_time`)
- **`<!-- llmwiki:metadata -->` HTML comment** at the top of every session page — AI agents scraping HTML can parse metadata without fetching the separate `.json` sibling
- **`wiki_export` MCP tool** (7th tool on the MCP server) — returns any AI-consumable export format by name (`llms-txt`, `llms-full-txt`, `jsonld`, `sitemap`, `rss`, `manifest`, or `list`). Capped at 200 KB per response.

#### Part B — Human polish

- **Reading time estimates** on every session page (`X min read` in the metadata strip)
- **Related pages panel** at the bottom of session pages (3-5 related sessions computed from shared project + entities, all client-side from `search-index.json`)
- **Activity heatmap** on the home page — SVG cells with per-day intensity gradient
- **Mark highlighting** support (`<mark>` styled with the accent color) for search results
- **Deep-link icons** on every `h2`/`h3`/`h4` in the content — hover to reveal, click to copy a canonical URL with `#anchor` to the clipboard
- **`.txt` and `.json` download buttons** in the session-actions strip next to Copy-as-markdown

#### Part C — Cross-cutting infra

- **Build manifest** (`llmwiki/manifest.py`) — generates `site/manifest.json` on every build with SHA-256 hashes of all files, total sizes, perf-budget check, and budget violations list
- **Link checker** (`llmwiki/link_checker.py`) — walks `site/` verifying every internal `<a href>`, `<link href>`, and `<script src>` resolves to an existing file. External URLs are skipped. Strict regex filters out code-block artifacts.
- **Performance budget** targets declared in `manifest.py` (cold build <30s, total site <150 MB, per-page <3 MB, CSS+JS <200 KB, `llms-full.txt` <10 MB)
- **New CLI subcommands**: `llmwiki check-links`, `llmwiki export <format>`, `llmwiki manifest` (all with `--fail-on-*` flags for CI integration)

### Tests

- **24 new tests** in `tests/test_v04.py` covering exporters, manifest, link checker, MCP `wiki_export`, schema.org microdata, canonical links, per-page siblings, and CLI subcommands
- **95 tests passing total** (was 71 in v0.3)

### Fixed

- Link checker rewritten to only match `<a>` / `<link>` / `<script>` tag hrefs (not URLs inside code blocks). The initial naive regex was catching runaway multi-line matches from rendered tool-result output.
- Canonical URLs and `.txt`/`.json` sibling links now use the actual HTML filename stem (`date-slug`) instead of the frontmatter `slug` field, which was causing broken link reports.

## [0.3.0] — 2026-04-08

### Added

- **`pyproject.toml`** — full PEP 621 metadata, PyPI-ready. Optional dep groups: `highlight` (pygments), `pdf` (pypdf), `dev` (pytest+ruff), `all`. Declared entry point `llmwiki = llmwiki.cli:main`.
- **Eval framework** (`llmwiki/eval.py`) — 7 structural quality checks (orphans, broken links, frontmatter coverage, type coverage, cross-linking, size bounds, contradiction tracking) totalling 100 points. New CLI: `llmwiki eval [--check ...] [--json] [--fail-below N]`. Zero LLM calls, pure structural analysis, runs in under a second on a 300-page wiki.
- **Codex CLI adapter** graduated from v0.2 stub → production with `SUPPORTED_SCHEMA_VERSIONS = ["v0.x", "v1.0"]`, two session store roots, config override, and hashed-path slug derivation.
- **i18n docs scaffold** — translations of `getting-started.md` in Chinese (`zh-CN`), Japanese (`ja`), and Spanish (`es`) under `docs/i18n/`. Each linked back to the English master with a sync date.
- **15 new tests** covering the eval framework, pyproject, i18n scaffold, and version bump.

### Deferred to v0.5+

- OpenCode / OpenClaw adapter
- Homebrew formula
- Local LLM via Ollama (optional synthesis backend)

(per explicit user direction — none of these block a v0.3.0 release)

## [0.2.0] — 2026-04-08

### Added

- **Three new slash commands**: `/wiki-update` (surgical in-place page update), `/wiki-graph` (knowledge graph generator), `/wiki-reflect` (higher-order self-reflection)
- **`llmwiki/graph.py`** — walks every `[[wikilink]]` and produces `graph/graph.json` (canonical) + `graph/graph.html` (vis.js). Reports top-linked, top-linking, orphans, broken edges. CLI: `llmwiki graph [--format json|html|both]`.
- **`llmwiki/watch.py`** — file watcher with polling + debounce. Detects mtime changes in agent session stores and auto-runs `llmwiki sync` after the debounce window. CLI: `llmwiki watch [--adapter ...] [--interval N] [--debounce M]`. Stdlib only, no `watchdog` dep.
- **`llmwiki/obsidian_output.py`** — bidirectional Obsidian output mode. Copies the compiled wiki into a subfolder of an Obsidian vault with backlinks and a README. CLI: `llmwiki export-obsidian --vault PATH [--subfolder NAME] [--clean] [--dry-run]`.
- **Full MCP server** (`llmwiki/mcp/server.py`) — graduated from v0.1 2-tool stub to **6 production tools**: `wiki_query` (keyword search + page content), `wiki_search` (raw grep), `wiki_list_sources`, `wiki_read_page` (path-traversal guarded), `wiki_lint` (structural report), `wiki_sync` (trigger converter).
- **Cursor adapter** (`llmwiki/adapters/cursor.py`) — detects Cursor IDE install on macOS/Linux/Windows, discovers workspace storage.
- **Gemini CLI adapter** (`llmwiki/adapters/gemini_cli.py`) — detects `~/.gemini/` sessions.
- **PDF adapter** (`llmwiki/adapters/pdf.py`) — optional `pypdf` dep, user-configurable roots, disabled by default.
- **Hover-to-preview wikilinks** in the HTML viewer — floating preview cards fetched from the client-side search index.
- **Timeline view** on the sessions index — compact SVG sparkline showing session frequency per day.
- **CLAUDE.md** extended with `/wiki-update`, `/wiki-graph`, `/wiki-reflect` slash command docs and new page types (`comparisons/`, `questions/`, `archive/`).
- **21 new tests** covering adapters, graph builder, Obsidian output, MCP server, file watcher, and CLI subcommands.

## [0.1.0] — 2026-04-08

Initial public release.

### Added

- Python CLI (`python3 -m llmwiki`) with `sync`, `build`, `serve`, `init` subcommands
- Claude Code adapter (`llmwiki.adapters.claude_code`) — converts `~/.claude/projects/*/*.jsonl` to markdown
- Codex CLI adapter stub (`llmwiki.adapters.codex_cli`) — scaffold for v0.2
- Karpathy-style wiki schema in `CLAUDE.md` and `AGENTS.md`
- God-level HTML generator (`llmwiki.build`)
  - Inter + JetBrains Mono typography
  - Light/dark theme toggle with `data-theme` attribute + system preference
  - Global search via pre-built JSON index
  - Cmd+K command palette
  - Keyboard shortcuts (`/` search, `g h` home, `j/k` next/prev session)
  - Syntax highlighting via Pygments (optional dep)
  - Collapsible tool-result sections (click to expand, auto-collapse > 500 chars)
  - Breadcrumbs on session pages
  - Reading progress bar on long pages
  - Sticky table headers on the sessions index
  - Copy-as-markdown and copy-code buttons (with `document.execCommand` fallback for HTTP)
  - Mobile-responsive breakpoints
  - Print-friendly CSS
- One-click scripts for macOS/Linux (`setup.sh`, `build.sh`, `sync.sh`, `serve.sh`)
- One-click scripts for Windows (`setup.bat`, `build.bat`, `sync.bat`, `serve.bat`)
- `.claude/commands/` slash commands: `wiki-sync`, `wiki-build`, `wiki-serve`, `wiki-query`, `wiki-lint`
- `.claude/skills/llmwiki-sync/SKILL.md` — global skill for auto-discovery
- GitHub Actions CI workflow (`.github/workflows/ci.yml`) — lint + build smoke test
- Documentation: getting-started, architecture, configuration, claude-code, codex-cli
- Redaction config with username, API key, token, and email patterns
- Idempotent incremental sync via `.ingestion-state.json` mtime tracking
- Live-session detection — skips sessions with activity in the last 60 minutes
- Sub-agent session support — rendered as separate pages linked from parent
