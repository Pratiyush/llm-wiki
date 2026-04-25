"""Graphify integration bridge for llmwiki.

Delegates graph building, community detection, and analysis to the
``graphify`` package (https://github.com/safishamsi/graphify) when
installed.  Falls back gracefully when not available.

Install:  pip install graphify          # or: pip install llm-notebook[graph]
Extras:   pip install graphify[mcp]     # MCP server
          pip install graphify[leiden]   # better community detection

Usage from CLI:
    python3 -m llmwiki graph                  # graphify is default
    python3 -m llmwiki graph --engine builtin # stdlib fallback

Usage from Python:
    from llmwiki.graphify_bridge import is_available, build_graphify_graph
    if is_available():
        result = build_graphify_graph()
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

from llmwiki import REPO_ROOT

WIKI_DIR = REPO_ROOT / "wiki"
GRAPH_DIR = REPO_ROOT / "graph"
GRAPHIFY_OUT = REPO_ROOT / "graphify-out"


def is_available() -> bool:
    """Return True when graphify is importable."""
    try:
        import graphify  # noqa: F401
        return True
    except ImportError:
        return False


def _community_labels(G, communities: dict[int, list[str]]) -> dict[int, str]:
    """Generate human-readable labels for each community.

    Uses the most-connected node in each community as the label.
    """
    labels: dict[int, str] = {}
    for cid, members in communities.items():
        if not members:
            labels[cid] = f"Community {cid}"
            continue
        # Pick the member with highest degree as representative
        best = max(members, key=lambda n: G.degree(n) if n in G else 0)
        labels[cid] = str(best)
    return labels


def _extract_wiki_nodes(wiki_dir: Path) -> dict[str, Any]:
    """Build graph nodes + edges from wiki markdown frontmatter + wikilinks.

    Graphify's AST extractor works on code files but not markdown.
    We parse wiki pages ourselves: each page becomes a node, each
    ``[[wikilink]]`` becomes an edge.

    Additionally, pages sharing the same ``project:`` frontmatter field
    are connected via project hub nodes and date-proximity edges to
    reduce graph orphans.
    """
    import re
    WIKILINK_RE = re.compile(r"\[\[([^\]|#]+?)(?:#[^\]]*)?(?:\|[^\]]+)?\]\]")

    nodes: list[dict] = []
    edges: list[dict] = []
    seen_ids: set[str] = set()

    # Track pages per project for post-loop edge enrichment
    # project_slug -> list of (node_id, date_str)
    project_pages: dict[str, list[tuple[str, str]]] = {}

    for md in sorted(wiki_dir.rglob("*.md")):
        text = md.read_text(encoding="utf-8", errors="replace")
        rel = md.relative_to(wiki_dir)
        raw_id = str(rel.with_suffix("")).replace("/", "_").replace(" ", "_")
        # Cap node ID at 120 chars to avoid filesystem issues on export
        node_id = raw_id[:120] if len(raw_id) > 120 else raw_id

        # Parse frontmatter
        title = md.stem
        page_type = "page"
        tags: list[str] = []
        project: str = ""
        date_str: str = ""
        if text.startswith("---"):
            end = text.find("---", 3)
            if end > 0:
                fm = text[3:end]
                for line in fm.splitlines():
                    if line.startswith("title:"):
                        title = line.split(":", 1)[1].strip().strip('"\'')
                    elif line.startswith("type:"):
                        page_type = line.split(":", 1)[1].strip().strip('"\'')
                    elif line.startswith("tags:"):
                        raw = line.split(":", 1)[1].strip()
                        tags = [t.strip().strip('"\'') for t in raw.strip("[]").split(",") if t.strip()]
                    elif line.startswith("project:"):
                        project = line.split(":", 1)[1].strip().strip('"\'')
                    elif line.startswith("date:"):
                        date_str = line.split(":", 1)[1].strip().strip('"\'')

        # Determine subfolder category
        parts = rel.parts
        category = parts[0] if len(parts) > 1 else "root"

        # Truncate label to 80 chars — Obsidian export uses labels as filenames
        label = title[:80] if len(title) > 80 else title

        nodes.append({
            "id": node_id,
            "label": label,
            "type": page_type,
            "file": str(rel),
            "file_type": "document",
            "source_file": str(rel),
            "category": category,
            "tags": tags,
        })
        seen_ids.add(node_id)

        # Extract wikilink edges
        for target in WIKILINK_RE.findall(text):
            target = target.strip()
            if len(target) > 120:
                continue  # Skip malformed / absurdly long wikilinks
            target_id = target.replace(" ", "_").replace("/", "_")
            edges.append({
                "source": node_id,
                "target": target_id,
                "type": "wikilink",
                "relation": "links_to",
                "confidence": "EXTRACTED",
                "source_file": str(rel),
            })

        # Collect project membership for enrichment
        if project:
            project_pages.setdefault(project, []).append((node_id, date_str))

    # ------------------------------------------------------------------
    # Project-based edge enrichment (reduces single-node communities)
    # ------------------------------------------------------------------
    project_edge_count = 0
    for proj_slug, members in project_pages.items():
        if not proj_slug:
            continue
        # Create a project hub node
        hub_id = f"project__{proj_slug}"
        if hub_id not in seen_ids:
            nodes.append({
                "id": hub_id,
                "label": f"Project: {proj_slug}",
                "type": "project",
                "file": "",
                "file_type": "document",
                "source_file": "",
                "category": "project",
                "tags": [],
            })
            seen_ids.add(hub_id)

        # Edge from each page to the project hub
        for nid, _ in members:
            edges.append({
                "source": nid,
                "target": hub_id,
                "type": "project_membership",
                "relation": "belongs_to",
                "confidence": "INFERRED",
                "source_file": "",
            })
            project_edge_count += 1

        # Date-proximity edges: connect each page to up to 5 nearest
        # siblings by date to avoid N^2 explosion on large projects
        sorted_members = sorted(members, key=lambda m: m[1])
        for i, (nid, _) in enumerate(sorted_members):
            # Connect to the next 5 pages (chronological neighbours)
            for j in range(i + 1, min(i + 6, len(sorted_members))):
                neighbor_id = sorted_members[j][0]
                edges.append({
                    "source": nid,
                    "target": neighbor_id,
                    "type": "project_proximity",
                    "relation": "same_project_near_date",
                    "confidence": "INFERRED",
                    "source_file": "",
                })
                project_edge_count += 1

    if project_edge_count:
        print(f"  wiki-nodes: {project_edge_count} project-based edges added "
              f"({len(project_pages)} projects)")

    # Create implicit nodes for wikilink targets that don't have their own page
    edge_targets = {e["target"] for e in edges}
    for tid in edge_targets - seen_ids:
        nodes.append({
            "id": tid,
            "label": tid.replace("_", " "),
            "type": "reference",
            "file": "",
            "file_type": "document",
            "source_file": "",
            "category": "unresolved",
        })

    return {"nodes": nodes, "edges": edges}


def build_graphify_graph(
    *,
    directed: bool = False,
    include_code: bool = False,
) -> dict[str, Any]:
    """Run the Graphify pipeline on the wiki.

    Parameters
    ----------
    directed : bool
        Use directed graph (preserves edge direction).
    include_code : bool
        Also extract llmwiki/ source code into the graph.

    Returns
    -------
    dict with keys: graph (NetworkX), communities, gods, report_path,
    json_path, html_path, stats.
    """
    from graphify.detect import detect
    from graphify.extract import extract
    from graphify.build import build_from_json
    from graphify.cluster import cluster, score_all
    from graphify.analyze import god_nodes, surprising_connections, suggest_questions
    from graphify.report import generate as generate_report
    from graphify.export import to_json, to_html

    # Step 1: Extract wiki pages into nodes + edges
    print("  graphify: extracting wiki pages (frontmatter + wikilinks)...")
    extraction = _extract_wiki_nodes(WIKI_DIR)

    # Build a detection_result compatible with Graphify's report generator
    wiki_files = list(WIKI_DIR.rglob("*.md"))
    detection_result: dict = {
        "files": {"document": [str(f) for f in wiki_files], "code": []},
        "total_files": len(wiki_files),
        "total_words": sum(f.stat().st_size // 5 for f in wiki_files if f.is_file()),
    }
    if include_code:
        src_dir = REPO_ROOT / "llmwiki"
        if src_dir.is_dir():
            result = detect(src_dir)
            detection_result = result
            code_files = [Path(f) for f in result.get("files", {}).get("code", [])]
            if code_files:
                print(f"  graphify: extracting {len(code_files)} code files (AST)...")
                code_ext = extract(code_files, cache_root=GRAPHIFY_OUT)
                extraction["nodes"].extend(code_ext.get("nodes", []))
                extraction["edges"].extend(code_ext.get("edges", []))

    if not extraction["nodes"]:
        print("  warning: no nodes found in wiki/", file=sys.stderr)
        return {"graph": None, "stats": {"total_nodes": 0, "total_edges": 0}}

    print(f"  graphify: {len(extraction['nodes'])} nodes, {len(extraction['edges'])} edges")

    # Step 2: Build NetworkX graph
    G = build_from_json(extraction, directed=directed)

    # Step 4: Community detection
    communities = cluster(G)
    cohesion = score_all(G, communities)
    labels = _community_labels(G, communities)
    print(f"  graphify: {len(communities)} communities detected")

    # Step 5: Analysis
    gods = god_nodes(G, top_n=10)
    surprises = surprising_connections(G, communities)
    questions = suggest_questions(G, communities, labels)

    # Step 6: Generate report
    report_md = generate_report(
        G, communities, cohesion,
        community_labels=labels,
        god_node_list=gods,
        surprise_list=surprises,
        detection_result=detection_result,
        token_cost={"input_tokens": 0, "output_tokens": 0, "cost_usd": 0.0},
        root=str(REPO_ROOT),
        suggested_questions=questions,
    )

    # Step 6b: Hyperedges — group relationships connecting 3+ nodes
    from graphify.export import attach_hyperedges as _attach
    # Find shared wikilink targets (nodes linked by 3+ pages)
    target_sources: dict[str, list[str]] = {}
    for e in extraction["edges"]:
        t = e["target"]
        target_sources.setdefault(t, []).append(e["source"])
    hyperedges = []
    for target, sources_list in target_sources.items():
        if len(sources_list) >= 3:
            hyperedges.append({
                "nodes": sources_list[:10] + [target],
                "type": "shared_reference",
                "label": f"all link to {target}",
            })
    if hyperedges:
        _attach(G, hyperedges)
        print(f"  graphify: {len(hyperedges)} hyperedges attached")

    # Step 7: Export (all formats)
    GRAPHIFY_OUT.mkdir(parents=True, exist_ok=True)
    GRAPH_DIR.mkdir(parents=True, exist_ok=True)

    json_path = GRAPHIFY_OUT / "graph.json"
    html_path = GRAPHIFY_OUT / "graph.html"
    svg_path = GRAPHIFY_OUT / "graph.svg"
    graphml_path = GRAPHIFY_OUT / "graph.graphml"
    report_path = GRAPHIFY_OUT / "GRAPH_REPORT.md"

    to_json(G, communities, str(json_path))
    to_html(G, communities, str(html_path), community_labels=labels)
    report_path.write_text(report_md, encoding="utf-8")

    # SVG export
    from graphify.export import to_svg, to_graphml
    to_svg(G, communities, str(svg_path), community_labels=labels)

    # GraphML — flatten list attributes to strings first (GraphML only supports scalars)
    try:
        import networkx as nx
        H = nx.Graph(G) if not G.is_directed() else nx.DiGraph(G)
        for _, ndata in H.nodes(data=True):
            for k in list(ndata.keys()):
                v = ndata[k]
                if isinstance(v, (list, tuple)):
                    ndata[k] = ", ".join(str(x) for x in v)
                elif not isinstance(v, (str, int, float, bool)):
                    ndata[k] = str(v)
        for _, _, edata in H.edges(data=True):
            for k in list(edata.keys()):
                v = edata[k]
                if not isinstance(v, (str, int, float, bool)):
                    edata[k] = str(v)
        to_graphml(H, communities, str(graphml_path))
    except Exception as e:
        print(f"  graphify: GraphML export skipped ({e})", file=sys.stderr)

    # Copy to graph/ for build pipeline compatibility
    graph_json = GRAPH_DIR / "graph.json"
    graph_html = GRAPH_DIR / "graph.html"
    graph_json.write_text(json_path.read_text(encoding="utf-8"), encoding="utf-8")
    graph_html.write_text(html_path.read_text(encoding="utf-8"), encoding="utf-8")

    stats = {
        "total_nodes": G.number_of_nodes(),
        "total_edges": G.number_of_edges(),
        "communities": len(communities),
        "god_nodes": [g.get("label", str(g)) if isinstance(g, dict) else str(g) for g in gods[:5]],
    }

    print(f"  graphify: wrote {json_path.relative_to(REPO_ROOT)}")
    print(f"  graphify: wrote {html_path.relative_to(REPO_ROOT)}")
    print(f"  graphify: wrote {svg_path.relative_to(REPO_ROOT)}")
    print(f"  graphify: wrote {graphml_path.relative_to(REPO_ROOT)}")
    print(f"  graphify: wrote {report_path.relative_to(REPO_ROOT)}")
    print(f"  graphify: {stats['total_nodes']} nodes, {stats['total_edges']} edges, "
          f"{stats['communities']} communities")

    if gods:
        print("  graphify: top nodes (most connected):")
        for g in gods[:5]:
            label = g.get("label", str(g)) if isinstance(g, dict) else str(g)
            print(f"    - {label}")

    return {
        "graph": G,
        "communities": communities,
        "community_labels": labels,
        "cohesion": cohesion,
        "gods": gods,
        "surprises": surprises,
        "questions": questions,
        "report_path": report_path,
        "json_path": json_path,
        "html_path": html_path,
        "stats": stats,
    }


def export_to_obsidian(vault_path: Path) -> Path:
    """Export the Graphify graph to an Obsidian vault."""
    from graphify.export import to_obsidian, to_canvas

    json_path = GRAPHIFY_OUT / "graph.json"
    if not json_path.is_file():
        raise FileNotFoundError(
            f"No graph found at {json_path}. Run `llmwiki graph` first."
        )

    import networkx as nx
    from networkx.readwrite import json_graph
    data = json.loads(json_path.read_text(encoding="utf-8"))
    G = json_graph.node_link_graph(data)

    communities: dict[int, list[str]] = {}
    for nid, ndata in G.nodes(data=True):
        cid = ndata.get("community", 0)
        communities.setdefault(cid, []).append(nid)

    to_obsidian(G, communities, str(vault_path))
    to_canvas(G, communities, str(vault_path / "graph.canvas"))

    print(f"  graphify: obsidian export written to {vault_path}")
    return vault_path


def query_graph(question: str, *, depth: int = 3, token_budget: int = 2000) -> str:
    """Query the knowledge graph with a natural language question.

    Scores nodes by keyword match (case-insensitive) + connectivity.
    Prioritizes well-connected nodes over orphans. BFS from top seeds
    to find the relevant subgraph.
    """
    json_path = GRAPHIFY_OUT / "graph.json"
    if not json_path.is_file():
        return "No graph found. Run `llmwiki graph` first."

    import networkx as nx
    from networkx.readwrite import json_graph

    data = json.loads(json_path.read_text(encoding="utf-8"))
    G = json_graph.node_link_graph(data)

    keywords = question.lower().split()
    # Score nodes by keyword match + connectivity bonus
    scored: list[tuple[float, str]] = []
    for nid, ndata in G.nodes(data=True):
        label = str(ndata.get("label", nid)).lower()
        nid_lower = str(nid).lower()
        # Match against both label and node ID
        text = f"{label} {nid_lower}"
        keyword_score = sum(1 for kw in keywords if kw in text)
        if keyword_score > 0:
            # Boost well-connected nodes (log scale to avoid domination)
            degree = G.degree(nid)
            connectivity_bonus = min(degree / 10.0, 2.0)
            # Prefer entity/concept pages over raw sources
            type_bonus = 0.5 if ndata.get("type") in ("entity", "concept") else 0
            total = keyword_score + connectivity_bonus + type_bonus
            scored.append((total, nid))
    scored.sort(reverse=True)

    if not scored:
        return "No matching nodes found in the knowledge graph."

    # BFS from top seeds
    seeds = [nid for _, nid in scored[:5]]
    visited = set()
    frontier = list(seeds)
    result_nodes = []
    for _ in range(depth):
        next_frontier = []
        for node in frontier:
            if node in visited:
                continue
            visited.add(node)
            result_nodes.append(node)
            next_frontier.extend(G.neighbors(node))
        frontier = next_frontier

    # Sort by degree (most connected first) and build text
    result_nodes.sort(key=lambda n: G.degree(n), reverse=True)
    lines = []
    for nid in result_nodes[:20]:
        ndata = G.nodes[nid]
        label = ndata.get("label", nid)
        ntype = ndata.get("type", "")
        degree = G.degree(nid)
        community = ndata.get("community", "?")
        file_ = ndata.get("file", "")
        line = f"- **{label}** ({ntype}, {degree} connections)"
        if file_:
            line += f" — `{file_}`"
        lines.append(line)

    text = "\n".join(lines)
    return text[:token_budget] if len(text) > token_budget else text
