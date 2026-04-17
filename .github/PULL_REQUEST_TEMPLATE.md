<!--
Thanks for the PR! Fill in every section below — reviewers use this
template as a checklist. PRs with empty sections usually bounce.

See CONTRIBUTING.md for the full rules, or
docs/maintainers/REVIEW_CHECKLIST.md for the full review bar.
-->

## Summary

<!-- One paragraph: what does this PR do? -->

Closes #<issue>

## What changed

<!-- Bullet points on the notable changes. One bullet per concern. -->

-
-
-

## How to test it

<!-- Shell commands or click-path a reviewer can run -->

```bash
python3 -m pytest tests/ -q
python3 -m llmwiki build
python3 -m llmwiki lint --fail-on-errors
```

## Pre-merge checklist

Every box below must be checked (or have a one-line waiver explaining why it does not apply to this PR).

- [ ] **One intent** — this PR does one thing (no mixing a fix with a refactor or a new feature)
- [ ] **All CI checks green** — no `--no-verify`, no skipped required jobs
- [ ] **Linked issue** — title or body contains `Closes #N` (or one-line waiver explaining why the change is trivial)
- [ ] **Conventional-commit title** — `<type>(<scope>): <imperative>` where type is `feat` / `fix` / `chore` / `docs` / `test` / `refactor` / `perf` / `security` / `release` (optionally with a version scope like `feat(v0.8):`)
- [ ] **Tests added or updated** — happy path + at least one edge case; TDD where shape is clear
- [ ] **CHANGELOG.md updated** — new entry under `## [Unreleased]` (skip for doc-only PRs that don't change behavior)
- [ ] **Breaking changes flagged** — PR labeled `breaking` and announced in the body under a clear heading
- [ ] **No new runtime dependencies** — stdlib + `markdown` only; new dev/test deps need justification + license check (no AGPL/GPL into MIT)
- [ ] **No real session data** — no personal sessions under `raw/sessions/` or in test fixtures; `wiki/` user content stays gitignored
- [ ] **No machine-specific paths** or secrets in committed files (check `.env`, `*.key`, home paths, usernames)
- [ ] **Docs updated** — `README.md`, `docs/`, inline `--help` all reflect any user-visible change
- [ ] **UI verified** (light AND dark mode) — for any change to `llmwiki/build.py` CSS or static site. Paste screenshots below.
- [ ] **A11y verified** — keyboard nav works, focus rings visible, `axe` clean (for UI changes). WCAG 2.1 AA minimum (contrast ≥ 4.5:1).
- [ ] **Commits GPG-signed** by the repo author; no AI co-author trailers; atomic commits (one logical change each)
- [ ] **Reviewer has read every changed line** — no rubber-stamping

## Screenshots / output

<!-- For UI changes: paste LIGHT + DARK screenshots side-by-side.
     For CLI changes: paste the new --help output.
     For build changes: paste the build summary line. -->

## Out of scope / follow-ups

<!-- What did you explicitly NOT do in this PR? What issues should be filed next? -->
