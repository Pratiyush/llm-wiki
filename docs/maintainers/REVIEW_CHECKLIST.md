# Code review checklist

> **Audience:** maintainers reviewing an incoming PR. This is the
> canonical bar — apply it every time so the review bar stays
> consistent across reviewers.

Copy the relevant section into the PR review comment. Run the
`/review-pr <URL>` slash command for a guided pass.

## Meta

- [ ] **Linked issue** — PR body references an issue, and the scope
      matches. If there's no issue for a non-trivial change, ask the
      contributor to file one first.
- [ ] **One concern per PR** — a bug fix that also refactors a module
      and adds a new feature gets split into three PRs.
- [ ] **Conventional-commit title** — `feat:` / `fix:` / `docs:` /
      `chore:` / `test:` (optionally with a version scope like
      `feat(v0.8):`).
- [ ] **CHANGELOG entry** — every user-visible change has an entry
      under `## [Unreleased]`. Doc-only PRs can skip.
- [ ] **Tests added or updated** — new feature = new tests. Bug fix =
      regression test that fails on master and passes on the branch.
- [ ] **CI is green** — lint-and-test (3.9 + 3.12), performance-budget,
      scan (privacy grep). No merging red PRs.

## Layer boundaries (see ARCHITECTURE.md)

- [ ] **Layer-appropriate changes** — a converter fix doesn't touch the
      HTML builder. A CSS tweak doesn't touch `convert.py`. Mixed-layer
      PRs need a strong justification in the body.
- [ ] **No new runtime deps** — stdlib + `markdown` only. If the PR
      adds a dep, it needs a dedicated "why" paragraph and usually an
      issue of its own for pre-discussion.
- [ ] **Layer-0 stays stdlib-only** — `convert.py` + adapters can't
      pull in `markdown` either. They produce markdown strings.

## Security + privacy

- [ ] **No real session data** — check every test fixture, docs example,
      and seed file. If a path looks like `/Users/<real_name>/...`
      or mentions a real API key, that's a blocker.
- [ ] **Redaction still works** — if the PR touches redaction regex or
      the converter, there must be a test that feeds in a fake
      secret and asserts it was redacted on the way out.
- [ ] **No XSS in rendered HTML** — if the PR renders new content
      from frontmatter or body, it must be HTML-escaped or explicitly
      wrapped in a trusted template. #74 is the canonical example of
      what happens when you forget this.
- [ ] **No network calls during build** — run
      `python3 -m llmwiki build` and confirm the console has no
      `GET https://...` lines (other than the highlight.js CDN, which
      is client-side, not build-time).
- [ ] **Localhost binding stays default** — any new server code must
      default to `127.0.0.1`. Public-bind requires an explicit
      `--host 0.0.0.0` flag.
- [ ] **No telemetry, ever** — no analytics snippets, no "phone home"
      health checks, no cloud log shippers.

## Code quality

- [ ] **Functions have docstrings** — new public functions in
      `llmwiki/` need a one-paragraph docstring explaining what,
      how, and any non-obvious invariants.
- [ ] **Inline comments where the reader would get stuck** — not
      comments that narrate every line. Comments answer "why" where
      the code can't.
- [ ] **Error handling matches the module** — exporters + adapters
      degrade gracefully; CLI commands return non-zero exit codes on
      failure; build never crashes on a single bad file.
- [ ] **Type hints on new public functions** — `-> dict[str, int]`
      style; use `Optional[...]` or `... | None` consistently with
      neighboring code.
- [ ] **No dead code** — if the PR touches a function, check if any
      now-unreferenced helpers should be deleted in the same diff.

## Tests

- [ ] **Tests cover the happy path AND at least one edge case** —
      empty input, missing field, malformed data, Unicode weirdness.
      Pick whichever is relevant.
- [ ] **Test names describe behavior** — `test_parse_changelog_handles_
      frontmatter_parser_mangling` beats `test_parse_1`.
- [ ] **Regression tests lock in recent fixes** — every bug fix PR
      gets at least one test that would have caught the bug before
      the fix.
- [ ] **No reliance on real filesystem outside tmp_path** — all tests
      use `tmp_path` or monkeypatching. No tests that write under the
      repo root.
- [ ] **Run `python3 -m pytest tests/ -q` locally** — don't trust CI
      alone; green CI + a broken local run means `tests/` depends
      on state that only CI has.

## Docs

- [ ] **README updated** if a user-visible surface changed (new CLI,
      new nav link, new file layout).
- [ ] **CHANGELOG updated** under `## [Unreleased]` for every
      user-visible change.
- [ ] **docs/ updated** for any architectural change.
      `docs/architecture.md` is the source of truth for layer
      boundaries; `docs/reference/entity-schema.md` for the model
      schema; `CLAUDE.md` for slash-command workflows.
- [ ] **docstrings match the code** — if the PR renames a flag or
      changes a return type, every referencing docstring updates too.

## Build + runtime smoke

- [ ] Run `python3 -m llmwiki build` locally on the real wiki. No
      crashes, no warnings that weren't there before, byte-identical
      output for unrelated pages.
- [ ] Run the preview server, open the affected page, click around.
      No console errors. No broken images. No 404s on internal links.

## Blocker vs nit

Use the two-category rule:

- **Blocker** — anything from the "Security + privacy" or "Meta"
  sections, plus failing tests, failing build, or broken layer
  boundaries. Mark as `request changes`.
- **Nit** — style, better variable names, doc wording, missing
  comment. Mark as `comment` and don't block.

If you're not sure which, assume blocker. Contributors would rather
fix a nit now than re-open the PR in two weeks.
