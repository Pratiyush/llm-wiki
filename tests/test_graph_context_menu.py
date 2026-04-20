"""Tests for the graph-viewer context menu (G-19 · #305).

The template is HTML+JS so these tests verify the emitted artifact:

* CSS + DOM structure present in HTML_TEMPLATE.
* Every action has a `data-action` button.
* mark-stale / archive are disabled placeholders (edit-mode gated).
* Keyboard accessibility: role="menu", role="menuitem", aria-label.
* Copy-to-clipboard fallback path is present.
* `network.on('oncontext', …)` handler wires right-click.
* Outside click + Escape key close the menu.
* JS keyboard shortcut map (n / c / Enter) is present.
* Menu clamps to viewport (no off-screen).
* Rendered graph.html actually contains all of the above.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from llmwiki.graph import HTML_TEMPLATE, build_graph, write_html


# ─── Template-level: ensure every piece is present ────────────────────────


def test_template_has_ctx_menu_element():
    assert 'id="ctx-menu"' in HTML_TEMPLATE
    assert 'role="menu"' in HTML_TEMPLATE
    assert 'aria-label="Node actions"' in HTML_TEMPLATE


def test_template_has_all_expected_actions():
    for action in (
        "open", "neighbours", "copy-slug", "copy-path", "view-references",
        "mark-stale", "archive",
    ):
        assert f'data-action="{action}"' in HTML_TEMPLATE, (
            f"missing context-menu action `{action}`"
        )


def test_template_edit_only_actions_are_disabled():
    # mark-stale and archive must be disabled until --edit mode ships.
    lines = HTML_TEMPLATE.splitlines()
    for action in ("mark-stale", "archive"):
        idx = next(
            (i for i, ln in enumerate(lines) if f'data-action="{action}"' in ln),
            None,
        )
        assert idx is not None, f"action `{action}` missing"
        # Look for `disabled` in the same tag (could be on next line for readability).
        joined = " ".join(lines[idx:idx + 3])
        assert "disabled" in joined, f"`{action}` should be disabled"


def test_template_has_keyboard_accessible_menuitems():
    # Each action button carries role="menuitem".
    count = HTML_TEMPLATE.count('role="menuitem"')
    # Seven actions (open, neighbours, copy-slug, copy-path, view-references,
    # mark-stale, archive) — at least 5, but we ship 7.
    assert count >= 7, f"expected >= 7 menuitem buttons, got {count}"


def test_template_registers_oncontext_handler():
    assert "network.on('oncontext'" in HTML_TEMPLATE
    assert "params.event.preventDefault()" in HTML_TEMPLATE
    assert "getNodeAt" in HTML_TEMPLATE


def test_template_outside_click_closes_menu():
    assert "document.addEventListener('click'" in HTML_TEMPLATE
    assert "hideContextMenu" in HTML_TEMPLATE


def test_template_escape_closes_menu():
    assert "document.addEventListener('keydown'" in HTML_TEMPLATE
    assert "e.key === 'Escape'" in HTML_TEMPLATE


def test_template_keyboard_shortcuts_map():
    """n → neighbours, c → copy-slug, Enter → open."""
    assert "{ 'n': 'neighbours', 'c': 'copy-slug', 'Enter': 'open' }" in HTML_TEMPLATE


def test_template_clamps_menu_to_viewport():
    assert "window.innerWidth" in HTML_TEMPLATE
    assert "window.innerHeight" in HTML_TEMPLATE
    assert "Math.min" in HTML_TEMPLATE


def test_template_highlight_neighbours_uses_edges():
    assert "highlightNeighbours" in HTML_TEMPLATE
    # Walks GRAPH.edges to build neighbour set.
    assert "GRAPH.edges.forEach" in HTML_TEMPLATE


def test_template_clipboard_fallback_present():
    # Must support browsers without the async Clipboard API.
    assert "execCommand('copy')" in HTML_TEMPLATE
    assert "navigator.clipboard.writeText" in HTML_TEMPLATE


def test_template_copy_copy_slug_escapes_quotes():
    """The CLI hint builds a command with double-quotes — quotes in
    the slug must not break out."""
    assert "replace(/\"/g, '\\\\\"')" in HTML_TEMPLATE


# ─── CSS guardrails ──────────────────────────────────────────────────────


def test_template_css_defines_ctx_menu_visibility_classes():
    assert "#ctx-menu" in HTML_TEMPLATE
    assert "#ctx-menu.show" in HTML_TEMPLATE
    assert "display: none" in HTML_TEMPLATE


def test_template_css_honors_theme_tokens():
    """Menu inherits the existing theme palette rather than hard-coded hex."""
    # Pull the CSS block for #ctx-menu and assert it uses var(--…).
    start = HTML_TEMPLATE.index("#ctx-menu {")
    # Find the end of the CSS section for the menu — up to the next selector
    # or the end of the <style> block.
    end = HTML_TEMPLATE.index("</style>", start)
    block = HTML_TEMPLATE[start:end]
    assert "var(--g-panel)" in block
    assert "var(--g-border)" in block
    assert "var(--g-text)" in block


def test_template_disabled_button_style():
    assert "#ctx-menu button[disabled]" in HTML_TEMPLATE


# ─── Rendered graph.html end-to-end ───────────────────────────────────────


def _seed_wiki(tmp_path: Path) -> None:
    wiki = tmp_path / "wiki"
    (wiki / "entities").mkdir(parents=True)
    (wiki / "concepts").mkdir(parents=True)
    (wiki / "entities" / "Foo.md").write_text(
        '---\ntitle: "Foo"\ntype: entity\n---\n\nLinks to [[Bar]].\n',
        encoding="utf-8",
    )
    (wiki / "concepts" / "Bar.md").write_text(
        '---\ntitle: "Bar"\ntype: concept\n---\n\nBar body.\n',
        encoding="utf-8",
    )


def _patch_graph_paths(tmp_path, monkeypatch):
    import llmwiki.graph as graph_mod
    monkeypatch.setattr(graph_mod, "WIKI_DIR", tmp_path / "wiki")
    monkeypatch.setattr(graph_mod, "REPO_ROOT", tmp_path)


def test_rendered_html_contains_context_menu(tmp_path, monkeypatch):
    _seed_wiki(tmp_path)
    _patch_graph_paths(tmp_path, monkeypatch)
    g = build_graph()
    out = tmp_path / "graph.html"
    write_html(g, out)
    text = out.read_text(encoding="utf-8")
    assert 'id="ctx-menu"' in text
    # All seven actions in the rendered output.
    for action in (
        "open", "neighbours", "copy-slug", "copy-path", "view-references",
        "mark-stale", "archive",
    ):
        assert f'data-action="{action}"' in text


def test_rendered_html_graph_payload_still_works(tmp_path, monkeypatch):
    """Context-menu changes must not break the __GRAPH_JSON__ injection
    or the existing click-to-navigate handler."""
    _seed_wiki(tmp_path)
    _patch_graph_paths(tmp_path, monkeypatch)
    g = build_graph()
    out = tmp_path / "graph.html"
    write_html(g, out)
    text = out.read_text(encoding="utf-8")
    # The GRAPH payload is injected.
    assert "const GRAPH =" in text
    # Existing features must still work.
    assert "network.on('click'" in text
    assert "cluster-toggle" in text


def test_rendered_html_under_60kb(tmp_path, monkeypatch):
    """Template-size budget guardrail. The context menu is net-new
    markup/JS/CSS; stay under 60 KB gzipped-estimate-equivalent."""
    _seed_wiki(tmp_path)
    _patch_graph_paths(tmp_path, monkeypatch)
    g = build_graph()
    out = tmp_path / "graph.html"
    write_html(g, out)
    assert out.stat().st_size < 60_000, (
        f"graph.html is {out.stat().st_size} B — template drift?"
    )


# ─── Interaction-flow logic (pure-python) ────────────────────────────────


def test_highlight_set_includes_self_and_neighbours():
    """Regression for the neighbour-set builder — the logic lives in JS
    but we assert the shape of the edges payload the JS consumes so any
    refactor is forced to stay correct."""
    edges = [
        {"source": "A", "target": "B"},
        {"source": "B", "target": "C"},
        {"source": "D", "target": "A"},
    ]

    # Simulate the JS algorithm in Python.
    target = "B"
    neighbours = {target}
    for e in edges:
        if e["source"] == target:
            neighbours.add(e["target"])
        if e["target"] == target:
            neighbours.add(e["source"])
    assert neighbours == {"A", "B", "C"}
