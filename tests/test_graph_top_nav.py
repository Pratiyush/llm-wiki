"""#456: graph.html used to ship with its own standalone chrome and no
site nav, so navigating to it from the top bar made the whole nav
disappear — visually a dead end + keyboard shortcuts + Cmd+K palette
silently stopped working. Now the same `<header class="nav">` from
build.py.nav_bar() is injected at the top of the body, the back-to-site
shim and standalone theme toggle are removed (the nav has both), and
the site script.js is loaded so the palette + keyboard shortcuts work.

These tests pin the contract.
"""
from __future__ import annotations

import re
from pathlib import Path

from llmwiki.graph import write_html


def _build_minimal_graph() -> dict:
    return {
        "nodes": [{"id": "n1", "label": "n1", "type": "entities"}],
        "edges": [],
        "stats": {"total_pages": 1, "total_edges": 0, "orphans": [], "top_linked": []},
    }


def _render(tmp_path: Path) -> str:
    out = tmp_path / "graph.html"
    write_html(_build_minimal_graph(), out)
    return out.read_text(encoding="utf-8")


def test_site_nav_injected(tmp_path: Path) -> None:
    text = _render(tmp_path)
    assert '<header class="nav">' in text, "site nav missing — graph is still a dead end"
    # The nav contains the standard link set.
    for link_text in ("Home", "Projects", "Sessions", "Graph", "Docs"):
        assert f">{link_text}</a>" in text, f"nav link {link_text!r} missing"


def test_graph_link_marked_active(tmp_path: Path) -> None:
    text = _render(tmp_path)
    assert 'href="graph.html" class="active"' in text, (
        "Graph link in nav must carry class=\"active\" so users see where they are"
    )


def test_no_duplicate_theme_toggle_id(tmp_path: Path) -> None:
    """Both the site nav and the graph header would otherwise carry
    `id="theme-toggle"`, which is invalid HTML and breaks
    `getElementById` for the late-defined one."""
    text = _render(tmp_path)
    occurrences = re.findall(r'id="theme-toggle"', text)
    assert len(occurrences) == 1, (
        f"Expected exactly one #theme-toggle (site nav's), found {len(occurrences)}"
    )


def test_back_to_site_shim_removed(tmp_path: Path) -> None:
    text = _render(tmp_path)
    assert 'id="back-to-site"' not in text, (
        "the #268 lightweight back-to-site shim should be gone — the site nav "
        "has Home now"
    )


def test_site_stylesheet_loaded(tmp_path: Path) -> None:
    text = _render(tmp_path)
    assert 'href="style.css"' in text, (
        "the site stylesheet must be linked so the injected nav has its visual style"
    )


def test_site_script_loaded(tmp_path: Path) -> None:
    text = _render(tmp_path)
    assert 'src="script.js"' in text, (
        "the site script must be loaded so the palette + keyboard shortcuts work"
    )


def test_main_landmark_wraps_content(tmp_path: Path) -> None:
    """A11y — the page needs a <main id="main-content"> so the
    skip-link target works and screen readers can jump to the graph."""
    text = _render(tmp_path)
    assert '<main id="main-content">' in text
    assert "</main>" in text


def test_skip_link_present(tmp_path: Path) -> None:
    text = _render(tmp_path)
    assert 'class="skip-link"' in text and 'href="#main-content"' in text


def test_no_local_theme_listener(tmp_path: Path) -> None:
    """The graph used to attach its own click listener to #theme-toggle
    via `themeToggle.addEventListener`. With the site nav now owning that
    button (and script.js attaching the canonical handler), a duplicate
    listener would flip the theme twice per click — net no-op. Make
    sure the local handler is gone."""
    text = _render(tmp_path)
    assert "themeToggle.addEventListener" not in text
    assert "themeToggle = document.getElementById" not in text


def test_placeholder_substituted(tmp_path: Path) -> None:
    text = _render(tmp_path)
    assert "__SITE_NAV__" not in text, "template placeholder leaked into output"
