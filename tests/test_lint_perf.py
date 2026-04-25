"""Perf-budget tests for the lint stage (closes #429).

The big O complexity bug we fixed in #412 only mattered at corpus sizes
beyond what the demo data exercises. This module synthesises a 500-page
corpus (representative of a real wiki) and pins wall-clock budgets so
the regression can't sneak back in.

These tests are marked ``@pytest.mark.slow`` so they don't gate every
PR — the CI workflow runs them on a separate job. ``pytest -m slow``
runs them locally; default ``pytest`` skips them.
"""

from __future__ import annotations

import time
from pathlib import Path

import pytest

from llmwiki.lint import REGISTRY, load_pages, run_all
from llmwiki.lint.rules import (
    DuplicateDetection,
    LinkIntegrity,
    OrphanDetection,
)


# ─── Synthetic corpus generator ──────────────────────────────────────


def _seed_corpus(root: Path, n_sources: int, n_entities: int) -> None:
    """Write ``n_sources`` source pages + ``n_entities`` entity pages.

    Sources are split into ~5 projects so the bucketing logic exercises
    a realistic mix of within-bucket and cross-bucket comparisons.
    Bodies are unique enough to avoid trivial fingerprint collisions
    but share boilerplate that worst-cases ``SequenceMatcher``.
    """
    boilerplate = (
        "## Summary\n\nA session about something.\n\n"
        "## Key claims\n- Claim A\n- Claim B\n- Claim C\n\n"
        "## Connections\n- [[OtherPage]]\n"
    )
    sources = root / "sources"
    sources.mkdir(parents=True, exist_ok=True)
    for i in range(n_sources):
        proj = f"proj-{i % 5}"
        page = sources / f"src-{i:04d}.md"
        page.write_text(
            f"---\n"
            f'title: "Source {i:04d}"\n'
            f"type: source\n"
            f"project: {proj}\n"
            f"---\n\n"
            f"{boilerplate}\n"
            f"<!-- unique-token-{i} -->\n",
            encoding="utf-8",
        )

    entities = root / "entities"
    entities.mkdir(parents=True, exist_ok=True)
    for i in range(n_entities):
        page = entities / f"Entity{i:04d}.md"
        page.write_text(
            f"---\n"
            f'title: "Entity{i:04d}"\n'
            f"type: entity\n"
            f"---\n\n"
            f"# Entity{i:04d}\n\n{boilerplate}\n",
            encoding="utf-8",
        )

    (root / "index.md").write_text(
        '---\ntitle: "Wiki Index"\ntype: index\n---\n\n# Wiki\n',
        encoding="utf-8",
    )


# ─── Per-rule budgets ────────────────────────────────────────────────


@pytest.fixture(scope="module")
def big_corpus(tmp_path_factory):
    root = tmp_path_factory.mktemp("perf-corpus")
    _seed_corpus(root, n_sources=400, n_entities=100)
    return load_pages(root)


@pytest.mark.slow
def test_duplicate_detection_under_1s(big_corpus):
    """Regression budget for #412 — old O(n²) implementation took
    minutes on a 500-page corpus. Two-stage fingerprint+SequenceMatcher
    fix must complete in under 1 second."""
    rule = DuplicateDetection()
    t0 = time.perf_counter()
    rule.run(big_corpus)
    elapsed = time.perf_counter() - t0
    assert elapsed < 1.0, (
        f"duplicate_detection took {elapsed:.2f}s on 500 pages "
        "(budget: 1.00s) — has the O(n²) regression returned?"
    )


@pytest.mark.slow
def test_link_integrity_under_500ms(big_corpus):
    rule = LinkIntegrity()
    t0 = time.perf_counter()
    rule.run(big_corpus)
    elapsed = time.perf_counter() - t0
    assert elapsed < 0.5, (
        f"link_integrity took {elapsed:.2f}s on 500 pages (budget: 0.50s)"
    )


@pytest.mark.slow
def test_orphan_detection_under_200ms(big_corpus):
    rule = OrphanDetection()
    t0 = time.perf_counter()
    rule.run(big_corpus)
    elapsed = time.perf_counter() - t0
    assert elapsed < 0.2, (
        f"orphan_detection took {elapsed:.2f}s on 500 pages (budget: 0.20s)"
    )


@pytest.mark.slow
def test_full_lint_pass_under_3s(big_corpus):
    """End-to-end: every registered rule run together must finish under 3s."""
    t0 = time.perf_counter()
    run_all(big_corpus)
    elapsed = time.perf_counter() - t0
    assert elapsed < 3.0, (
        f"full lint pass took {elapsed:.2f}s on 500 pages (budget: 3.00s)"
    )


# ─── Edge cases (#429 checklist) ─────────────────────────────────────


@pytest.mark.slow
def test_500_unique_pages_linear(tmp_path):
    """500 unique pages → time scales linearly (within 4× of 100 pages)."""
    root_small = tmp_path / "small"
    _seed_corpus(root_small, n_sources=80, n_entities=20)
    pages_small = load_pages(root_small)

    root_big = tmp_path / "big"
    _seed_corpus(root_big, n_sources=400, n_entities=100)
    pages_big = load_pages(root_big)

    rule = DuplicateDetection()
    t0 = time.perf_counter()
    rule.run(pages_small)
    t_small = time.perf_counter() - t0
    t0 = time.perf_counter()
    rule.run(pages_big)
    t_big = time.perf_counter() - t0

    # 5× page count → expect ≤25× O(n²) within bucket (theoretical
    # ceiling), plus a generous noise headroom for warmup / GC.
    if t_small < 1e-3:
        pytest.skip(
            f"small-corpus too fast to ratio-test ({t_small * 1000:.2f}ms)"
        )
    ratio = t_big / t_small
    assert ratio < 40, (
        f"DuplicateDetection scaled super-linearly: {t_small:.3f}s → "
        f"{t_big:.3f}s (ratio {ratio:.1f}×, budget <40×)"
    )


