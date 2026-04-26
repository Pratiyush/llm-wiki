"""Knowledge graph builder for llmwiki.

Walks every file under `wiki/` looking for `[[wikilink]]` references, builds a
node-and-edge list, writes `graph/graph.json`, and generates an interactive
`graph/graph.html` using vis.js loaded from a CDN (optional offline fallback).

Stdlib only — no networkx, no vis.js bundled.

Usage:

    python3 -m llmwiki graph              # writes graph/graph.json + graph.html
    python3 -m llmwiki graph --json       # json only
    python3 -m llmwiki graph --html       # html only
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any, Optional

from llmwiki import REPO_ROOT

WIKI_DIR = REPO_ROOT / "wiki"
GRAPH_DIR = REPO_ROOT / "graph"

WIKILINK_RE = re.compile(r"\[\[([^\]|]+)(?:\|[^\]]*)?\]\]")

# #328: wiki-layer pages that have no corresponding site HTML page.
# Graph clicks on these used to 404 — the viewer now disables the click
# and shows a tooltip.  We keep the node + edges (for the graph
# topology) but mark `site_url = None`.
_NO_SITE_TYPES = {"entities", "concepts", "syntheses", "questions",
                  "comparisons", "hot", "categories", "projects_meta"}
_NO_SITE_BASENAMES = {
    "CRITICAL_FACTS", "MEMORY", "SOUL",
    "hints", "hot", "dashboard", "overview",
    "log", "log-archive-2026",
}


def _compute_site_url(text: str, rel_parts: tuple[str, ...],
                      slug: str, type_: str) -> str | None:
    """Map a wiki page to its generated site URL (or ``None`` when no
    site page exists).

    * ``wiki/index.md`` → ``index.html``
    * ``wiki/projects/<slug>.md`` → ``projects/<slug>.html``
    * ``wiki/sources/<proj>/<stem>.md`` → the matching ``sessions/<proj>/<date-stem>.html``
      (looked up from the ``source_file`` frontmatter field, because wiki source
      pages use bare slugs but site session pages use date-prefixed stems).
    * entities / concepts / syntheses / nav files → None

    Never raises — returns ``None`` on any lookup miss so the caller can
    gracefully disable the click.
    """
    if slug == "index" and len(rel_parts) == 1:
        return "index.html"
    if len(rel_parts) >= 2 and rel_parts[0] == "projects":
        return f"projects/{slug}.html"
    if len(rel_parts) >= 2 and rel_parts[0] == "sources":
        # Find the matching site/sessions/ path via the source_file frontmatter.
        m = re.search(r"^source_file:\s*(.+)$", text, re.MULTILINE)
        if not m:
            return None
        sf = m.group(1).strip().strip("'\"")
        # sf looks like ``raw/sessions/<proj>/<stem>.md`` or ``raw/sessions/<stem>.md``
        try:
            rel = sf.split("raw/sessions/", 1)[1]
        except IndexError:
            return None
        rel = rel.removesuffix(".md")
        return f"sessions/{rel}.html"
    if type_ in _NO_SITE_TYPES:
        return None
    if slug in _NO_SITE_BASENAMES:
        return None
    return None


def scan_pages() -> dict[str, dict[str, Any]]:
    """Return a dict {slug: {path, type, title, out_links, site_url}}."""
    pages: dict[str, dict[str, Any]] = {}
    if not WIKI_DIR.exists():
        return pages
    for p in sorted(WIKI_DIR.rglob("*.md")):
        slug = p.stem
        if slug in ("README",):
            continue
        # Type = parent directory name when under sources/entities/concepts/etc.
        try:
            rel = p.relative_to(WIKI_DIR)
            type_ = rel.parts[0] if len(rel.parts) > 1 else "root"
        except ValueError:
            type_ = "root"
        title = slug
        try:
            text = p.read_text(encoding="utf-8")
        except OSError:
            continue
        # Extract title from frontmatter if present
        title_match = re.search(r'^title:\s*"?([^"\n]+)', text, re.MULTILINE)
        if title_match:
            title = title_match.group(1).strip('"')
        # Extract wikilinks
        out_links = set(WIKILINK_RE.findall(text))
        site_url = _compute_site_url(text, rel.parts, slug, type_)
        pages[slug] = {
            "path": str(p.relative_to(REPO_ROOT)),
            "type": type_,
            "title": title,
            "out_links": out_links,
            "site_url": site_url,
        }
    return pages


def _verify_site_url(site_url: str | None, site_dir: Path | None) -> str | None:
    """Return ``site_url`` unchanged if the file exists, else ``None``.

    #328: prevents the viewer from offering links that 404.  When
    ``site_dir`` is ``None`` (graph built before the site has been
    compiled) we keep the URL as-is — the caller is telling us the
    site doesn't exist yet, and we'd rather have a 404 than drop
    every session link.
    """
    if not site_url or site_dir is None:
        return site_url
    if not site_dir.is_dir():
        return site_url
    return site_url if (site_dir / site_url).is_file() else None


def build_graph(verify_site_dir: Path | None = None) -> dict[str, Any]:
    """Build the knowledge graph.

    ``verify_site_dir``: when given and the directory exists, each
    node's ``site_url`` is validated against the compiled site — URLs
    pointing at non-existent files are nulled so the viewer shows a
    graceful tooltip instead of 404ing.  Defaults to ``site/`` under
    ``REPO_ROOT`` when called from ``copy_to_site`` (see below).
    """
    pages = scan_pages()
    if verify_site_dir is not None:
        for p in pages.values():
            p["site_url"] = _verify_site_url(p.get("site_url"), verify_site_dir)

    # Compute in-degree
    in_deg: dict[str, int] = {slug: 0 for slug in pages}
    for slug, page in pages.items():
        for target in page["out_links"]:
            if target in in_deg:
                in_deg[target] += 1

    # Nodes
    nodes = []
    for slug, page in pages.items():
        nodes.append(
            {
                "id": slug,
                "label": page["title"],
                "type": page["type"],
                "path": page["path"],
                # #328: map wiki page → real site HTML URL so clicks don't 404.
                # None for pages that have no compiled site page.
                "site_url": page.get("site_url"),
                "in_degree": in_deg.get(slug, 0),
                "out_degree": len(page["out_links"]),
            }
        )

    # Edges
    edges = []
    broken_edges = []
    for slug, page in pages.items():
        for target in page["out_links"]:
            if target in pages:
                edges.append({"source": slug, "target": target})
            else:
                broken_edges.append({"source": slug, "target": target, "broken": True})

    return {
        "nodes": nodes,
        "edges": edges,
        "broken_edges": broken_edges,
        "stats": {
            "total_pages": len(pages),
            "total_edges": len(edges),
            "broken_edges": len(broken_edges),
            "orphans": [n["id"] for n in nodes if n["in_degree"] == 0],
            "top_linked": sorted(nodes, key=lambda n: -n["in_degree"])[:5],
            "top_linking": sorted(nodes, key=lambda n: -n["out_degree"])[:5],
        },
    }


def write_json(graph: dict[str, Any], out_path: Path) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(graph, indent=2), encoding="utf-8")


HTML_TEMPLATE = r"""<!DOCTYPE html>
<html lang="en">
<head>
<script>
  // #477: read the same localStorage key the rest of the site uses
  // ("llmwiki-theme") BEFORE first paint to avoid a flash of the wrong
  // theme. Falls back to system preference, then dark.
  (function () {
    try {
      var t = localStorage.getItem('llmwiki-theme');
      if (!t) {
        t = (window.matchMedia && window.matchMedia('(prefers-color-scheme: light)').matches) ? 'light' : 'dark';
      }
      document.documentElement.setAttribute('data-theme', t);
    } catch (e) {
      document.documentElement.setAttribute('data-theme', 'dark');
    }
  })();
