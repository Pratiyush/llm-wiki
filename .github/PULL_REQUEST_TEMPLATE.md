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
```

## Checklist

- [ ] Linked to an issue (or explained why the change is trivial enough not to need one)
- [ ] One concern per PR — no mixing a bug fix with a new feature
- [ ] Conventional-commit title: `feat:` / `fix:` / `docs:` / `chore:` / `test:` (optionally with a version scope like `feat(v0.8):`)
- [ ] Tests added or updated — happy path + at least one edge case
- [ ] `python3 -m pytest tests/ -q` passes locally
- [ ] `python3 -m llmwiki build` completes without new warnings
- [ ] CHANGELOG.md has a new entry under `## [Unreleased]` (skip for doc-only PRs)
- [ ] No new runtime dependencies (stdlib + `markdown` only)
- [ ] No real session data under `raw/sessions/` or in test fixtures
- [ ] No machine-specific paths in committed files
- [ ] Docs updated for any user-visible change

## Screenshots / output

<!-- Paste screenshots, preview URLs, or CLI output if the change affects the rendered site or the CLI -->

## Out of scope / follow-ups

<!-- What did you explicitly NOT do in this PR? What issues should be filed next? -->
