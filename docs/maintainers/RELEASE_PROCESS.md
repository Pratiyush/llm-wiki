# Release process

> **Audience:** whoever is cutting the next tag. This is the
> step-by-step checklist. Run the `/release <version>` slash command
> for a guided walkthrough that follows the same steps.

llmwiki uses [semantic versioning](https://semver.org/) with a
pre-`1.0.0` caveat: every `0.x.y` release can break compatibility
freely. `1.0.0` will be the first stable release.

Minor-version bumps (`0.X.0`) ship when a coherent feature batch
lands (heatmap + tool chart + token usage = v0.8). Patch bumps
(`0.X.y`) ship when a critical fix can't wait for the next minor.

## Pre-flight

- [ ] Master is green (all tests pass, all recent CI runs passed)
- [ ] `python3 -m pytest tests/ -q` on a clean checkout — local
      pass beats CI-only pass
- [ ] `python3 -m llmwiki build` succeeds end-to-end, no warnings
      that weren't there before
- [ ] Preview the built site locally and click through every nav
      item — look for broken links, missing icons, crashed JS
- [ ] No open `priority:critical` bugs (run `gh issue list --label
      priority:critical --state open` and verify it's empty)

## Bump version

The single source of truth is `llmwiki/__init__.py`. Every other
place that mentions the version is derivative and must match.

- [ ] Update `__version__ = "X.Y.Z"` in `llmwiki/__init__.py`
- [ ] Update `version = "X.Y.Z"` in `pyproject.toml` (the test
      `test_pyproject_version_matches_package` enforces this)
- [ ] Update the version badge in `README.md`
      (`Version-vX.Y.Z-7C3AED.svg`)
- [ ] Update the tests badge in `README.md` with the new passing count
      from `python3 -m pytest tests/`
- [ ] Run `python3 -m llmwiki --version` and confirm it prints the
      new version

## Update CHANGELOG

- [ ] Move every entry from `## [Unreleased]` into a new
      `## [X.Y.Z] — YYYY-MM-DD` section
- [ ] Re-create an empty `## [Unreleased]` section above the new one
- [ ] Group entries by `### Added` / `### Changed` / `### Fixed` /
      `### Removed` in keep-a-changelog order
- [ ] Add a one-line "Theme:" at the top of the release section
      summarising the batch (e.g. "Theme: v0.8 visualization trio —
      heatmap, tool charts, token usage")
- [ ] Spot-check every PR number against the actual merged PRs —
      copy-paste errors happen

## Commit + tag

```bash
git add llmwiki/__init__.py pyproject.toml README.md CHANGELOG.md
git commit -m "release(vX.Y.Z): bump version + CHANGELOG"
git tag vX.Y.Z
git push origin master vX.Y.Z
```

- [ ] Do NOT force-push master
- [ ] Do NOT amend the release commit after tagging

## GitHub Release

- [ ] `gh release create vX.Y.Z --title "vX.Y.Z" --notes-from-tag
      --prerelease`
      (`--prerelease` stays set for every `0.x.y` until `1.0.0`)
- [ ] Confirm the release shows up at
      `https://github.com/Pratiyush/llm-wiki/releases`

## Verify Pages deploy

- [ ] `.github/workflows/pages.yml` fires on both `master` push and
      the new tag. Watch the run with `gh run list --workflow=pages.yml
      --limit=3`
- [ ] Visit `https://pratiyush.github.io/llm-wiki/` and confirm the
      new version badge + any new features are visible
- [ ] If the deploy failed, fix master first; don't hotfix the tag

## Announce (optional)

- [ ] Post to the project X account / LinkedIn with a link to the
      GitHub Release page
- [ ] Pin an "issue digest" discussion thread with the highlights
      if it's a milestone release (v0.5, v0.9, v1.0, ...)

## Rollback

If a release is broken, don't delete the tag. Do:

1. Cut a patch release (`vX.Y.Z+1`) that reverts the bad PR
2. Mark the broken release as "Pre-release" and edit the notes to
   say "superseded by vX.Y.Z+1"
3. Never delete tags — downstream packages may pin to them
