# Contributing to llmwiki

Thanks for wanting to contribute. This project follows strict rules about commits, PRs, and privacy — please read this before opening a PR.

**Try the live demo first:** [pratiyush.github.io/llm-wiki](https://pratiyush.github.io/llm-wiki/). It's rebuilt on every `master` push from [`examples/demo-sessions/`](examples/demo-sessions) so you can see every feature working before touching code.

## Table of contents

- [TL;DR rules of contribution](#tldr-rules-of-contribution)
- [Code of conduct](#code-of-conduct)
- [Dev setup](#dev-setup)
- [Project structure](#project-structure)
- [Commit + PR rules](#commit--pr-rules)
- [Adding a new adapter](#adding-a-new-adapter)
- [Privacy rules](#privacy-rules)
- [Testing](#testing)
- [Releases](#releases)

## TL;DR rules of contribution

1. **One concern per PR.** Don't mix a bug fix with a new feature.
2. **Commit prefixes:** `feat:` / `fix:` / `docs:` / `chore:` / `test:` — e.g. `feat(v0.7): tool-calling bar chart (#65)`.
3. **Never commit real session data.** `raw/sessions/` is gitignored. Fixtures must be synthetic or heavily redacted.
4. **No new runtime deps.** Stdlib + `markdown` only. Viewer loads highlight.js from a CDN — no server-side parser needed.
5. **Tests must pass.** Run `python3 -m pytest tests/ -q` before pushing. CI runs on Python 3.9 + 3.12.
6. **Add a CHANGELOG entry** under `## [Unreleased]` for every user-visible change.
7. **Open an issue first** for anything bigger than a one-file fix. Keeps scope aligned.

That's it. If you follow those seven rules your PR is 90% of the way through review.

## Code of conduct

Be kind. Respect privacy. Prefer plain English to jargon. No scope creep.

## Dev setup

```bash
git clone https://github.com/Pratiyush/llm-wiki.git
cd llm-wiki
./setup.sh                # installs markdown, scaffolds raw/ wiki/ site/
python3 -m pytest tests/ -q
```

Requirements:

- Python ≥ 3.9
- `markdown` (required — the only runtime dep)
- `ruff` (dev — lint)
- `pytest` (dev — tests)

No other runtime deps. That's a hard rule. Syntax highlighting runs in the browser via [highlight.js](https://highlightjs.org/) loaded from a CDN, so the build pipeline stays stdlib-only.

## Project structure

See [docs/architecture.md](docs/architecture.md) for the full breakdown. TL;DR:

```
llmwiki/              # Python package
├── cli.py            # argparse entry (init/sync/build/serve/adapters/version)
├── convert.py        # .jsonl → markdown
├── build.py          # markdown → HTML (god-level UI)
├── serve.py          # localhost HTTP server
├── adapters/         # session-store adapters (one per agent)
└── mcp/              # MCP server (7 production tools, stdio transport)

.claude/              # Claude Code plugin surface
.claude-plugin/       # plugin.json + marketplace.json
.kiro/steering/       # always-loaded rules
docs/                 # user-facing + framework docs
tests/                # fixtures + snapshot tests
```

## Commit + PR rules

Adapted from the parent [Open Source Project Framework](docs/framework.md):

### Identity

- `git config user.name "Pratiyush"` (on this fork — you should use your own name on your fork)
- **Never** add `Co-authored-by: Claude`, `Co-authored-by: AI`, or similar AI attribution lines. Commits from this project are human-authored.

### PR size

- **One intent per PR.** Don't mix "add a new adapter" with "fix a CSS bug". Split before opening.
- **≤500 lines of diff.** If the PR gets larger than that, the reviewer will ask you to split.
- **Atomic commits.** Each commit tells a clear story; renames isolated from behavior changes.

### PR title format

Conventional Commits. Types we accept:

| Type | When | Version bump |
|------|------|--------------|
| `feat` | New user-visible capability | minor |
| `fix` | Bug fix | patch |
| `chore` | Maintenance, deps, CI, version bumps | patch |
| `docs` | Docs only | patch |
| `test` | Tests only | patch |
| `refactor` | Internal restructuring, no behavior change | patch |
| `perf` | Performance improvement | patch |
| `security` | Security fix or hardening | patch |
| `release` | Version bump + CHANGELOG promotion | — |

Optionally scope with a version: `feat(v0.8): tool chart`. Include the issue number: `Closes #65` in the body.

### PR body — 15-box pre-merge checklist

Every box must be checked (or have a one-line waiver). See [`.github/PULL_REQUEST_TEMPLATE.md`](.github/PULL_REQUEST_TEMPLATE.md) for the current list. Covers at minimum:

1. One intent (no mixing concerns)
2. CI green
3. Linked issue via `Closes #N`
4. Conventional-commit title
5. Tests added/updated (happy path + edge case)
6. CHANGELOG under Unreleased
7. Breaking changes flagged + labeled `breaking`
8. No new runtime deps (stdlib + `markdown` only)
9. No real session data in `raw/` or fixtures
10. No machine-specific paths or secrets
11. Docs updated for user-visible changes
12. **UI verified in light AND dark mode** (for CSS/UI changes) — screenshots attached
13. **A11y verified** — keyboard nav, focus rings, WCAG 2.1 AA (≥ 4.5:1 contrast)
14. Commits GPG-signed, no AI co-author trailers, atomic
15. Reviewer has read every changed line (no rubber-stamping)

### Branch protection

- Default branch is `master`; never push directly — PR required.
- CI must pass before merge.
- Signed commits required.
- Branch must be up-to-date with master before merge.

## Adding a new adapter

See [docs/framework.md §5.25 Adapter Flow](docs/framework.md) for the full contract. Minimum requirements:

1. **One file** under `llmwiki/adapters/<agent>.py` that:
   - Subclasses `BaseAdapter`
   - Registers itself via `@register("<agent>")`
   - Sets `session_store_path` to the agent's default location(s)
   - Declares `SUPPORTED_SCHEMA_VERSIONS`

2. **At least one fixture** under `tests/fixtures/<agent>/minimal.jsonl` — synthetic or heavily redacted.

3. **One snapshot test** under `tests/snapshots/<agent>/minimal.md` — the expected markdown output.

4. **One test** under `tests/test_<agent>_adapter.py` that runs the converter against the fixture and diffs against the snapshot.

5. **One documentation page** at `docs/adapters/<agent>.md`.

6. **A CHANGELOG entry** under `## [Unreleased]`.

7. **One line** in `README.md` under "Works with".

### Cross-platform path requirement

`DEFAULT_ROOTS` (or `DEFAULT_VAULT_PATHS` / `session_store_path`) must work on
macOS, Linux, **and** Windows. Two patterns are acceptable:

1. **Dot-directory** (`Path.home() / ".agent" / ...`) -- works on all three
   platforms by default; a single entry is fine.
2. **OS-specific directories** (e.g. `~/Library/Application Support/...`,
   `~/.config/...`, `~/AppData/Roaming/...`) -- you need at least one entry per
   platform. Use inline comments to label which path is for which OS.

Always use `Path.home()` -- never hardcode `/Users/`, `/home/`, or `C:\Users\`.
The test in `tests/test_cross_platform_paths.py` enforces these rules.

Adapters with no default paths (like `pdf`, where the user must configure roots)
are exempt.

### Review checklist for adapter PRs

- [ ] Adapter declares `SUPPORTED_SCHEMA_VERSIONS`
- [ ] `DEFAULT_ROOTS` covers macOS + Linux + Windows (see above)
- [ ] Fixture is under 50 KB and contains **no real PII**
- [ ] Snapshot test passes locally
- [ ] `docs/adapters/<agent>.md` exists and is linked from README
- [ ] Graceful degradation: unknown record types are skipped, not crashed on
- [ ] No new runtime deps introduced

## Privacy rules

llmwiki processes session transcripts that may contain PII, API keys, file paths, and secrets. These rules are **non-negotiable**:

1. **Redaction is on by default.** Username, API keys, tokens, passwords, and emails are redacted before anything hits `raw/`.
2. **Never commit real session data.** `raw/` is gitignored. Fixtures under `tests/fixtures/` must be synthetic or heavily redacted.
3. **Never commit machine-specific paths.** No `.claude/settings.local.json`, no `.ingestion-state.json`, no `.framework/`, no `.temp/`.
4. **Privacy grep** runs in CI: `grep -r "<real_username>" .` must return zero hits in committed files.
5. **No telemetry, ever.** The tool never calls home.
6. **Localhost-only binding by default.** The server binds to `127.0.0.1` unless the user explicitly passes `--host 0.0.0.0`.

## Testing

```bash
python3 -m pytest tests/ -q             # all tests
python3 -m pytest tests/test_convert.py # one file
python3 -m llmwiki build                # smoke test build
python3 -m llmwiki --version            # version check
```

Every adapter must ship with:

- A fixture (synthetic or heavily redacted)
- A snapshot test
- A graceful-degradation test (passes an unknown record type)

## Releases

`v0.x` is pre-production. API, schema, and file layout may change.

Release flow (Phase 6 of the framework):

1. Bump version in `llmwiki/__init__.py`
2. Update `CHANGELOG.md`
3. `git tag v0.x.y && git push origin v0.x.y`
4. Create a GitHub Release (mark pre-release for 0.x)
5. `.github/workflows/pages.yml` auto-deploys the demo site

## Questions?

Open an issue with the `question` label. Or ping [@Pratiyush](https://github.com/Pratiyush) on X.
