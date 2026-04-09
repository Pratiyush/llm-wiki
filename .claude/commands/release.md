Walk the llmwiki release process step by step.

Usage: /release <version>        # e.g. /release 0.9.0

This slash command loads `docs/maintainers/RELEASE_PROCESS.md` and
walks through every step interactively. The rule is: don't skip a
step even if it "should be" fine — skipping steps is how broken
releases ship.

## Workflow

1. **Load the release process doc** —
   `docs/maintainers/RELEASE_PROCESS.md` has the canonical checklist.
   Read it end to end before doing anything.

2. **Run the pre-flight** — confirm all of:
   - Master is green (`gh run list --branch master --limit 5`)
   - `python3 -m pytest tests/ -q` passes on a clean checkout
   - `python3 -m llmwiki build` completes without new warnings
   - Preview the built site and click through every nav item
   - No open `priority:critical` bugs
     (`gh issue list --label priority:critical --state open`)

   If any of these fail, stop and fix them first.

3. **Bump the version** — three files must agree:
   - `llmwiki/__init__.py` → `__version__ = "<NEW>"`
   - `pyproject.toml` → `version = "<NEW>"`
   - `README.md` → version badge
     (`Version-v<NEW>-7C3AED.svg`)
   Run `python3 -m llmwiki --version` to confirm.

4. **Update CHANGELOG** — for every entry:
   - Move from `## [Unreleased]` into `## [<NEW>] — YYYY-MM-DD`
   - Group by `### Added` / `### Changed` / `### Fixed` / `### Removed`
   - Add a one-line "Theme:" at the top of the new section
   - Keep an empty `## [Unreleased]` section above

5. **Spot-check PR numbers** — every `#N` in the new section should
   link to a real merged PR. Run
   `gh pr list --state merged --limit 30` and cross-reference.

6. **Commit and tag** — use these exact commands:
   ```bash
   git add llmwiki/__init__.py pyproject.toml README.md CHANGELOG.md
   git commit -m "release(v<NEW>): bump version + CHANGELOG"
   git tag v<NEW>
   git push origin master v<NEW>
   ```
   Do NOT force-push master. Do NOT amend the release commit after
   tagging.

7. **Create the GitHub Release**:
   ```bash
   gh release create v<NEW> --title "v<NEW>" --notes-from-tag --prerelease
   ```
   The `--prerelease` flag stays set for every `0.x.y` until `1.0.0`.

8. **Verify the Pages deploy**:
   ```bash
   gh run list --workflow=pages.yml --limit=3
   ```
   The new tag + the master push should both trigger the workflow.
   Watch both runs. Visit
   `https://pratiyush.github.io/llm-wiki/` and confirm the new
   version badge is visible.

9. **Announce (optional)** — post to X / LinkedIn if it's a
   milestone release (v0.5, v0.9, v1.0, ...).

10. **Append to log** — one line to `wiki/log.md`:

        ## [YYYY-MM-DD] release | v<NEW>

## Rollback

If a release is broken AFTER the tag is pushed:

1. Cut a patch release (`v<NEW>+1`) that reverts the bad PR
2. Mark the broken release as "Pre-release" on GitHub and edit
   the notes to say "superseded by v<NEW>+1"
3. **Never delete tags** — downstream packages may pin to them
4. **Never force-push master** — always roll forward

## Example

```
/release 0.9.0
```

Walks through every step, confirms each checkbox with the user
before moving to the next, refuses to proceed if a pre-flight
check fails.
