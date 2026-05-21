"""Knowledge graph API."""

from __future__ import annotations

import json
from pathlib import Path

from fastapi import APIRouter

from llmwiki import REPO_ROOT
from llmwiki.graph import scan_pages, build_graph

router = APIRouter()


@router.get("/data")
async def get_graph_data():
    """Return knowledge graph as nodes and edges for vis.js."""
    pages = scan_pages()
    nodes = []
    edges = []
    seen_targets = set()

    # Color map for page types
    colors = {
        "source": "#3b82f6",
        "entities": "#10b981",
        "concepts": "#f59e0b",
        "syntheses": "#8b5cf6",
        "root": "#6b7280",
        "projects": "#ec4899",
    }

    for slug, info in pages.items():
        nodes.append({
            "id": slug,
            "label": info.get("title", slug),
            "type": info.get("type", "root"),
            "color": colors.get(info.get("type", "root"), "#6b7280"),
        })
        seen_targets.add(slug)

    for slug, info in pages.items():
        for target in info.get("out_links", []):
            if target in seen_targets:
                edges.append({"from": slug, "to": target})

    return {"nodes": nodes, "edges": edges}


@router.post("/rebuild")
async def rebuild_graph():
    """Rebuild the knowledge graph on disk."""
    try:
        build_graph(json_only=False)
        return {"status": "ok"}
    except Exception as e:
        return {"status": "error", "message": str(e)}