</script>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>llmwiki — Knowledge Graph</title>
<!-- #456: pull in the same site stylesheet so the top nav we inject below
     looks identical to every other page on the site. Loaded BEFORE the
     graph's own <style> block so graph-specific selectors (#header, #network,
     etc.) keep their precedence and the visualization layout is untouched. -->
<link rel="stylesheet" href="style.css">
<style>
  /* Theme vars — mirror the site palette so dark/light sync works. */
  :root[data-theme="dark"] {
    --g-bg: #0c0a1d;
    --g-panel: #110f26;
    --g-border: #2d2b4a;
    --g-text: #e2e8f0;
    --g-muted: #94a3b8;
    --g-accent: #a78bfa;
    --g-node-source: #7c3aed;
    --g-node-entities: #2563eb;
    --g-node-concepts: #059669;
    --g-node-syntheses: #d97706;
    --g-node-root: #64748b;
    --g-orphan: #ef4444;
    --g-edge: rgba(148, 163, 184, 0.4);
    --g-highlight: #facc15;
  }
  :root[data-theme="light"] {
    --g-bg: #f8fafc;
    --g-panel: #ffffff;
    --g-border: #e2e8f0;
    --g-text: #0f172a;
    --g-muted: #475569;
    --g-accent: #7c3aed;
    --g-node-source: #7c3aed;
    --g-node-entities: #2563eb;
    --g-node-concepts: #059669;
    --g-node-syntheses: #d97706;
    --g-node-root: #64748b;
    --g-orphan: #dc2626;
    --g-edge: rgba(100, 116, 139, 0.45);
    --g-highlight: #ca8a04;
  }

  html, body {
    margin: 0; padding: 0; height: 100%;
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
    background: var(--g-bg); color: var(--g-text);
    transition: background 0.2s, color 0.2s;
  }
  #header {
    padding: 12px 20px; border-bottom: 1px solid var(--g-border);
    background: var(--g-panel);
    display: flex; align-items: center; gap: 16px; flex-wrap: wrap;
  }
  #header h1 { margin: 0; font-size: 1.05rem; font-weight: 600; flex: 0 0 auto; }
  #header .crumbs { font-size: 0.82rem; color: var(--g-muted); }
  #header .spacer { flex: 1 1 auto; }

  .control {
    display: inline-flex; align-items: center; gap: 6px;
    padding: 6px 10px; border: 1px solid var(--g-border); border-radius: 6px;
    background: var(--g-bg); color: var(--g-text);
    font-size: 0.82rem; cursor: pointer;
    transition: background 0.15s, border-color 0.15s;
  }
  .control:hover { border-color: var(--g-accent); }
  .control input {
    border: none; outline: none; background: transparent;
    color: var(--g-text); font-size: 0.82rem; min-width: 160px;
  }
  .control input::placeholder { color: var(--g-muted); }

  /* #456: site nav above the graph subheader takes ~56px; subheader itself
     ~58px. Subtract both so the canvas fills the remaining viewport. */
  #network { width: 100%; height: calc(100vh - 56px - 58px); position: relative; }

  /* Orphan highlight: nodes with 0 inbound links get a red stroke.
     This matches the issue's "orphan pages glow red" requirement. */

  #stats-overlay {
    position: absolute; bottom: 16px; right: 16px;
    background: var(--g-panel); border: 1px solid var(--g-border);
    border-radius: 8px; padding: 12px 16px;
    max-width: 280px; font-size: 0.8rem;
    box-shadow: 0 6px 24px rgba(0, 0, 0, 0.3);
    backdrop-filter: blur(4px);
    z-index: 10;
  }
  #stats-overlay h3 {
    margin: 0 0 8px 0; font-size: 0.78rem;
    text-transform: uppercase; letter-spacing: 0.04em;
    color: var(--g-muted);
  }
  #stats-overlay .stat { display: flex; justify-content: space-between; padding: 2px 0; }
  #stats-overlay .stat b { color: var(--g-text); }
  #stats-overlay .hub-item { font-family: ui-monospace, monospace; font-size: 0.75rem; color: var(--g-muted); }
  #stats-overlay .hub-item b { color: var(--g-accent); }

  #legend {
    position: absolute; top: 16px; right: 16px;
    background: var(--g-panel); border: 1px solid var(--g-border);
    border-radius: 8px; padding: 10px 14px;
    font-size: 0.75rem; z-index: 10;
  }
  #legend .dot {
    display: inline-block; width: 10px; height: 10px;
    border-radius: 50%; margin-right: 6px; vertical-align: middle;
  }
  #legend .row { padding: 2px 0; color: var(--g-muted); }

  #offline-notice {
    position: absolute; inset: 0; display: none;
    align-items: center; justify-content: center;
    background: var(--g-bg); color: var(--g-muted);
    font-size: 0.9rem; z-index: 20;
  }
  #offline-notice.show { display: flex; }

  /* G-19 (#305): node context menu — shown on right-click or long-tap.
     Keyboard-accessible; closes on Escape / outside click. */
  #ctx-menu {
    position: absolute; display: none; z-index: 30;
    min-width: 220px;
    background: var(--g-panel); border: 1px solid var(--g-border);
    border-radius: 8px; padding: 4px; font-size: 0.82rem;
    box-shadow: 0 8px 30px rgba(0, 0, 0, 0.35);
  }
  #ctx-menu.show { display: block; }
  #ctx-menu .ctx-header {
    padding: 6px 10px; font-family: ui-monospace, monospace;
    font-size: 0.75rem; color: var(--g-muted);
    border-bottom: 1px solid var(--g-border); margin-bottom: 4px;
  }
  #ctx-menu button {
    display: block; width: 100%; text-align: left;
    padding: 7px 10px; border: 0; border-radius: 5px;
    background: transparent; color: var(--g-text);
    font-size: 0.82rem; cursor: pointer;
    font-family: inherit;
  }
  #ctx-menu button:hover:not([disabled]),
  #ctx-menu button:focus:not([disabled]) {
    background: rgba(124, 58, 237, 0.18);
    outline: none;
  }
  #ctx-menu button[disabled] {
    color: var(--g-muted); cursor: not-allowed; opacity: 0.55;
  }
  #ctx-menu .ctx-kbd {
    float: right; font-family: ui-monospace, monospace;
    font-size: 0.7rem; color: var(--g-muted);
    margin-left: 12px;
  }
  #ctx-menu .ctx-separator {
    height: 1px; background: var(--g-border);
    margin: 4px -4px;
  }

  a { color: var(--g-accent); }

  @media (max-width: 640px) {
    #stats-overlay, #legend { max-width: 180px; font-size: 0.72rem; }
  }
