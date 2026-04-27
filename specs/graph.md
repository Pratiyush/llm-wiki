# graph spec

## Goal

Interactive force-directed knowledge graph of every wiki page and its `[[wikilinks]]`. Click a node to focus, drag to pan, scroll to zoom.

## URL pattern

- `/graph.html`

## Must

- Page `<title>` contains "Graph" (e.g. "llmwiki — Knowledge Graph").
- The site nav bar (Home/Projects/Sessions/Graph/Docs/Changelog) is present and the "Graph" link carries `class="active"` (closes #456 — graph used to be standalone with no nav chrome).
- A `<div id="network">` containing the rendered graph canvas.
- vis-network loads from a CDN-pinned URL with SHA-384 SRI integrity attribute.
- Clicking a node triggers focus (color/size change, edges highlighted).
- Theme toggle works on `/graph.html` exactly as on every other page.

## Should

- Graph initial layout settles in under 3 seconds on a 500-node corpus.
- Empty wikis render a placeholder ("No links yet — write some `[[wikilinks]]`") rather than a blank canvas.
- The graph respects the same `prefers-color-scheme` settings as the rest of the site (dark theme = dark canvas).

## Won't

- Won't lazy-load the graph data — `graph.json` is fetched eagerly because the page has no other purpose.

## Cross-references

- #456 (closed) — site nav restored on `/graph.html`
- v1.3.67 (#679) — SHA-384 SRI for vis-network@9.1.9
- `llmwiki/graph.py:copy_to_site`
