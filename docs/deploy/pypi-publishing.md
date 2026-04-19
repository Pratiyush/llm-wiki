# PyPI publishing — one-time setup

> Status: the Actions workflow (`/.github/workflows/release.yml`) is ready.
> This document is the checklist for **one-time PyPI configuration** that
> unblocks `pip install llmwiki` (#101).

## How the pipeline works

Every time a version tag (`v*.*.*`) is pushed:

1. **`build`** — builds sdist + wheel with `python -m build` on Python 3.12.
2. **`publish`** — uploads to PyPI via OIDC trusted publisher. **Gated on
   `vars.PYPI_PUBLISHING == 'true'`**: until that variable is set, the job
   is skipped silently so unconfigured repos don't fail on every tag.
3. **`sign`** — signs artifacts with Sigstore (`gh-action-sigstore-python`).
4. **`github-release`** — creates (or updates) the matching GitHub Release
   with `--generate-notes`, attaches all artifacts + signatures. Runs even
   if publish/sign fail so Releases always keep tracking tags.

The package is uploaded as **`llmwiki`** (no hyphen). The CLI entry point
stays `llmwiki` either way.

## One-time setup (do this once, on pypi.org)

### 1. Reserve the project name on PyPI

1. Log in to [pypi.org](https://pypi.org) (create an account if you
   haven't yet — GitHub sign-in works).
2. **"Your projects" → "Manage"** — the `llmwiki` name might already be
   taken. If it is, either:
   - Use a variant: `llmwiki-py`, `karpathy-llmwiki`, etc. (update
     `pyproject.toml::name` + the PyPI project name in the workflow to
     match), or
   - Ask PyPI admins to transfer the name (see
     [PEP 541](https://peps.python.org/pep-0541/)).
3. Once the name is yours (or a variant is chosen), continue.

### 2. Add the GitHub repo as a trusted publisher

Inside the PyPI project page:

**Publishing → Add a new publisher → GitHub**

| Field | Value |
|---|---|
| PyPI Project Name | `llmwiki` |
| Owner | `Pratiyush` |
| Repository name | `llm-wiki` |
| Workflow name | `release.yml` |
| Environment name | `release` |

Save. This binds the GitHub OIDC identity to PyPI so the workflow can
upload without a long-lived API token.

### 3. Create the `release` GitHub environment

1. **[Repository settings → Environments → New environment](https://github.com/Pratiyush/llm-wiki/settings/environments)**
2. Name: **`release`**
3. Optional protection rules:
   - **Required reviewers** — add your own handle so every PyPI upload
     requires an explicit click.
   - **Wait timer** — 5 minutes gives you time to abort a mis-tagged release.
   - **Deployment branches** — limit to `master` so only master-tagged
     releases can trigger the upload.

### 4. Flip the publishing gate on

```bash
gh variable set PYPI_PUBLISHING --body "true" --repo Pratiyush/llm-wiki
# Verify
gh variable list --repo Pratiyush/llm-wiki | grep PYPI_PUBLISHING
```

### 5. Cut a real release tag

```bash
# Make sure you are on master with everything merged
git checkout master && git pull

# Bump version if needed, update CHANGELOG, commit...

# Create a signed tag
git tag -s v1.1.0 -m "v1.1.0 release"
git push origin v1.1.0
```

Watch the workflow at:
<https://github.com/Pratiyush/llm-wiki/actions/workflows/release.yml>

The `publish` job should now run and show `uploading` + `success`.

### 6. Verify from a clean machine

```bash
python3 -m venv /tmp/pypi-smoke && source /tmp/pypi-smoke/bin/activate
pip install llmwiki
llmwiki --version    # should match the tag
llmwiki adapters     # should list Claude Code, Codex, Cursor, Gemini, …
deactivate
```

## Troubleshooting

**`publish` skipped** — `PYPI_PUBLISHING` variable not set, or set to
something other than `"true"`. Fix:
`gh variable set PYPI_PUBLISHING --body "true"`.

**`publish` fails with "invalid-publisher"** — the OIDC binding on
pypi.org doesn't match what GitHub sent. Double-check: owner =
`Pratiyush`, repo = `llm-wiki`, workflow = `release.yml`, environment
= `release`. Casing matters.

**`publish` fails with "403 Forbidden: User ... isn't allowed to upload
to project ..."** — the PyPI project exists but the trusted publisher
hasn't been added yet (or was added under a different project name).
Re-check step 2.

**Artifacts rejected for metadata** — check that `pyproject.toml`'s
`name`, `version`, and `description` are all present; `python -m build`
locally + `twine check dist/*` surface issues before a tag push.

**Second upload of the same version** — PyPI refuses to overwrite a
version. Bump to the next patch (`v1.1.1`), update the changelog, re-tag.

## Related

- `#101` — this issue
- `.github/workflows/release.yml` — the pipeline
- `docs/deploy/homebrew-setup.md` — sibling doc for the Homebrew tap (#102)