</style>
<!-- #ui-h14 (#571): pin vis-network to a specific version + SRI hash so
     a malicious or accidental upstream change can't ship code to every
     visitor of the site. Bump the version + regenerate integrity via
     `curl -s <url> | openssl dgst -sha384 -binary | openssl base64 -A`
     when upgrading. -->
<script src="https://unpkg.com/vis-network@9.1.9/standalone/umd/vis-network.min.js"
        integrity="sha384-yxKDWWf0wwdUj/gPeuL11czrnKFQROnLgY8ll7En9NYoXibgg3C6NK/UDHNtUgWJ"
        crossorigin="anonymous"
        referrerpolicy="no-referrer"></script>
</head>
<body>
<a href="#main-content" class="skip-link">Skip to content</a>
__SITE_NAV__
<main id="main-content">
<div id="header">
  <h1>llmwiki — Knowledge Graph</h1>
  <span class="crumbs" id="top-crumbs"></span>
  <span class="spacer"></span>
  <label class="control" title="Filter nodes by label">
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/></svg>
    <input id="search-input" type="search" placeholder="Search nodes… (type to filter)" autocomplete="off">
  </label>
  <button class="control" id="cluster-toggle" title="Group nodes by project / type">
    Cluster: <b id="cluster-mode">off</b>
  </button>
  <!-- #456: removed the standalone back-to-site link and theme toggle —
       both responsibilities now live in the site nav above. The site's
       script.js wires #theme-toggle (in the nav) to data-theme +
       localStorage.llmwiki-theme; the graph's CSS reacts to data-theme
       via :root[data-theme=...] selectors so the visualization re-themes
       in lockstep without needing a duplicate ID here. -->