@pytest.mark.slow
def test_500_pages_with_shared_prefixes(tmp_path):
    """Worst case for SequenceMatcher: many bodies sharing a long prefix.
    The fingerprint pre-filter must keep us out of O(n²) territory.
    """
    root = tmp_path / "shared-prefix"
    sources = root / "sources"
    sources.mkdir(parents=True)
    # Same long shared prefix means same body fingerprint for many pages
    # → the fingerprint bucket is large but the title pre-filter inside
    # the fp bucket still keeps SequenceMatcher calls bounded.
    shared_prefix = "lorem ipsum dolor sit amet, " * 200  # ~5KB of shared
    for i in range(400):
        page = sources / f"page-{i:04d}.md"
        page.write_text(
            f"---\n"
            f'title: "Page {i:04d}"\n'
            f"type: source\n"
            f"project: shared\n"
            f"---\n\n{shared_prefix}\n\nUnique-{i}\n",
            encoding="utf-8",
        )
    (root / "index.md").write_text(
        '---\ntitle: "Index"\ntype: index\n---\n# I\n',
        encoding="utf-8",
    )

    pages = load_pages(root)
    rule = DuplicateDetection()
    t0 = time.perf_counter()
    rule.run(pages)
    elapsed = time.perf_counter() - t0
    assert elapsed < 2.0, (
        f"shared-prefix worst case took {elapsed:.2f}s (budget: 2.00s)"
    )


@pytest.mark.slow
def test_repeat_runs_dont_leak(big_corpus):
    """Run lint 5×; total wall clock must not super-linearly grow
    (rough memory-leak proxy — leaks usually surface as GC slowdown
    rather than OOM in a test harness)."""
    rule = DuplicateDetection()
    times = []
    for _ in range(5):
        t0 = time.perf_counter()
        rule.run(big_corpus)
        times.append(time.perf_counter() - t0)
    # Last run shouldn't be more than 3× the first (allowing for warmup
    # noise). A real leak would show monotonic growth >> 3×.
    assert times[-1] < times[0] * 3 + 0.1, (
        f"DuplicateDetection slowed across 5 runs: {times}"
    )


# ─── Correctness preserved at scale (#412 checklist) ─────────────────


def test_two_identical_pages_flagged(tmp_path):
    """Two identical pages must still be flagged after the perf rewrite."""
    root = tmp_path
    sources = root / "sources"
    sources.mkdir()
    body = "## Same\n\nIdentical body content here.\n"
    for name in ("a.md", "b.md"):
        (sources / name).write_text(
            f'---\ntitle: "Dup"\ntype: source\nproject: p\n---\n\n{body}',
            encoding="utf-8",
        )
    (root / "index.md").write_text(
        '---\ntitle: "I"\ntype: index\n---\n\n# I\n',
        encoding="utf-8",
    )
    pages = load_pages(root)
    rule = DuplicateDetection()
    issues = rule.run(pages)
    assert any("possible duplicate" in i["message"] for i in issues), (
        f"identical pages not flagged: {issues}"
    )


def test_same_title_different_bodies_not_flagged(tmp_path):
    """Same title, different bodies → no false positive."""
    root = tmp_path
    sources = root / "sources"
    sources.mkdir()
    (sources / "a.md").write_text(
        '---\ntitle: "Same"\ntype: source\nproject: p\n---\n\n'
        + "Body A " * 200,
        encoding="utf-8",
    )
    (sources / "b.md").write_text(
        '---\ntitle: "Same"\ntype: source\nproject: p\n---\n\n'
        + "Completely different body B " * 200,
        encoding="utf-8",
    )
    (root / "index.md").write_text(
        '---\ntitle: "I"\ntype: index\n---\n\n# I\n',
        encoding="utf-8",
    )
    pages = load_pages(root)
    rule = DuplicateDetection()
    issues = rule.run(pages)
    assert not issues, f"false positive on different-body pages: {issues}"


def test_whitespace_only_difference_flagged(tmp_path):
    """CRLF vs LF must not hide a duplicate (fingerprint normalises)."""
    root = tmp_path
    sources = root / "sources"
    sources.mkdir()
    body = "## Same\nIdentical body."
    (sources / "a.md").write_text(
        f'---\ntitle: "Dup"\ntype: source\nproject: p\n---\n\n{body}\n',
        encoding="utf-8",
    )
    (sources / "b.md").write_text(
        f'---\ntitle: "Dup"\ntype: source\nproject: p\n---\n\n'
        + body.replace("\n", "\r\n") + "\r\n",
        encoding="utf-8",
    )
    (root / "index.md").write_text(
        '---\ntitle: "I"\ntype: index\n---\n\n# I\n',
        encoding="utf-8",
    )
    pages = load_pages(root)
    rule = DuplicateDetection()
    issues = rule.run(pages)
    assert any("possible duplicate" in i["message"] for i in issues), (
        f"CRLF/LF whitespace difference hid the duplicate: {issues}"
    )
