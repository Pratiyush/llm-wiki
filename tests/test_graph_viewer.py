"""Tests for the interactive knowledge-graph viewer (v1.1.0 · #118).

The template itself is HTML/JS, so we verify it from the outside:
- the Python graph builder produces the expected node/edge shape
- the rendered HTML contains every interactive feature the issue asks for
- `copy_to_site()` emits `site/graph.html`
- the site navigation exposes a "Graph" link
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

import llmwiki.graph as graph_mod
from llmwiki.graph import (
    HTML_TEMPLATE,
    build_graph,
    copy_to_site,
    scan_pages,
    write_html,
    write_json,
)


# ─── Fixtures ──────────────────────────────────────────────────────────


def _seed_wiki(tmp_path: Path) -> Path:
    """Build a minimal wiki/ tree: one entity, one concept, one orphan."""
    wiki = tmp_path / "wiki"
    (wiki / "entities").mkdir(parents=True)
    (wiki / "concepts").mkdir(parents=True)

    (wiki / "entities" / "Foo.md").write_text(
        '---\ntitle: "Foo Co."\n---\n\nFoo links to [[Bar]] and [[NonExistent]].\n',
        encoding="utf-8",
    )
    (wiki / "entities" / "Bar.md").write_text(
        '---\ntitle: "Bar Inc."\n---\n\nBar points to [[Rag]].\n',
        encoding="utf-8",
    )
    (wiki / "concepts" / "Rag.md").write_text(
        '---\ntitle: "RAG"\n---\n\nRetrieval-augmented generation.\n',
        encoding="utf-8",
    )
    # An orphan page (no inbound links)
    (wiki / "concepts" / "Orphaned.md").write_text(
        '---\ntitle: "Orphaned concept"\n---\n\nNo one links here.\n',
        encoding="utf-8",
    )
    return wiki


@pytest.fixture
def seeded_graph(tmp_path: Path, monkeypatch):
    wiki = _seed_wiki(tmp_path)
    monkeypatch.setattr(graph_mod, "WIKI_DIR", wiki)
    monkeypatch.setattr(graph_mod, "REPO_ROOT", tmp_path)
    return build_graph()


# ─── Graph builder ────────────────────────────────────────────────────


def test_scan_pages_excludes_readme(tmp_path: Path, monkeypatch):
    wiki = tmp_path / "wiki"
    wiki.mkdir()
    (wiki / "README.md").write_text("should skip", encoding="utf-8")
    (wiki / "Keep.md").write_text("keep me", encoding="utf-8")
    monkeypatch.setattr(graph_mod, "WIKI_DIR", wiki)
    monkeypatch.setattr(graph_mod, "REPO_ROOT", tmp_path)
    pages = scan_pages()
    assert "README" not in pages
    assert "Keep" in pages


def test_build_graph_computes_in_degree(seeded_graph):
    nodes = {n["id"]: n for n in seeded_graph["nodes"]}
    # Bar has 1 inbound (Foo → Bar), Rag has 1 inbound (Bar → Rag)
    assert nodes["Bar"]["in_degree"] == 1
    assert nodes["Rag"]["in_degree"] == 1
    assert nodes["Foo"]["in_degree"] == 0  # no one links to Foo
    assert nodes["Orphaned"]["in_degree"] == 0


def test_build_graph_tracks_broken_edges(seeded_graph):
    # Foo → NonExistent is broken
    broken = seeded_graph["broken_edges"]
    assert any(
        e["source"] == "Foo" and e["target"] == "NonExistent"
        for e in broken
    )


def test_build_graph_stats_include_orphans(seeded_graph):
    stats = seeded_graph["stats"]
    assert "Foo" in stats["orphans"]
    assert "Orphaned" in stats["orphans"]
    assert stats["total_pages"] == 4


# ─── HTML template: interactive features (#118) ──────────────────────


def test_template_has_search_input():
    assert 'id="search-input"' in HTML_TEMPLATE
    assert 'type="search"' in HTML_TEMPLATE


def test_template_has_click_to_navigate_handler():
    # #328: template now opens `node.site_url` (precomputed), not a
    # client-side rewrite. Nodes with site_url=None trigger a tooltip.
    assert "window.open(node.site_url" in HTML_TEMPLATE
    assert "noopener" in HTML_TEMPLATE
    assert "_flashNoSiteTooltip" in HTML_TEMPLATE


def test_template_has_stats_overlay():
    assert 'id="stats-overlay"' in HTML_TEMPLATE
    assert 'id="s-pages"' in HTML_TEMPLATE
    assert 'id="s-edges"' in HTML_TEMPLATE
    assert 'id="s-orphans"' in HTML_TEMPLATE
    assert 'id="s-hubs"' in HTML_TEMPLATE


def test_template_has_cluster_toggle():
    assert 'id="cluster-toggle"' in HTML_TEMPLATE
    assert "network.cluster(" in HTML_TEMPLATE


def test_template_has_theme_toggle_and_localstorage(tmp_path: Path):
    # #456: the theme toggle now lives in the SITE NAV (injected at
    # render time by write_html). The HTML_TEMPLATE itself only carries
    # the pre-paint reader; the click handler + setItem ship via the
    # site script.js. We verify the rendered output here so the
    # cross-page theme sync contract still holds end-to-end.
    g = {"nodes": [], "edges": [],
         "stats": {"total_pages": 0, "total_edges": 0, "orphans": [], "top_linked": []}}
    out = tmp_path / "g.html"
    write_html(g, out)
    rendered = out.read_text(encoding="utf-8")
    assert 'id="theme-toggle"' in rendered, (
        "rendered graph.html must expose a theme toggle (now via the site nav)"
    )
    # Pre-paint reader still in the template head.
    assert "localStorage.getItem('llmwiki-theme')" in HTML_TEMPLATE
    # The setItem half lives in script.js (loaded by the rendered page).
    assert 'src="script.js"' in rendered


def test_template_uses_css_vars_for_theme():
    # Dark and light palettes share CSS variable names so the toggle
    # just flips `data-theme` and the whole viewer follows.
    assert '--g-bg' in HTML_TEMPLATE
    assert '--g-text' in HTML_TEMPLATE
    assert '[data-theme="dark"]' in HTML_TEMPLATE
    assert '[data-theme="light"]' in HTML_TEMPLATE


def test_template_has_orphan_highlighting():
    # Orphan nodes get --g-orphan as border color and borderWidth: 3
    assert "--g-orphan" in HTML_TEMPLATE
    assert "isOrphan" in HTML_TEMPLATE


def test_template_has_offline_fallback_hook():
    assert 'id="offline-notice"' in HTML_TEMPLATE
    assert "typeof vis === 'undefined'" in HTML_TEMPLATE


def test_template_has_legend():
    assert 'id="legend"' in HTML_TEMPLATE
    # All four node types appear in the legend
    for kind in ("sources", "entities", "concepts", "syntheses"):
        assert kind in HTML_TEMPLATE


def test_template_uses_vis_network_cdn():
    assert "vis-network" in HTML_TEMPLATE


# ─── write_html / write_json ──────────────────────────────────────────


def test_write_html_injects_graph_json(tmp_path: Path, seeded_graph):
    out = tmp_path / "g.html"
    write_html(seeded_graph, out)
    text = out.read_text(encoding="utf-8")
    # Placeholder is fully replaced
    assert "__GRAPH_JSON__" not in text
    # The graph's nodes appear in the embedded JSON
    assert '"Foo"' in text
    assert '"Bar"' in text


def test_write_html_escapes_closing_script_tag(tmp_path: Path):
    # Defensive: a malicious label containing </script> must not
    # break out of the embedded payload.
    g = {
        "nodes": [{"id": "x", "label": "</script>", "type": "entities",
                   "in_degree": 0, "out_degree": 0, "path": "wiki/x.md"}],
        "edges": [],
        "broken_edges": [],
        "stats": {"total_pages": 1, "total_edges": 0, "broken_edges": 0,
                  "orphans": ["x"], "top_linked": [], "top_linking": []},
    }
    out = tmp_path / "g.html"
    write_html(g, out)
    text = out.read_text(encoding="utf-8")
    # Four real </script> tags exist in the rendered output now: the
    # #477 pre-paint inline block in <head>, the CDN loader, the
    # site script.js loader (#456 — graph isn't a dead end anymore),
    # and the main inline graph script. A fifth would mean the
    # </script> inside the label injected out of the payload — catch
    # that.
    assert text.count("</script>") == 4
    # And the escaped form should be present inside the JSON payload.
    assert "<\\/script>" in text


def test_write_json_roundtrip(tmp_path: Path, seeded_graph):
    out = tmp_path / "g.json"
    write_json(seeded_graph, out)
    loaded = json.loads(out.read_text(encoding="utf-8"))
    assert loaded["stats"]["total_pages"] == seeded_graph["stats"]["total_pages"]


# ─── copy_to_site() — #118 site integration ───────────────────────────


def test_copy_to_site_writes_graph_html(tmp_path: Path, seeded_graph):
    site = tmp_path / "site"
    site.mkdir()
    out = copy_to_site(site, graph=seeded_graph)
    assert out is not None
    assert out == site / "graph.html"
    assert out.is_file()
    assert "vis-network" in out.read_text(encoding="utf-8")


def test_copy_to_site_returns_none_for_empty_wiki(tmp_path: Path):
    site = tmp_path / "site"
    site.mkdir()
    empty_graph = {"nodes": [], "edges": [], "broken_edges": [],
                   "stats": {"total_pages": 0, "total_edges": 0,
                             "broken_edges": 0, "orphans": [],
                             "top_linked": [], "top_linking": []}}
    assert copy_to_site(site, graph=empty_graph) is None


def test_copy_to_site_rebuilds_graph_when_omitted(tmp_path: Path, monkeypatch):
    wiki = _seed_wiki(tmp_path)
    monkeypatch.setattr(graph_mod, "WIKI_DIR", wiki)
    monkeypatch.setattr(graph_mod, "REPO_ROOT", tmp_path)
    site = tmp_path / "site"
    site.mkdir()
    out = copy_to_site(site)
    assert out is not None and out.is_file()


# ─── Site nav integration (build.py adds "Graph" link) ───────────────


def test_site_nav_includes_graph_link():
    from llmwiki import build as build_mod
    # The nav link template lives in build.py; source-grep is the
    # lightest test that guards the registration.
    src = Path(build_mod.__file__).read_text(encoding="utf-8")
    assert '"graph.html", "Graph"' in src


# ─── Edge cases ───────────────────────────────────────────────────────


def test_graph_with_no_pages_returns_empty_stats(tmp_path: Path, monkeypatch):
    wiki = tmp_path / "wiki"
    wiki.mkdir()
    monkeypatch.setattr(graph_mod, "WIKI_DIR", wiki)
    monkeypatch.setattr(graph_mod, "REPO_ROOT", tmp_path)
    g = build_graph()
    assert g["nodes"] == []
    assert g["edges"] == []
    assert g["stats"]["total_pages"] == 0


def test_wikilink_with_alias_pipe_is_parsed(tmp_path: Path, monkeypatch):
    wiki = tmp_path / "wiki"
    (wiki / "entities").mkdir(parents=True)
    (wiki / "entities" / "A.md").write_text(
        "Link: [[Target|display text]]", encoding="utf-8"
    )
    (wiki / "entities" / "Target.md").write_text("body", encoding="utf-8")
    monkeypatch.setattr(graph_mod, "WIKI_DIR", wiki)
    monkeypatch.setattr(graph_mod, "REPO_ROOT", tmp_path)
    g = build_graph()
    nodes = {n["id"]: n for n in g["nodes"]}
    assert nodes["Target"]["in_degree"] == 1


def test_html_template_escapes_user_html():
    # The stats panel uses escapeHtml() when rendering node IDs so a
    # title like "<script>" can't inject.
    assert "escapeHtml" in HTML_TEMPLATE
    assert "&amp;" in HTML_TEMPLATE  # part of the escape table


def test_html_template_size_budget():
    # Guardrail — the template shouldn't balloon. 25 kB is plenty for
    # the interactive features we ship.
    assert len(HTML_TEMPLATE) < 25_000, (
        f"HTML template is {len(HTML_TEMPLATE)} bytes — "
        "keep it under 25 kB or split into an external .html asset"
    )


def test_graph_html_has_navigation_back_to_site(tmp_path: Path):
    """#268 was satisfied by a lightweight back-to-site shim. #456 went
    further — the full site nav is now injected at render time, which
    subsumes the shim. Regression contract: the rendered graph.html
    must reach the home page via at least one Home link in the nav."""
    g = {"nodes": [], "edges": [],
         "stats": {"total_pages": 0, "total_edges": 0, "orphans": [], "top_linked": []}}
    out = tmp_path / "g.html"
    write_html(g, out)
    text = out.read_text(encoding="utf-8")
    assert '<header class="nav">' in text, "site nav missing from rendered graph"
    # Find the Home link inside the nav.
    nav_block = text[text.find('<header class="nav">') : text.find("</header>")]
    assert 'href="index.html"' in nav_block, "Home link missing from injected nav"
    assert ">Home</a>" in nav_block
