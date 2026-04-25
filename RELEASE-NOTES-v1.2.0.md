# llmwiki v1.2.0 — first stable on the 1.x line

**Release date:** 2026-04-25
**Tag:** `v1.2.0`
**PyPI:** `pip install llmwiki==1.2.0` (once trusted publisher is configured — see issue #246)
**Homebrew:** `brew install Pratiyush/tap/llmwiki` (once tap is published — see issue #247)

This is the first stable release on the 1.x line. It promotes the eight rc1–rc8 prereleases into a single stable tag and bundles the post-rc8 audit fixes, a one-shot pipeline runner, the new Playwright/axe-core E2E suite, and ten UX-critique items into one shippable cut.

## What's new

### `llmwiki all` — one command for the whole pipeline
```bash
python3 -m llmwiki all              # build → graph → export → lint
python3 -m llmwiki all --strict     # exit 2 on any lint warning (CI gate)
```
Plus `/wiki-all` slash command for Claude Code. Replaces the chain of four manual slash commands users were running after every sync.

### Playwright + axe-core E2E suite
62 Gherkin scenarios across 11 feature files: homepage, session detail, command palette, keyboard nav, mobile bottom nav, theme toggle, copy-as-markdown, responsive (9 viewports × 3 pages), accessibility, and visual regression. Found and fixed 3 real bugs while landing the suite. Opt-in via the `[e2e]` extras.

### Auto-seeded project stubs
`build` now creates an empty `wiki/projects/<slug>.md` for every newly-discovered project on first run. No more bare hero on real-data project pages while demos look rich.

### 2 new lint rules
- `frontmatter_count_consistency` — flags inflated `user_messages` / `tool_calls` counts that don't match the body
- `tools_consistency` — flags `tools_used` / `tool_counts.keys()` divergence

The wiki lint registry now ships 16 rules.

## What's fixed

### Critical data-fidelity bugs from the post-rc8 audit (#378)
- **Code blocks were stripped from every AI-consumable export.** `_plain_text` replaced fenced blocks with a single space, deleting the most valuable content from `.txt`/`.json`/`llms.txt`/`llms-full.txt`/search chunks. Code is now preserved.
- **JSON sibling types were strings.** `is_subagent: "false"` (a truthy string in both JS and Python) is now `false` (bool); `user_messages` / `tool_calls` are now `int`.
- **`sync --force` silently dropped ~200 of 495 colliding sessions.** The collision disambiguator was gated on `not force`. Per-run filename tracking now disambiguates regardless of `--force`.

### Accessibility + UX
- WCAG color-contrast violations resolved on session pages (light) and dark-mode chrome (#385).
- JS pageerror in graph.html no longer fires during cross-page navigation (#386).
- Branded 404 page; sticky TOC on docs hub; (count) suffixes on `wiki/index.md` headings; pluralised hero subtitles; nine other UX-critique items closed (#387 series).

### Demo-data quality
8 demo session files had `user_messages` / `tool_calls` 2–10× higher than the body actually contained. Rewritten from body content. New lint rule prevents regression.

### Other fixes
- Broken adapter doc paths after the `contrib/` move (#367, #379)
- `setup.sh --dry-run` referenced a flag that doesn't exist (replaced with `--status`)
- 22 broken wikilinks in demo project pages (un-wikilinked or stub pages added)
- 6 entity/concept stub pages added to resolve seeded model-page wikilinks
- `graphifyy` typo → `graphify` (7 occurrences in user-facing strings)
- Non-hermetic graphify test now skips when the optional package isn't installed
- `CRITICAL_FACTS.md` seed no longer fails its own lint on a fresh init

## Changed

- **Adapters split: core vs contrib** (#363). 3 core auto-discovered (claude_code, codex_cli, obsidian); 6 moved to `adapters/contrib/` (chatgpt, copilot, cursor, gemini, opencode).
- **CLI slimmed from 25 to 11 subcommands** (#362). Removed: quarantine, backlinks, references, tag, log, watch, export-obsidian, export-marp/jupyter/qmd, check-links, manifest, install-skills, link-obsidian, completion.
- **Graphify is now an optional dep** (#364). `pip install llmwiki[graph]`.

## Removed

- 9 dead-weight modules (~5K lines): prototypes, auto_dream, visual_baselines, cache_tiers, eval, web_clipper, scheduled_sync, reader_shell, image_pipeline.
- 3 niche exporters (~800 lines): export_marp, export_jupyter, export_qmd.
- 3 non-session adapters (~600 lines): jira_adapter, meeting, pdf.
- 14 CLI subcommands.
- 89 stale git branches.

## Upgrading from 1.0.0 / 1.1.0-rc*

This release is a drop-in upgrade — nothing in the public API changed, just the underlying behaviour got more correct. Run:

```bash
pip install --upgrade llmwiki
python3 -m llmwiki all --strict     # verify everything still passes
```

If you were relying on any of the deleted CLI subcommands (e.g. `quarantine`, `check-links`, `install-skills`), see [docs/UPGRADING.md](docs/UPGRADING.md) for the replacement.

If you have hand-authored `wiki/projects/<slug>.md` files, they will not be touched — `ensure_project_stubs()` only creates stubs for slugs that have no metadata file.

## Stats

- **41 commits** since `v1.1.0-rc8`.
- **2068 unit tests** + **62 E2E scenarios** passing.
- **16 lint rules** in the registry (was 14).
- **0 broken wikilinks** in seeded wiki content.

## Contributors

- @Pratiyush

## Full changelog

See [CHANGELOG.md](https://github.com/Pratiyush/llm-wiki/blob/master/CHANGELOG.md#120--2026-04-25).
