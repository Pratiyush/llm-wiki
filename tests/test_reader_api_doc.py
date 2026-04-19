"""Tests for docs/reference/reader-api.md (v1.2+ preview · #116).

The doc describes a contract the future hosted reader will meet. We can't
test a server that doesn't exist, but we CAN keep the doc honest:

- Every file path it claims `llmwiki build` writes must still be a real
  emission target (grep the source, not the `site/` output — the build
  shouldn't have to have been run for the tests to pass).
- Every invariant it locks in (cache_tier enum, lifecycle enum,
  confidence range, entity_type enum) must still match the code.
- Every cross-referenced doc must exist.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from llmwiki import REPO_ROOT
from llmwiki.lifecycle import LifecycleState
from llmwiki.schema import ENTITY_TYPES

# cache_tiers lands in a sibling PR (#52) — import it if present,
# otherwise fall back to the documented constants so this test suite
# stays green regardless of merge order.
try:
    from llmwiki.cache_tiers import CACHE_TIERS  # type: ignore[import-not-found]
except ImportError:
    CACHE_TIERS = ("L1", "L2", "L3", "L4")


API_DOC = REPO_ROOT / "docs" / "reference" / "reader-api.md"


@pytest.fixture(scope="module")
def doc() -> str:
    assert API_DOC.is_file(), "docs/reference/reader-api.md is missing"
    return API_DOC.read_text(encoding="utf-8")


# ─── Structure ────────────────────────────────────────────────────────


def test_doc_has_all_top_level_sections(doc: str):
    for heading in (
        "Why a contract first",
        "Shipped today",
        "Future endpoint contract",
        "Data model invariants",
        "Versioning",
        "Content negotiation",
        "Migration path",
    ):
        assert heading in doc, f"reader-api doc missing section '{heading}'"


def test_doc_documents_four_v1_endpoints(doc: str):
    # The four endpoints we're committing to for v1
    for path in ("/api/v1/bootstrap", "/api/v1/article",
                 "/api/v1/search", "/api/v1/sync"):
        assert path in doc, f"reader-api doc missing endpoint {path}"


def test_doc_marks_sync_as_internal(doc: str):
    # /sync is a local-only trigger; document that it's auth-gated so
    # no one wires it to the public internet by accident.
    idx = doc.find("/api/v1/sync")
    assert idx != -1
    # The word "internal" should appear within the next 1000 chars
    assert "internal" in doc[idx:idx + 1000].lower()


# ─── Shipped-today file list is real ──────────────────────────────────


SHIPPED_PATHS_TABLE_RE = re.compile(
    r"^\|\s*(`[^`]+`)\s*\|", re.MULTILINE
)


def _shipped_paths(doc: str) -> list[str]:
    """Pull the Path column from the 'Shipped today' table."""
    # Locate the "Shipped today" section
    start = doc.find("Shipped today")
    end = doc.find("Future endpoint contract", start)
    assert start != -1 and end != -1
    section = doc[start:end]
    return [m.strip("`") for m in SHIPPED_PATHS_TABLE_RE.findall(section)]


def test_every_shipped_path_is_emitted_by_build():
    """Every path in the shipped-today table must correspond to a real
    emission in the code (build.py / exporters.py / graph.py / …)."""
    paths = _shipped_paths(API_DOC.read_text(encoding="utf-8"))
    # Glob-style templates like '/<group>/<slug>.html' map to the route
    # patterns, not a specific file — skip those and verify only the
    # single-file emissions which should be grep-able.
    single_file_paths = [p for p in paths if "<" not in p and ">" not in p]
    assert single_file_paths, "no static paths parsed from table"

    # Collect the source of the build pipeline once.
    src_roots = [
        REPO_ROOT / "llmwiki" / "build.py",
        REPO_ROOT / "llmwiki" / "exporters.py",
        REPO_ROOT / "llmwiki" / "graph.py",
        REPO_ROOT / "llmwiki" / "manifest.py",
        REPO_ROOT / "llmwiki" / "search_facets.py",
    ]
    haystack = "\n".join(
        p.read_text(encoding="utf-8")
        for p in src_roots if p.is_file()
    )

    missing: list[str] = []
    for path in single_file_paths:
        bare = path.lstrip("/")
        # The file name must appear somewhere in the build pipeline source.
        # We intentionally accept any substring match so refactors that
        # split files don't break the test.
        if bare not in haystack:
            missing.append(path)
    assert not missing, (
        "reader-api doc lists these `Shipped today` paths, but no "
        f"llmwiki/*.py source emits them: {missing}"
    )


# ─── Data model invariants must match code ─────────────────────────────


def test_cache_tier_invariant_matches_module(doc: str):
    # Doc says: cache_tier ∈ {L1, L2, L3, L4}. Verify the module agrees.
    for tier in CACHE_TIERS:
        assert f"`{tier}`" in doc, (
            f"reader-api doc should enumerate {tier} as a valid cache_tier"
        )


def test_lifecycle_invariant_matches_module(doc: str):
    for state in LifecycleState:
        assert state.value in doc, (
            f"reader-api doc should enumerate lifecycle '{state.value}'"
        )


def test_confidence_range_invariant_matches_module(doc: str):
    # The doc says confidence is in [0, 1], never percent.
    assert "[0, 1]" in doc
    assert "percent" in doc.lower()


def test_entity_type_invariant_matches_module(doc: str):
    # All seven entity types must appear in the doc invariant list.
    for et in ENTITY_TYPES:
        assert f"`{et}`" in doc, (
            f"reader-api doc should list entity_type '{et}'"
        )


# ─── Cross-links ──────────────────────────────────────────────────────


LINK_RE = re.compile(r"\]\(([^)]+)\)")


def test_cross_linked_docs_exist(doc: str):
    """Every relative doc link (not URL) must resolve to a real file.

    `cache-tiers.md` is allowed to be missing until #52 lands its doc —
    the contract references it by name so readers can follow once both
    ship.
    """
    # Docs that are known to land in sibling PRs; the contract is allowed
    # to reference them before they exist on master.
    pending_siblings = {"cache-tiers.md"}

    missing: list[str] = []
    for target in LINK_RE.findall(doc):
        if target.startswith(("http://", "https://", "#", "mailto:")):
            continue
        # Allow anchors like `foo.md#section`
        base = target.split("#", 1)[0]
        path = (API_DOC.parent / base).resolve()
        if not path.exists() and Path(base).name not in pending_siblings:
            missing.append(target)
    assert not missing, f"reader-api doc links to missing paths: {missing}"


def test_doc_cross_references_cache_tiers(doc: str):
    # Cache tiers + brand system are the two doc siblings this contract
    # relies on; link to both so readers can navigate.
    assert "cache-tiers" in doc
    assert "brand-system" in doc


# ─── Versioning discipline ────────────────────────────────────────────


def test_doc_states_versioning_rules(doc: str):
    # Must say: additive = safe, rename = breaking, bumps to v2 keep v1
    # alive one minor.
    assert "additive" in doc.lower() or "additive-only" in doc.lower()
    assert "v2" in doc.lower() or "/v2/" in doc
    assert "breaking" in doc.lower()


# ─── Acceptance criteria from #116 ────────────────────────────────────


def test_doc_covers_required_endpoint_areas(doc: str):
    """Issue #116 called out bootstrap / article / search / sync as the
    four areas a future SPA needs. All four must be present."""
    for keyword in ("bootstrap", "article", "search", "sync"):
        assert keyword in doc.lower(), (
            f"reader-api doc should cover the '{keyword}' endpoint area"
        )
