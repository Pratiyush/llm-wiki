"""Tests for the PyPI release pipeline wiring (v1.1.0 · #101).

The actual PyPI upload happens on GitHub Actions, not here — these
tests keep the local-side plumbing honest so the manual PyPI setup
described in ``docs/deploy/pypi-publishing.md`` stays aligned with
what the release workflow expects.
"""

from __future__ import annotations

import os
import re
from pathlib import Path

import pytest

from llmwiki import REPO_ROOT, __version__


RELEASE_YML = REPO_ROOT / ".github" / "workflows" / "release.yml"
PYPI_DOC = REPO_ROOT / "docs" / "deploy" / "pypi-publishing.md"
CHECK_SCRIPT = REPO_ROOT / "scripts" / "check-release-artifacts.sh"
PYPROJECT = REPO_ROOT / "pyproject.toml"


@pytest.fixture(scope="module")
def release_yml() -> str:
    return RELEASE_YML.read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def pypi_doc() -> str:
    assert PYPI_DOC.is_file(), (
        "docs/deploy/pypi-publishing.md is missing — the release workflow "
        "references it; re-add it or update the workflow comment"
    )
    return PYPI_DOC.read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def pyproject() -> str:
    return PYPROJECT.read_text(encoding="utf-8")


# ─── Workflow wiring ──────────────────────────────────────────────────


def test_release_workflow_uses_oidc_trusted_publishing(release_yml: str):
    assert "id-token: write" in release_yml
    assert "pypa/gh-action-pypi-publish" in release_yml


def test_release_workflow_gated_on_pypi_publishing_variable(release_yml: str):
    # The publish job must stay gated — otherwise unconfigured repos
    # get a red CI check on every tag push.
    assert "vars.PYPI_PUBLISHING == 'true'" in release_yml


def test_release_workflow_environment_matches_docs(
    release_yml: str, pypi_doc: str
):
    # Both sides of the trusted-publisher binding must agree on the
    # environment name. Mismatches cause PyPI to reject the OIDC token
    # with "invalid-publisher".
    assert "environment: release" in release_yml
    assert "Environment name | `release`" in pypi_doc or \
        "Env: release" in pypi_doc or \
        "environment: release" in pypi_doc.lower()


def test_release_workflow_triggers_only_on_version_tags(release_yml: str):
    # Must NOT trigger on every master push — only on vX.Y.Z tags.
    assert 'tags:' in release_yml
    assert '"v*.*.*"' in release_yml or "'v*.*.*'" in release_yml


def test_release_workflow_signs_with_sigstore(release_yml: str):
    assert "sigstore/gh-action-sigstore-python" in release_yml


def test_github_release_job_runs_even_if_publish_fails(release_yml: str):
    # We commit to keeping GitHub Releases visible even when PyPI is
    # misconfigured, so the failure mode is graceful.
    assert "if: always()" in release_yml


# ─── pyproject.toml must be publishable ───────────────────────────────


def test_pyproject_has_required_metadata(pyproject: str):
    # Without these fields `python -m build` + `twine check` fail and
    # PyPI rejects the sdist.
    for field in ('name =', 'version =', 'description =', 'readme =',
                  'requires-python =', 'authors'):
        assert field in pyproject, f"pyproject.toml missing {field!r}"


def test_pyproject_version_is_pep440_compatible(pyproject: str):
    m = re.search(r'^version\s*=\s*"([^"]+)"', pyproject, re.MULTILINE)
    assert m is not None
    v = m.group(1)
    # PEP 440: digits-only release, plus optional pre-release tag
    # (aN/bN/rcN), plus optional post/dev. No hyphens before rc.
    assert re.fullmatch(r"\d+(\.\d+)*((a|b|rc)\d+)?(\.post\d+)?(\.dev\d+)?", v), (
        f"pyproject.toml version {v!r} isn't PEP 440 — PyPI will reject "
        "the upload. Use e.g. '1.1.0rc2' not 'v1.1.0-rc2'."
    )


def test_pyproject_version_matches_package_version(pyproject: str):
    m = re.search(r'^version\s*=\s*"([^"]+)"', pyproject, re.MULTILINE)
    assert m is not None
    assert m.group(1) == __version__, (
        f"pyproject.toml version {m.group(1)!r} != "
        f"llmwiki.__version__ {__version__!r} — pip install will show "
        "one value while llmwiki --version shows another"
    )


# ─── Doc walkthrough ──────────────────────────────────────────────────


def test_pypi_doc_mentions_trusted_publisher(pypi_doc: str):
    assert "trusted publisher" in pypi_doc.lower()
    assert "OIDC" in pypi_doc


def test_pypi_doc_mentions_publishing_variable(pypi_doc: str):
    assert "PYPI_PUBLISHING" in pypi_doc


def test_pypi_doc_covers_troubleshooting(pypi_doc: str):
    # Must at minimum document the three failure modes the workflow
    # can produce: skipped, invalid-publisher, 403.
    for keyword in ("publish` skipped", "invalid-publisher", "403"):
        assert keyword in pypi_doc, (
            f"docs/deploy/pypi-publishing.md doesn't cover {keyword!r}"
        )


# ─── Local smoke-test helper ──────────────────────────────────────────


def test_check_release_artifacts_script_exists_and_executable():
    assert CHECK_SCRIPT.is_file(), (
        "scripts/check-release-artifacts.sh is missing — it's referenced "
        "by the PyPI publishing doc as the local dry-run entry point"
    )
    assert os.access(CHECK_SCRIPT, os.X_OK), (
        "scripts/check-release-artifacts.sh isn't executable; "
        "run `chmod +x` on it"
    )


def test_check_release_artifacts_script_runs_twine_check():
    text = CHECK_SCRIPT.read_text(encoding="utf-8")
    # Must build AND validate — building alone doesn't catch the
    # metadata issues that trip up PyPI.
    assert "python -m build" in text or "python3 -m build" in text
    assert "twine check" in text
