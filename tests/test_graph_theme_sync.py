"""Tests for #477 — graph viewer theme key sync with the rest of the site.

The bug: `llmwiki/graph.py` wrote `localStorage["theme"]` but the rest of
the site uses `localStorage["llmwiki-theme"]`. Toggling theme on the
graph never persisted to /, /docs/, /sessions/, etc., and vice-versa.
The graph template also hardcoded `<html data-theme="dark">` so light-
mode users always saw a dark graph regardless of OS / site preference.

The fix:
  1. Standardise on `llmwiki-theme` for both read + write in graph.py.
  2. Drop the hardcoded `data-theme="dark"` attribute on `<html>`.
  3. Add a pre-paint inline `<script>` that reads localStorage (with
     `prefers-color-scheme` fallback) BEFORE first paint to eliminate
     the flash of wrong theme.
"""

from __future__ import annotations

from llmwiki.graph import HTML_TEMPLATE


def test_graph_template_uses_llmwiki_theme_key():
    """No remaining `localStorage.getItem('theme')` or `setItem('theme'`.

    #456: the standalone toggle (and its setItem call) was removed from
    the graph template — that responsibility now lives in the site nav,
    wired by script.js. The pre-paint reader stays in the template.
    """
    # The legacy bare 'theme' key must be gone everywhere in the template.
    assert "localStorage.getItem('theme')" not in HTML_TEMPLATE
    assert "localStorage.setItem('theme'" not in HTML_TEMPLATE
    # The pre-paint script reads the canonical key.
    assert "localStorage.getItem('llmwiki-theme')" in HTML_TEMPLATE


def test_graph_template_has_no_hardcoded_data_theme_dark():
    """`<html data-theme="dark">` was the override that broke light mode.

    The pre-paint script sets the attribute from storage; the markup
    must not race against it.
    """
    assert '<html lang="en" data-theme="dark">' not in HTML_TEMPLATE
    # The only `<html>` tag should be the bare lang-only form.
    assert '<html lang="en">' in HTML_TEMPLATE


def test_graph_template_has_pre_paint_theme_script():
    """The pre-paint script must run inside <head> before the body
    renders so users never see a flash of wrong theme."""
    head_start = HTML_TEMPLATE.find("<head>")
    head_end = HTML_TEMPLATE.find("</head>")
    assert head_start > 0 and head_end > head_start
    head = HTML_TEMPLATE[head_start:head_end]
    # The pre-paint script must reference the canonical key + the
    # prefers-color-scheme fallback.
    assert "llmwiki-theme" in head
    assert "prefers-color-scheme" in head
    assert "data-theme" in head


def test_graph_template_toggle_writes_canonical_key(tmp_path):
    """Clicking the nav theme toggle must persist via the canonical key.

    #456: the toggle moved out of the graph template into the site nav.
    The contract is now end-to-end: the rendered graph.html loads
    script.js (which carries the click handler that writes
    `localStorage.llmwiki-theme`) and exposes one `id="theme-toggle"`
    in the nav for that handler to bind to. The graph's own
    `themeToggle.addEventListener` block is intentionally gone — a
    duplicate would flip the theme twice per click.
    """
    from pathlib import Path
    from llmwiki.graph import write_html
    g = {"nodes": [], "edges": [],
         "stats": {"total_pages": 0, "total_edges": 0, "orphans": [], "top_linked": []}}
    out: Path = tmp_path / "graph.html"
    write_html(g, out)
    rendered = out.read_text(encoding="utf-8")
    # script.js (which carries the canonical setItem call) is loaded.
    assert 'src="script.js"' in rendered
    # The nav exposes a unique #theme-toggle for that handler.
    assert rendered.count('id="theme-toggle"') == 1
    # The local handler must be gone from the template.
    assert "themeToggle.addEventListener" not in HTML_TEMPLATE
