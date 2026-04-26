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
    """No remaining `localStorage.getItem('theme')` or `setItem('theme'`."""
    # The legacy bare 'theme' key must be gone everywhere in the template.
    assert "localStorage.getItem('theme')" not in HTML_TEMPLATE
    assert "localStorage.setItem('theme'" not in HTML_TEMPLATE
    # The site's canonical key is the only one used.
    assert "localStorage.getItem('llmwiki-theme')" in HTML_TEMPLATE
    assert "localStorage.setItem('llmwiki-theme'" in HTML_TEMPLATE


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


def test_graph_template_toggle_writes_canonical_key():
    """Clicking the toolbar toggle must persist via the canonical key."""
    # Find the toggle handler block. It writes via setItem.
    toggle_section = HTML_TEMPLATE[HTML_TEMPLATE.find("themeToggle.addEventListener"):]
    # Sanity: the handler exists at all.
    assert "themeToggle.addEventListener" in HTML_TEMPLATE
    # And it writes to the canonical key only.
    assert "localStorage.setItem('llmwiki-theme'" in toggle_section
    assert "localStorage.setItem('theme'" not in toggle_section
