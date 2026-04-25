"""Tests for llmwiki.graphify_bridge — Graphify integration."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from llmwiki.graphify_bridge import is_available, GRAPHIFY_OUT

_GRAPHIFY_INSTALLED = importlib.util.find_spec("graphify") is not None


# ─── availability check ─────────────────────────────────────────────


def test_is_available_returns_bool():
    result = is_available()
    assert isinstance(result, bool)


@pytest.mark.skipif(
    not _GRAPHIFY_INSTALLED,
    reason="graphify is an optional dependency; install with `pip install llmwiki[graph]`",
)
def test_is_available_true_when_graphify_installed():
    """When graphify is installed in the dev environment, is_available() is True."""
    assert is_available() is True


def test_is_available_false_when_not_installed():
    with patch.dict("sys.modules", {"graphify": None}):
        # Force ImportError by removing the module
        import importlib
        from llmwiki import graphify_bridge
        importlib.reload(graphify_bridge)
        # The function does a fresh import each time so we need to mock it
        with patch("builtins.__import__", side_effect=ImportError("no graphify")):
            assert graphify_bridge.is_available() is False
        importlib.reload(graphify_bridge)


# ─── bridge module imports ───────────────────────────────────────────


def test_bridge_module_imports():
    from llmwiki.graphify_bridge import (
        is_available,
        build_graphify_graph,
        export_to_obsidian,
        query_graph,
    )
    assert callable(build_graphify_graph)
    assert callable(export_to_obsidian)
    assert callable(query_graph)


# ─── CLI integration ─────────────────────────────────────────────────


def test_cli_graph_has_engine_flag():
    from llmwiki.cli import build_parser

    parser = build_parser()
    # Parse a graph --help to check the engine flag exists
    args = parser.parse_args(["graph", "--engine", "graphify"])
    assert args.engine == "graphify"


def test_cli_graph_engine_default_is_graphify():
    from llmwiki.cli import build_parser

    parser = build_parser()
    args = parser.parse_args(["graph"])
    assert args.engine == "graphify"


def test_cli_graph_engine_graphify_accepted():
    from llmwiki.cli import build_parser

    parser = build_parser()
    args = parser.parse_args(["graph", "--engine", "graphify"])
    assert args.engine == "graphify"


# ─── pyproject.toml declares graph extra ──────────────────────────────


def test_pyproject_has_graph_extra():
    from llmwiki import REPO_ROOT

    toml_path = REPO_ROOT / "pyproject.toml"
    content = toml_path.read_text(encoding="utf-8")
    assert 'graph = ["graphifyy' in content


# ─── graphify-out in .gitignore ──────────────────────────────────────


def test_gitignore_excludes_graphify_out():
    from llmwiki import REPO_ROOT

    gitignore = (REPO_ROOT / ".gitignore").read_text(encoding="utf-8")
    assert "graphify-out/" in gitignore


# ─── query_graph returns string ──────────────────────────────────────


def test_query_graph_no_graph_file(tmp_path):
    """When no graph.json exists, return a helpful message."""
    from llmwiki.graphify_bridge import query_graph
    with patch("llmwiki.graphify_bridge.GRAPHIFY_OUT", tmp_path):
        result = query_graph("test question")
    assert "No graph found" in result


# ─── project-based edge enrichment ──────────────────────────────────


def test_extract_wiki_nodes_project_edges(tmp_path):
    """Pages sharing a project: field get connected via project hub + proximity edges."""
    from llmwiki.graphify_bridge import _extract_wiki_nodes

    # Create three wiki pages in the same project
    for i, (slug, date) in enumerate([
        ("alpha", "2026-04-01"),
        ("beta", "2026-04-02"),
        ("gamma", "2026-04-03"),
    ]):
        (tmp_path / f"{slug}.md").write_text(
            f"---\ntitle: \"{slug}\"\ntype: source\nproject: test-proj\ndate: {date}\n---\n\n# {slug}\n",
            encoding="utf-8",
        )

    result = _extract_wiki_nodes(tmp_path)
    nodes = result["nodes"]
    edges = result["edges"]

    # Expect a project hub node
    hub_nodes = [n for n in nodes if n["type"] == "project"]
    assert len(hub_nodes) == 1
    assert hub_nodes[0]["id"] == "project__test-proj"
    assert hub_nodes[0]["label"] == "Project: test-proj"

    # Expect 3 membership edges (one per page)
    membership = [e for e in edges if e["type"] == "project_membership"]
    assert len(membership) == 3

    # Expect proximity edges: alpha->beta, alpha->gamma, beta->gamma = 3
    proximity = [e for e in edges if e["type"] == "project_proximity"]
    assert len(proximity) == 3


def test_extract_wiki_nodes_no_project_no_extra_edges(tmp_path):
    """Pages without project: field produce no project edges."""
    from llmwiki.graphify_bridge import _extract_wiki_nodes

    (tmp_path / "solo.md").write_text(
        "---\ntitle: \"solo\"\ntype: entity\n---\n\n# Solo page\n",
        encoding="utf-8",
    )

    result = _extract_wiki_nodes(tmp_path)
    edges = result["edges"]

    project_edges = [e for e in edges if e["type"] in ("project_membership", "project_proximity")]
    assert len(project_edges) == 0


def test_extract_wiki_nodes_project_proximity_capped_at_5(tmp_path):
    """Proximity edges connect at most 5 neighbours (not N^2)."""
    from llmwiki.graphify_bridge import _extract_wiki_nodes

    # Create 10 pages in the same project
    for i in range(10):
        (tmp_path / f"page{i:02d}.md").write_text(
            f"---\ntitle: \"page{i}\"\ntype: source\nproject: big\ndate: 2026-04-{i+1:02d}\n---\n\n",
            encoding="utf-8",
        )

    result = _extract_wiki_nodes(tmp_path)
    proximity = [e for e in result["edges"] if e["type"] == "project_proximity"]

    # With 10 pages and max 5 forward neighbours each, the number should be
    # 5+5+5+5+5+4+3+2+1+0 = 35 (not 10*9/2 = 45)
    assert len(proximity) == 35
