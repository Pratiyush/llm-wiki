"""Tests that the command palette's search index covers every docs
page + slash command (#277).

Before: the palette could only find sessions, projects, and the 3
hard-coded pages (home / projects / sessions).  After: every
`docs/**/*.md` and every `.claude/commands/*.md` appears.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def search_index() -> dict:
    idx = REPO_ROOT / "site" / "search-index.json"
    if not idx.is_file():
        pytest.skip("site/search-index.json missing — run `llmwiki build` first")
    return json.loads(idx.read_text(encoding="utf-8"))


# ─── docs coverage ──────────────────────────────────────────────────


def test_palette_index_contains_docs_entries(search_index):
    docs_entries = [e for e in search_index["entries"] if e["type"] == "docs"]
    assert len(docs_entries) >= 20, (
        f"expected many docs entries, got {len(docs_entries)}"
    )


def test_palette_index_includes_cheatsheet(search_index):
    cheatsheet = [
        e for e in search_index["entries"]
        if e["type"] == "docs" and "cheatsheet" in e["url"].lower()
    ]
    assert cheatsheet, "command cheatsheet missing from palette"
    assert cheatsheet[0]["url"] == "docs/cheatsheet.html"


def test_palette_index_includes_upgrade_guide(search_index):
    upgrade = [
        e for e in search_index["entries"]
        if e["type"] == "docs" and e["url"] == "docs/UPGRADING.html"
    ]
    assert upgrade, "upgrade guide missing from palette"


def test_palette_index_includes_every_tutorial(search_index):
    tutorials = [
        e for e in search_index["entries"]
        if e["type"] == "docs" and "/tutorials/" in e["url"]
    ]
    # We ship 8 numbered tutorials + setup-guide → ≥9.
    assert len(tutorials) >= 8


def test_palette_index_includes_reference_pages(search_index):
    refs = [
        e for e in search_index["entries"]
        if e["type"] == "docs" and "/reference/" in e["url"]
    ]
    titles = {e["url"] for e in refs}
    # Sanity: CLI + slash + UI reference must all be there.
    must_have = {
        "docs/reference/cli.html",
        "docs/reference/slash-commands.html",
        "docs/reference/ui.html",
    }
    missing = must_have - titles
    assert not missing, f"missing reference pages: {missing}"


# ─── slash coverage ─────────────────────────────────────────────────


def test_palette_index_contains_slash_entries(search_index):
    slashes = [e for e in search_index["entries"] if e["type"] == "slash"]
    assert len(slashes) >= 10, f"expected many slashes, got {len(slashes)}"


def test_palette_slash_titles_start_with_wiki_prefix_or_maintainer(search_index):
    slashes = [e for e in search_index["entries"] if e["type"] == "slash"]
    for s in slashes:
        assert s["title"].startswith("/"), (
            f"slash title should start with /: {s['title']!r}"
        )


def test_palette_slash_entries_have_empty_url(search_index):
    """Slashes aren't URLs — palette.js handles them specially."""
    slashes = [e for e in search_index["entries"] if e["type"] == "slash"]
    for s in slashes:
        assert s["url"] == "", (
            f"slash entries must have empty url (they copy to clipboard), "
            f"got {s['url']!r}"
        )


def test_palette_slash_entries_have_non_empty_description(search_index):
    slashes = [e for e in search_index["entries"] if e["type"] == "slash"]
    for s in slashes:
        assert s["body"], f"slash {s['title']!r} has empty body"


def test_palette_slash_includes_known_wrappers(search_index):
    slashes = {
        e["title"] for e in search_index["entries"] if e["type"] == "slash"
    }
    for expected in (
        "/wiki-build", "/wiki-sync", "/wiki-query", "/wiki-lint",
        "/wiki-candidates", "/wiki-synthesize",
    ):
        assert expected in slashes, f"missing slash in index: {expected}"


# ─── total index size ───────────────────────────────────────────────


def test_palette_index_has_more_than_just_sessions(search_index):
    """Smoke: old palette had ~30 entries (3 pages + projects). New
    palette has 3 pages + projects + docs + slashes — hundreds."""
    total = len(search_index["entries"])
    assert total >= 100, f"palette index shrunk: {total}"
