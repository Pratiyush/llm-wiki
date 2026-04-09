Run the canonical llmwiki code review against a pull request and post findings.

Usage: /review-pr <pr-number-or-url>

This slash command loads `docs/maintainers/REVIEW_CHECKLIST.md` and
applies every section to the diff of the given PR. The rule is: one
concern per bullet, blocker-vs-nit classification, link to the
relevant doc section for every finding.

## Workflow

1. **Resolve the PR number** — accept either `123` or
   `https://github.com/Pratiyush/llm-wiki/pull/123`. Use `gh pr view
   <N>` to fetch the title, body, author, and file list.

2. **Read the governance docs first** — load all of:
   - `docs/maintainers/REVIEW_CHECKLIST.md` (the full bar)
   - `docs/maintainers/ARCHITECTURE.md` (layer boundaries)
   - `docs/maintainers/DECLINED.md` (prior rejections that may apply)
   - `CONTRIBUTING.md` (TL;DR rules)
   - `SECURITY.md` (privacy + security bar)

3. **Fetch the diff** — `gh pr diff <N>` for the raw patch. Walk
   the diff file by file, mapping each to its layer via
   `docs/maintainers/ARCHITECTURE.md`.

4. **Run the checklist** — apply every section of
   `REVIEW_CHECKLIST.md` to the diff:
   - Meta (linked issue, one concern, commit title, CHANGELOG, tests, CI)
   - Layer boundaries (layer-appropriate changes, no new runtime deps)
   - Security + privacy (no real session data, XSS, no network,
     localhost binding, no telemetry)
   - Code quality (docstrings, comments, error handling, type hints,
     dead code)
   - Tests (happy + edge, descriptive names, regression, tmp_path,
     run locally)
   - Docs (README, CHANGELOG, docs/, docstrings)
   - Build + runtime smoke

5. **Classify each finding** — two categories only:
   - **Blocker** — Meta section failures, security/privacy issues,
     failing tests, failing build, broken layer boundaries
   - **Nit** — style, wording, missing comment, cosmetic

6. **Post the review** — group findings by file, then by severity
   within each file. Blockers first. Every finding cites the
   relevant section of `REVIEW_CHECKLIST.md` so the contributor
   can look up the rule.

7. **Final verdict** — one of:
   - **Approve** — no blockers, maybe a few nits
   - **Request changes** — at least one blocker
   - **Comment** — questions only, no blockers, no nits (rare)

## Output format

```markdown
# Review: PR #123 — <title>

**Author:** @<name>
**Verdict:** <Approve | Request changes | Comment>
**Summary:** <one sentence>

## Blockers

### `llmwiki/build.py`

- **[Security]** `<finding>` — see [REVIEW_CHECKLIST §Security + privacy](docs/maintainers/REVIEW_CHECKLIST.md#security--privacy)

### `tests/test_foo.py`

- **[Tests]** `<finding>` — see [REVIEW_CHECKLIST §Tests](docs/maintainers/REVIEW_CHECKLIST.md#tests)

## Nits

### `docs/bar.md`

- **[Docs]** `<finding>` — optional

## Next steps

<!-- What the contributor should do to get to Approve -->
```

## Blocker shortlist

If any of these are true, mark as **Request changes** immediately:

- Tests are failing on master (CI red)
- No linked issue and the PR touches > 2 files
- New runtime dependency introduced in `pyproject.toml`
- Real session data committed under `tests/fixtures/` or `wiki/`
- The maintainer's real username appears anywhere in committed files
- `CHANGELOG.md` is not updated for a `feat:` / `fix:` PR
- Network calls added to `build.py` or `convert.py`
- Server binds to `0.0.0.0` by default

## Append to log

After posting the review, append one line to `wiki/log.md`:

    ## [YYYY-MM-DD] review | PR #<N>: <verdict>
