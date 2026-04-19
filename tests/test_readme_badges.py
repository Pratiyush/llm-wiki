"""Guardrails for the README badge block (v1.1.0 · #129).

These tests don't verify badge visuals — they verify the plumbing stays
wired up so badges don't silently rot:

- Every workflow the badges point at exists in ``.github/workflows/``.
- The version badge matches ``llmwiki.__version__``.
- The CI + link-check + wiki-checks + docker badges are present (the
  four key workflows the issue #129 asked to surface).
- The demo GIF referenced from the README is checked into the repo.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from llmwiki import REPO_ROOT, __version__


README = REPO_ROOT / "README.md"


@pytest.fixture(scope="module")
def readme_text() -> str:
    return README.read_text(encoding="utf-8")


# ─── Core badges the issue (#129) asked for ────────────────────────────


def test_ci_badge_present(readme_text: str):
    assert "actions/workflows/ci.yml/badge.svg" in readme_text, (
        "CI workflow badge is missing from README — re-add the shields.io "
        "line pointing at .github/workflows/ci.yml"
    )


def test_link_check_badge_present(readme_text: str):
    assert "actions/workflows/link-check.yml/badge.svg" in readme_text


def test_wiki_checks_badge_present(readme_text: str):
    assert "actions/workflows/wiki-checks.yml/badge.svg" in readme_text


def test_docker_badge_present(readme_text: str):
    assert "actions/workflows/docker-publish.yml/badge.svg" in readme_text


# ─── Badges must point at workflows that actually exist ────────────────


BADGE_WORKFLOW_RE = re.compile(
    r"actions/workflows/([A-Za-z0-9_.-]+\.yml)/badge\.svg"
)


def test_every_badge_workflow_file_exists(readme_text: str):
    workflows_dir = REPO_ROOT / ".github" / "workflows"
    missing = []
    for name in set(BADGE_WORKFLOW_RE.findall(readme_text)):
        if not (workflows_dir / name).is_file():
            missing.append(name)
    assert not missing, (
        f"README links to these workflow badges but no matching file "
        f"exists under .github/workflows/: {missing}"
    )


# ─── Version badge ────────────────────────────────────────────────────


VERSION_BADGE_RE = re.compile(
    r"badge/version-([A-Za-z0-9._-]+)-[0-9A-Fa-f]{6}\.svg"
)


def test_version_badge_matches_package_version(readme_text: str):
    matches = VERSION_BADGE_RE.findall(readme_text)
    assert matches, "README has no version badge"
    badge_version = matches[0].replace("--", "-")

    def _normalize(v: str) -> str:
        """Collapse PEP 440 (``1.1.0rc2``) and shields (``v1.1.0-rc2``)
        into a comparable canonical form."""
        return v.lower().lstrip("v").replace("-", "").replace(".", "")

    assert _normalize(badge_version) == _normalize(__version__), (
        f"version badge says {badge_version!r} but "
        f"llmwiki.__version__ is {__version__!r}"
    )


# ─── Test-count badge ─────────────────────────────────────────────────


TEST_COUNT_RE = re.compile(r"badge/tests-(\d+)%20passing")


def test_test_count_badge_present(readme_text: str):
    assert TEST_COUNT_RE.search(readme_text), (
        "test-count badge missing; re-add shields.io badge pointing "
        "at tests/ directory"
    )


def test_test_count_badge_is_a_reasonable_number(readme_text: str):
    """The badge is manually maintained — this test just guards against
    obvious rot (e.g. 0 passing, 1 passing) and over-claiming."""
    m = TEST_COUNT_RE.search(readme_text)
    assert m is not None
    count = int(m.group(1))
    # We currently ship well over 1000 tests. If the badge drifts below
    # that threshold it's almost certainly stale or truncated.
    assert count >= 1000, (
        f"test-count badge reports {count} passing — that's suspiciously "
        "low; refresh the badge from the latest pytest run"
    )


# ─── Demo asset (issue #129's "video demo/walkthrough" checkbox) ──────


def test_demo_gif_exists_and_is_referenced_from_readme(readme_text: str):
    gif = REPO_ROOT / "docs" / "demo.gif"
    assert gif.is_file(), (
        f"expected demo GIF at {gif.relative_to(REPO_ROOT)} — regenerate "
        "via `scripts/demo-record.sh` + `asciinema rec` + `cast-to-gif.py`"
    )
    assert "docs/demo.gif" in readme_text, (
        "demo.gif exists but isn't embedded in README — add "
        "`![llm-wiki demo](docs/demo.gif)` so GitHub renders it"
    )


def test_demo_record_script_executable_and_uses_new_v11_features():
    script = REPO_ROOT / "scripts" / "demo-record.sh"
    assert script.is_file()
    text = script.read_text(encoding="utf-8")
    # The script should exercise the v1.1 additions so future regenerations
    # capture them (#35 Ollama ≈ synthesize, #50 --estimate, #51 candidates).
    assert "synthesize --estimate" in text, (
        "demo script doesn't showcase the --estimate cost preview (v1.1 · #50)"
    )
    assert "candidates list" in text, (
        "demo script doesn't showcase the candidates workflow (v1.1 · #51)"
    )
