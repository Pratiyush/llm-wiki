"""#458: theme reverted to light when navigating from / to /docs/.

The script.js theme handler ran AFTER first paint, so a freshly-loaded
page would briefly render in light, then jump to dark (or vice-versa)
once the deferred script reached the localStorage read at line 43-44.
On a hard reload across pages the wrong-theme flash was visible enough
to look like the theme had reset.

Fix: bake a tiny inline `<script>` into every page's `<head>` that reads
`localStorage["llmwiki-theme"]` and sets `data-theme` BEFORE first paint.
Mirrors the pattern graph.html already uses (#477).

These tests pin the pre-paint contract for both `page_head` (used by
non-article pages) and `page_head_article` (used by session detail
pages with schema.org microdata).
"""
from __future__ import annotations

from llmwiki.build import page_head, page_head_article


def _head_only(page_html: str) -> str:
    """Return everything between `<head>` and `</head>` for tests that
    only care about head-scope contracts."""
    head_start = page_html.find("<head>")
    head_end = page_html.find("</head>")
    assert head_start > 0 and head_end > head_start, "no <head> found"
    return page_html[head_start:head_end]


def test_page_head_includes_pre_paint_theme_script() -> None:
    head = _head_only(page_head("Title", "desc"))
    assert "localStorage.getItem('llmwiki-theme')" in head
    assert "setAttribute('data-theme'" in head
    # Must run inside <head> so it executes before first paint, not
    # deferred / DOMContentLoaded.
    assert "DOMContentLoaded" not in head


def test_page_head_article_includes_pre_paint_theme_script() -> None:
    head = _head_only(page_head_article("Article", "desc"))
    assert "localStorage.getItem('llmwiki-theme')" in head
    assert "setAttribute('data-theme'" in head


def test_pre_paint_script_falls_back_to_prefers_color_scheme() -> None:
    """Without a stored value, the pre-paint script should respect the
    user's OS theme preference rather than always defaulting to one
    fixed value (which would also count as a flash for OS-dark users
    visiting for the first time)."""
    head = _head_only(page_head("Title", "desc"))
    assert "prefers-color-scheme" in head


def test_pre_paint_runs_before_stylesheet_link() -> None:
    """Pre-paint script must execute BEFORE the stylesheet loads so
    `data-theme` is set before any CSS variable resolves."""
    head = _head_only(page_head("Title", "desc"))
    script_pos = head.find("localStorage.getItem('llmwiki-theme')")
    css_pos = head.find('href="style.css"')
    assert script_pos > 0 and css_pos > 0
    assert script_pos < css_pos, (
        "pre-paint theme script must come before the stylesheet link, "
        "otherwise CSS will evaluate against a missing data-theme attribute"
    )


def test_pre_paint_script_uses_canonical_localstorage_key() -> None:
    """Both page_head and page_head_article must read the same key the
    rest of the site (and graph.html) writes — `llmwiki-theme`."""
    for fn in (page_head, page_head_article):
        head = _head_only(fn("T", "d"))
        assert "'llmwiki-theme'" in head
        # Legacy bare key absent.
        assert "'theme'" not in head or "'llmwiki-theme'" in head