</div>

<div id="network">
  <div id="offline-notice">vis-network failed to load — check your connection or host the library locally.</div>
  <div id="legend" aria-label="Node color legend">
    <div class="row"><span class="dot" style="background: var(--g-node-source)"></span>sources</div>
    <div class="row"><span class="dot" style="background: var(--g-node-entities)"></span>entities</div>
    <div class="row"><span class="dot" style="background: var(--g-node-concepts)"></span>concepts</div>
    <div class="row"><span class="dot" style="background: var(--g-node-syntheses)"></span>syntheses</div>
    <div class="row"><span class="dot" style="border: 2px solid var(--g-orphan); background: transparent"></span>orphan</div>
  </div>
  <div id="stats-overlay" aria-label="Graph statistics">
    <h3>Stats</h3>
    <div class="stat"><span>Pages</span><b id="s-pages">0</b></div>
    <div class="stat"><span>Edges</span><b id="s-edges">0</b></div>
    <div class="stat"><span>Orphans</span><b id="s-orphans">0</b></div>
    <div class="stat"><span>Avg connections</span><b id="s-avg">0</b></div>
    <h3 style="margin-top: 10px;">Top hubs</h3>
    <div id="s-hubs"></div>
  </div>
  <!-- G-19 (#305) node context menu — right-click / long-tap target -->
  <div id="ctx-menu" role="menu" aria-label="Node actions">
    <div class="ctx-header" id="ctx-target">—</div>
    <button type="button" role="menuitem" data-action="open">Open page <span class="ctx-kbd">Enter</span></button>
    <button type="button" role="menuitem" data-action="neighbours">Find neighbours (1-hop) <span class="ctx-kbd">N</span></button>
    <button type="button" role="menuitem" data-action="copy-slug">Copy slug <span class="ctx-kbd">C</span></button>
    <button type="button" role="menuitem" data-action="copy-path">Copy wiki path</button>
    <button type="button" role="menuitem" data-action="view-references">View references (CLI hint)</button>
    <div class="ctx-separator" role="separator"></div>
    <button type="button" role="menuitem" data-action="mark-stale" disabled
            title="Requires `llmwiki serve --edit` (not yet shipped)">
      Mark stale
    </button>
    <button type="button" role="menuitem" data-action="archive" disabled
            title="Requires `llmwiki serve --edit` (not yet shipped)">
      Archive
    </button>
  </div>
</div>
</main>
<!-- #456: load the site's script.js so the nav's command palette,
     theme toggle, and keyboard shortcuts (g h / g p / g s / / / ?) work
     here too. The site's theme handler reads & writes the same
     localStorage key (`llmwiki-theme`) the pre-paint script in <head>
     reads, so the graph's data-theme stays in sync without a local
     handler. -->
<script src="script.js" defer></script>

<script>
'use strict';
const GRAPH = __GRAPH_JSON__;

// #456: graph used to wire its own #theme-toggle button + #theme-label.
// Both responsibilities now live in the site nav (script.js handles the
// click; CSS variables react to data-theme automatically). Local handler
// removed so two listeners don't fight over the same event.
const root = document.documentElement;

// ─── Check vis-network loaded (local fallback hook) ────────────────────
if (typeof vis === 'undefined') {
  document.getElementById('offline-notice').classList.add('show');
} else {
  main();
}

function main() {
  const cssVar = name =>
    getComputedStyle(document.documentElement).getPropertyValue(name).trim() || '#7c3aed';
  const colors = {
    sources: () => cssVar('--g-node-source'),
    entities: () => cssVar('--g-node-entities'),
    concepts: () => cssVar('--g-node-concepts'),
    syntheses: () => cssVar('--g-node-syntheses'),
    root: () => cssVar('--g-node-root'),
  };
  const orphanColor = () => cssVar('--g-orphan');

  // ─── Stats overlay ───────────────────────────────────────────────────
  const stats = GRAPH.stats || {};
  const pages = stats.total_pages ?? GRAPH.nodes.length;
  const edgeCount = stats.total_edges ?? GRAPH.edges.length;
  const orphans = stats.orphans ?? [];
  document.getElementById('s-pages').textContent = pages;
  document.getElementById('s-edges').textContent = edgeCount;
  document.getElementById('s-orphans').textContent = orphans.length;
  document.getElementById('s-avg').textContent =
    pages > 0 ? (edgeCount / pages).toFixed(2) : '0';
  document.getElementById('top-crumbs').textContent =
    pages + ' pages · ' + edgeCount + ' edges · ' + orphans.length + ' orphans';

  const hubsEl = document.getElementById('s-hubs');
  (stats.top_linked || []).slice(0, 5).forEach(n => {
    if (!n || n.in_degree === 0) return;
    const row = document.createElement('div');
    row.className = 'hub-item';
    row.innerHTML = '<b>' + String(n.in_degree).padStart(3) + '</b> ' +
      escapeHtml(n.id);
    hubsEl.appendChild(row);
  });

  // ─── Build vis DataSets ──────────────────────────────────────────────
  const nodes = new vis.DataSet(GRAPH.nodes.map(n => {
    const isOrphan = n.in_degree === 0;
    return {
      id: n.id,
      label: n.label,
      color: {
        background: (colors[n.type] || colors.root)(),
        border: isOrphan ? orphanColor() : (colors[n.type] || colors.root)(),
        highlight: { background: cssVar('--g-highlight'), border: cssVar('--g-highlight') },
      },
      borderWidth: isOrphan ? 3 : 1,
      value: Math.max(n.in_degree, 1),
      group: n.type,
      title:
        n.type + ' · ' + n.in_degree + ' inbound, ' + n.out_degree + ' outbound' +
        (n.path ? '\nClick to open ' + n.path : ''),
      path: n.path,
      type: n.type,
    };
  }));
  const edges = new vis.DataSet(GRAPH.edges.map(e => ({
    from: e.source,
    to: e.target,
    arrows: 'to',
    color: { color: cssVar('--g-edge') },
    title: e.source + ' → ' + e.target,
  })));

  // ─── Render network ──────────────────────────────────────────────────
  const container = document.getElementById('network');
  const network = new vis.Network(container, { nodes, edges }, {
    nodes: {
      shape: 'dot',
      font: { color: cssVar('--g-text'), size: 12, face: 'system-ui' },
      scaling: { min: 8, max: 32, label: { enabled: true, min: 10, max: 18 } },
    },
    edges: { smooth: { enabled: true, type: 'dynamic' } },
    physics: {
      barnesHut: { gravitationalConstant: -4000, springLength: 120, springConstant: 0.03 },
      stabilization: { iterations: 200 },
    },
    interaction: { hover: true, tooltipDelay: 120 },
  });

  // ─── Click-to-navigate (#328) ────────────────────────────────────────
  // Use the precomputed `site_url` on each node instead of rewriting
  // paths client-side. Nodes without a compiled site page (entities,
  // concepts, nav files) have site_url === null — click shows a
  // transient tooltip instead of opening a broken link.
  network.on('click', params => {
    if (!params.nodes || !params.nodes.length) return;
    const node = nodes.get(params.nodes[0]);
    if (!node) return;
    if (node.site_url) {
      window.open(node.site_url, '_blank', 'noopener');
    } else {
      _flashNoSiteTooltip(node, params.event);
    }
  });

  // Transient "no page" hint for entity / concept / nav nodes.
  function _flashNoSiteTooltip(node, ev) {
    const tip = document.createElement('div');
    tip.textContent = node.label + ' — no compiled page (see ## Connections)';
    tip.style.cssText =
      'position:fixed;z-index:50;padding:6px 10px;border-radius:6px;' +
      'background:var(--g-panel);border:1px solid var(--g-border);' +
      'color:var(--g-muted);font-size:0.78rem;' +
      'pointer-events:none;transition:opacity 0.3s;';
    tip.style.left = (ev.clientX + 12) + 'px';
    tip.style.top = (ev.clientY + 12) + 'px';
    document.body.appendChild(tip);
    setTimeout(() => { tip.style.opacity = '0'; }, 1400);
    setTimeout(() => { tip.remove(); }, 1800);
  }

  // ─── G-19 (#305): node context menu ──────────────────────────────────
  // The context menu is wired up only when its DOM nodes are present.
  // Closes #386 — a minimal graph render without these elements would
  // throw on the addEventListener calls below.
  const ctxMenu = document.getElementById('ctx-menu');
  const ctxTarget = document.getElementById('ctx-target');
  let ctxNode = null;

  function showContextMenu(nodeId, clientX, clientY) {
    const node = nodes.get(nodeId);
    if (!node) return;
    ctxNode = node;
    ctxTarget.textContent = node.label || node.id;
    // Position the menu, clamped inside the viewport.
    ctxMenu.style.left = '0px';
    ctxMenu.style.top = '0px';
    ctxMenu.classList.add('show');
    const rect = ctxMenu.getBoundingClientRect();
    const maxX = window.innerWidth - rect.width - 8;
    const maxY = window.innerHeight - rect.height - 8;
    ctxMenu.style.left = Math.min(clientX, maxX) + 'px';
    ctxMenu.style.top = Math.min(clientY, maxY) + 'px';
    const first = ctxMenu.querySelector('button:not([disabled])');
    if (first) first.focus();
  }

  function hideContextMenu() {
    ctxMenu.classList.remove('show');
    ctxNode = null;
  }

  network.on('oncontext', params => {
    params.event.preventDefault();
    const nodeId = network.getNodeAt(params.pointer.DOM);
    if (nodeId) {
      showContextMenu(nodeId, params.event.clientX, params.event.clientY);
    } else {
      hideContextMenu();
    }
  });

  document.addEventListener('click', e => {
    if (!ctxMenu.contains(e.target)) hideContextMenu();
  });
  document.addEventListener('keydown', e => {
    if (e.key === 'Escape' && ctxMenu.classList.contains('show')) {
      e.preventDefault();
      hideContextMenu();
    }
  });

  // Highlight the 1-hop neighbourhood of `nodeId`; dim everything else.
  function highlightNeighbours(nodeId) {
    const neighbourIds = new Set([nodeId]);
    GRAPH.edges.forEach(e => {
      if (e.source === nodeId) neighbourIds.add(e.target);
      if (e.target === nodeId) neighbourIds.add(e.source);
    });
    const update = [];
    nodes.forEach(n => {
      const inSet = neighbourIds.has(n.id);
      update.push({
        id: n.id,
        color: inSet
          ? baseColors[n.id]
          : { background: 'rgba(100,100,100,0.12)', border: 'rgba(100,100,100,0.25)' },
      });
    });
    nodes.update(update);
  }

  async function copyToClipboard(text) {
    try {
      await navigator.clipboard.writeText(text);
      return true;
    } catch (_) {
      // Fallback: textarea trick for older browsers / privacy mode.
      const ta = document.createElement('textarea');
      ta.value = text;
      ta.style.position = 'fixed'; ta.style.opacity = '0';
      document.body.appendChild(ta);
      ta.focus(); ta.select();
      let ok = false;
      try { ok = document.execCommand('copy'); } catch (_) {}
      document.body.removeChild(ta);
      return ok;
    }
  }

  if (ctxMenu) ctxMenu.addEventListener('click', async e => {
    const btn = e.target.closest('button[data-action]');
    if (!btn || btn.disabled || !ctxNode) return;
    const action = btn.dataset.action;
    const node = ctxNode;
    hideContextMenu();
    switch (action) {
      case 'open': {
        // #328: use precomputed site_url so nodes without a compiled
        // page degrade gracefully instead of 404.
        if (node.site_url) {
          window.open(node.site_url, '_blank', 'noopener');
        } else {
          alert(node.label + ' — no compiled page exists for this node. '
            + 'Entities, concepts, and nav files live in wiki/ but aren\u2019t rendered as standalone site pages.');
        }
        break;
      }
      case 'neighbours':
        highlightNeighbours(node.id);
        break;
      case 'copy-slug':
        await copyToClipboard(String(node.id));
        break;
      case 'copy-path':
        await copyToClipboard(String(node.path || node.id));
        break;
      case 'view-references': {
        const slug = String(node.id).replace(/"/g, '\\"');
        await copyToClipboard('llmwiki references "' + slug + '"');
        alert('Copied CLI command to clipboard:\n\n  llmwiki references "' + slug + '"');
        break;
      }
      default:
        /* mark-stale / archive: disabled placeholder — requires edit mode */
        break;
    }
  });

  // Keyboard shortcuts while menu is visible.
  if (ctxMenu) ctxMenu.addEventListener('keydown', e => {
    if (!ctxNode) return;
    const map = { 'n': 'neighbours', 'c': 'copy-slug', 'Enter': 'open' };
    const action = map[e.key];
    if (action) {
      const btn = ctxMenu.querySelector('button[data-action="' + action + '"]');
      if (btn && !btn.disabled) { e.preventDefault(); btn.click(); }
    }
  });

  // ─── Live search filter ──────────────────────────────────────────────
  const searchInput = document.getElementById('search-input');
  let baseColors = {};
  nodes.forEach(n => { baseColors[n.id] = n.color; });

  function applyFilter(q) {
    q = (q || '').trim().toLowerCase();
    const update = [];
    nodes.forEach(n => {
      const label = (n.label || '').toString().toLowerCase();
      const dim = q && !label.includes(q) && !String(n.id).toLowerCase().includes(q);
      update.push({
        id: n.id,
        color: dim ? { background: 'rgba(100,100,100,0.15)', border: 'rgba(100,100,100,0.3)' }
                   : baseColors[n.id],
      });
    });
    nodes.update(update);
  }
  if (searchInput) searchInput.addEventListener('input', e => applyFilter(e.target.value));

  // ─── Cluster toggle ──────────────────────────────────────────────────
  let clusterMode = 'off';
  const clusterBtn = document.getElementById('cluster-toggle');
  if (clusterBtn) clusterBtn.addEventListener('click', () => {
    clusterMode = clusterMode === 'off' ? 'type' : 'off';
    document.getElementById('cluster-mode').textContent = clusterMode;
    if (clusterMode === 'type') {
      const types = [...new Set(GRAPH.nodes.map(n => n.type))];
      types.forEach(t => {
        try {
          network.cluster({
            joinCondition: n => n.group === t,
            clusterNodeProperties: {
              id: 'cluster:' + t,
              label: t + ' (' + GRAPH.nodes.filter(x => x.type === t).length + ')',
              color: { background: (colors[t] || colors.root)() },
            },
          });
        } catch (_) { /* empty type */ }
      });
    } else {
      GRAPH.nodes.forEach(n => {
        const id = 'cluster:' + n.type;
        if (network.isCluster(id)) network.openCluster(id);
      });
    }
  });
}

function escapeHtml(s) {
  return String(s).replace(/[&<>"']/g, c =>
    ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
}
</script>
</body>
</html>
"""


def write_html(graph: dict[str, Any], out_path: Path) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    # json.dumps with ensure_ascii=False keeps unicode labels readable in
    # source view. Embedding the JSON directly in a ``<script>`` block is
    # safe because ``json.dumps`` escapes ``</`` sequences; we also double-
    # check that there's no ``</script>`` in the rendered text below.
    payload = json.dumps(graph, ensure_ascii=False)
    if "</script>" in payload:
        # Extremely defensive — a wiki page title containing literal
        # `</script>` would otherwise close our block early. Escape it.
        payload = payload.replace("</script>", "<\\/script>")
    # #456: inject the site's standard nav so graph.html isn't a navigation
    # dead end. Imported lazily to avoid a top-level circular dependency
    # (build.py imports graph.copy_to_site).
    from llmwiki.build import nav_bar
    site_nav_html = nav_bar(active="graph", link_prefix="")
    html = (
        HTML_TEMPLATE
        .replace("__GRAPH_JSON__", payload)
        .replace("__SITE_NAV__", site_nav_html)
    )
    out_path.write_text(html, encoding="utf-8")


def copy_to_site(site_dir: Path, *, graph: Optional[dict[str, Any]] = None) -> Optional[Path]:
    """Emit ``site/graph.html`` so the interactive viewer is reachable
    from the static site (v1.1.0 · #118).

    If ``graph`` is omitted we rebuild it from the wiki on the fly so
    callers can wire this into ``build_site()`` without having to run
    ``llmwiki graph`` first.

    Returns the path written, or ``None`` when the wiki has no pages.
    """
    # #328: verify site_urls against the actual compiled site so dead
    # links get nulled to the graceful "no page" tooltip.
    g = graph or build_graph(verify_site_dir=site_dir)
    if not g.get("nodes"):
        return None
    out = site_dir / "graph.html"
    write_html(g, out)
    return out


def build_and_report(write_json_flag: bool = True, write_html_flag: bool = True) -> int:
    graph = build_graph()
    if not graph["nodes"]:
        print(f"warning: no wiki pages found under {WIKI_DIR}", file=sys.stderr)
        return 1

    if write_json_flag:
        json_path = GRAPH_DIR / "graph.json"
        write_json(graph, json_path)
        print(f"  wrote {json_path.relative_to(REPO_ROOT)}")

    if write_html_flag:
        html_path = GRAPH_DIR / "graph.html"
        write_html(graph, html_path)
        print(f"  wrote {html_path.relative_to(REPO_ROOT)}")

    stats = graph["stats"]
    print()
    print(f"  {stats['total_pages']} pages · {stats['total_edges']} edges · "
          f"{stats['broken_edges']} broken · {len(stats['orphans'])} orphans")

    if stats["top_linked"]:
        print()
        print("  Top linked-to:")
        for n in stats["top_linked"]:
            if n["in_degree"] > 0:
                print(f"    {n['in_degree']:3} ← {n['id']}")

    if stats["top_linking"]:
        print()
        print("  Top linking-from:")
        for n in stats["top_linking"]:
            if n["out_degree"] > 0:
                print(f"    {n['out_degree']:3} → {n['id']}")

    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true", help="Write graph.json only")
    parser.add_argument("--html", action="store_true", help="Write graph.html only")
    args = parser.parse_args(argv)
    # Default: write both
    if not args.json and not args.html:
        return build_and_report(True, True)
    return build_and_report(args.json, args.html)


if __name__ == "__main__":
    sys.exit(main())
