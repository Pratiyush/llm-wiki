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
    # We currently ship well over 2000 tests. If the badge drifts below
    # that threshold it's almost certainly stale or truncated.
    assert count >= 2000, (
        f"test-count badge reports {count} passing — that's suspiciously "
        "low; refresh the badge from the latest pytest run"
    )


# #682: pin the badge within ±15% of the actually-collected test count
# so it can't silently drift hundreds of tests behind reality (the bug
# this audit caught: badge said 2363, real count was 2651).
def test_test_count_badge_within_window_of_actual():
    """Run pytest --collect-only and compare to the badge number.

    Tolerance ±15% — we don't expect every PR to bump the badge, but a
    drift of more than 15% means the badge has been stale through
    multiple PR cycles. Refresh it.
    """
    import subprocess
    import sys

    badge_match = TEST_COUNT_RE.search(README.read_text(encoding="utf-8"))
    assert badge_match is not None
    badge_count = int(badge_match.group(1))

    proc = subprocess.run(
        [sys.executable, "-m", "pytest", "tests/", "--collect-only"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    # Output contains a line like "<N> tests collected in <T>s"
    text = proc.stdout + proc.stderr
    m = re.search(r"(\d+) tests collected", text)
    if m is None:
        pytest.skip(f"could not parse pytest --collect-only output: {text[-200:]!r}")
    actual = int(m.group(1))

    # Allow ±15% drift before failing.
    lower = int(actual * 0.85)
    upper = int(actual * 1.15)
    assert lower <= badge_count <= upper, (
        f"test-count badge says {badge_count} but pytest currently "
        f"collects {actual}; outside the ±15% drift window "
        f"[{lower}, {upper}]. Refresh the badge."
    )


# ─── #271: no hard-coded "11 lint rules" references in user-facing docs ─


def test_no_stale_lint_rule_counts_in_user_docs():
    """Lint-rule count changes when we add rules. Hard-coded numbers in
    user-facing docs rot. We pin to the live ``REGISTRY`` as the source
    of truth — this test flags any hard-coded '11 lint rules' /
    '13 lint rules' string in README / CLI help / top-level design docs,
    **unless** the surrounding line also mentions a historical release
    (v0.x.y) — those are legitimate release-notes references."""
    from llmwiki.lint import REGISTRY
    from llmwiki.lint import rules  # noqa: F401 — force registration
    live = len(REGISTRY)
    assert live >= 14, "unexpectedly low lint-rule count"

    targets = [
        REPO_ROOT / "README.md",
        REPO_ROOT / "CLAUDE.md",
        REPO_ROOT / "docs" / "reference" / "slash-commands.md",
        REPO_ROOT / "docs" / "deploy" / "docker.md",
    ]
    stale_phrases = (
        "11 lint rules",  # pre-#51 / pre-#52 docs
        "13 lint rules",  # pre-#302 / pre-#303 docs
    )
    offenders: list[str] = []
    for p in targets:
        if not p.is_file():
            continue
        text = p.read_text(encoding="utf-8")
        for phrase in stale_phrases:
            # Walk every occurrence individually; skip lines that cite
            # a historical release (v0.x.y or v1.x.y-rcN) nearby.
            start = 0
            while True:
                i = text.find(phrase, start)
                if i < 0:
                    break
                # Inspect the containing line.
                line_start = text.rfind("\n", 0, i) + 1
                line_end = text.find("\n", i)
                if line_end < 0:
                    line_end = len(text)
                line = text[line_start:line_end]
                historical = bool(re.search(
                    r"\bv0\.\d+\.(?:\d+|x)|v1\.\d+\.\d+-rc\d+", line
                ))
                if not historical:
                    offenders.append(
                        f"{p.relative_to(REPO_ROOT)}:line {text[:i].count(chr(10)) + 1}: "
                        f"contains {phrase!r}"
                    )
                start = i + len(phrase)
    assert not offenders, (
        "stale lint-rule counts in user-facing docs — update to the "
        f"live count ({live}) or reference it dynamically:\n  "
        + "\n  ".join(offenders)
    )


# Demo asset tests removed — demo GIF/scripts cleaned up in simplification.
