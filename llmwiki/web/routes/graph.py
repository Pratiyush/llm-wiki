"""Knowledge graph API."""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, HTTPException, Query

from llmwiki import REPO_ROOT
from llmwiki.graph import build_and_report, build_graph, scan_pages
from llmwiki.notebooks import DEFAULT_NOTEBOOK_SLUG, is_valid_slug, notebook_wiki_dir

router = APIRouter()


@router.get("/data")
async def get_graph_data(notebook: str | None = Query(None)):
    """Return knowledge graph as nodes and edges for vis.js."""
    wiki_dir, _ = _notebook_dirs_or_404(notebook)
    pages = scan_pages(wiki_dir=wiki_dir)
    graph = build_graph(wiki_dir=wiki_dir)
    nodes = []
    edges = []
    graph_nodes = {node["id"]: node for node in graph["nodes"]}

    # Color map for page types
    colors = {
        "source": "#3b82f6",
        "entities": "#10b981",
        "concepts": "#f59e0b",
        "syntheses": "#8b5cf6",
        "root": "#6b7280",
        "projects": "#ec4899",
    }

    for slug, node in graph_nodes.items():
        info = pages.get(slug, {})
        nodes.append({
            "id": slug,
            "label": node.get("label", info.get("title", slug)),
            "type": node.get("type", info.get("type", "root")),
            "color": colors.get(node.get("type", info.get("type", "root")), "#6b7280"),
        })

    for edge in graph["edges"]:
        edges.append({"from": edge["source"], "to": edge["target"]})

    return {"nodes": nodes, "edges": edges}


@router.post("/rebuild")
async def rebuild_graph(notebook: str | None = Query(None)):
    """Rebuild the knowledge graph on disk."""
    wiki_dir, graph_dir = _notebook_dirs_or_404(notebook)
    try:
        status = build_and_report(wiki_dir=wiki_dir, graph_dir=graph_dir)
        if status != 0:
            raise RuntimeError("no wiki pages found")
        return {"status": "ok"}
    except Exception as e:
        return {"status": "error", "message": str(e)}


def _notebook_dirs_or_404(notebook: str | None) -> tuple[Path, Path]:
    if notebook is None:
        slug = DEFAULT_NOTEBOOK_SLUG
    elif is_valid_slug(notebook):
        slug = notebook
    else:
        raise HTTPException(status_code=404, detail="notebook wiki not found")

    wiki_dir = notebook_wiki_dir(slug, repo_root=REPO_ROOT)
    if not wiki_dir.is_dir():
        raise HTTPException(status_code=404, detail="notebook wiki not found")
    return wiki_dir, wiki_dir.parent / "graph"
