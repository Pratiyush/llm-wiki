"""Tests for v0.2 additions — graph, obsidian_output, mcp, watch, new adapters."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from llmwiki.adapters import REGISTRY, discover_adapters
from llmwiki.adapters.base import BaseAdapter
from llmwiki.adapters.cursor import CursorAdapter
from llmwiki.adapters.gemini_cli import GeminiCliAdapter
from llmwiki.adapters.pdf import PdfAdapter

from tests.conftest import REPO_ROOT


# ─── adapter registry v0.2 ────────────────────────────────────────────────


def test_v02_registry_has_new_adapters():
    discover_adapters()
    for name in ("cursor", "gemini_cli", "pdf"):
        assert name in REGISTRY, f"missing adapter: {name}"


def test_new_adapters_subclass_base():
    assert issubclass(CursorAdapter, BaseAdapter)
    assert issubclass(GeminiCliAdapter, BaseAdapter)
    assert issubclass(PdfAdapter, BaseAdapter)


def test_new_adapters_have_schema_versions():
    assert CursorAdapter.SUPPORTED_SCHEMA_VERSIONS
    assert GeminiCliAdapter.SUPPORTED_SCHEMA_VERSIONS
    assert PdfAdapter.SUPPORTED_SCHEMA_VERSIONS


def test_pdf_adapter_requires_explicit_config():
    # PDF adapter is_available() returns True when pypdf is installed.
    # The real gate is the `enabled` flag in config — discover_sessions()
    # returns [] when enabled is False (the default). This test verifies
    # the practical behavior: no configured roots → no sessions.
    adapter = PdfAdapter()
    assert adapter.discover_sessions() == []


def test_cursor_adapter_slug_fallback():
    a = CursorAdapter()
    p = Path("/tmp/nonexistent/some-workspace-hash/state.vscdb")
    slug = a.derive_project_slug(p)
    assert slug  # any non-empty string


def test_gemini_adapter_slug_fallback():
    a = GeminiCliAdapter()
    p = Path("/tmp/nonexistent/demo/session-123.json")
    slug = a.derive_project_slug(p)
    assert "gemini" in slug


# ─── graph builder ────────────────────────────────────────────────────────


def test_graph_build_function_exists():
    from llmwiki.graph import build_graph, scan_pages

    # scan_pages should be callable even if wiki is empty
    pages = scan_pages()
    assert isinstance(pages, dict)

    graph = build_graph()
    assert "nodes" in graph
    assert "edges" in graph
    assert "stats" in graph
    assert "total_pages" in graph["stats"]


def test_graph_nodes_have_expected_keys():
    from llmwiki.graph import build_graph

    g = build_graph()
    if not g["nodes"]:
        pytest.skip("no wiki pages to graph")
    node = g["nodes"][0]
    for key in ("id", "label", "type", "path", "in_degree", "out_degree"):
        assert key in node, f"node missing {key}: {node}"


# ─── obsidian_output ──────────────────────────────────────────────────────


def test_obsidian_output_imports():
    from llmwiki.obsidian_output import export_to_vault, _add_source_backlink, _build_readme
    assert callable(export_to_vault)
    assert callable(_add_source_backlink)
    assert callable(_build_readme)


def test_obsidian_output_adds_backlink():
    from llmwiki.obsidian_output import _add_source_backlink

    source = REPO_ROOT / "wiki" / "index.md"
    content = "# Hello\n\nSome content.\n"
    out = _add_source_backlink(content, source)
    assert "## llmwiki Source" in out
    assert "Hello" in out
    # Idempotent: calling again doesn't duplicate the backlink
    out2 = _add_source_backlink(out, source)
    assert out2.count("## llmwiki Source") == 1


def test_obsidian_output_refuses_missing_vault(tmp_path):
    from llmwiki.obsidian_output import export_to_vault

    missing = tmp_path / "does-not-exist"
    rc = export_to_vault(vault=missing, dry_run=True)
    assert rc != 0


# ─── MCP server ───────────────────────────────────────────────────────────


def test_mcp_tools_list():
    from llmwiki.mcp.server import TOOLS

    names = {t["name"] for t in TOOLS}
    expected = {"wiki_query", "wiki_search", "wiki_list_sources", "wiki_read_page", "wiki_lint", "wiki_sync"}
    assert expected.issubset(names), f"missing: {expected - names}"


def test_mcp_initialize_handler():
    from llmwiki.mcp.server import handle_initialize, PROTOCOL_VERSION

    result = handle_initialize({})
    assert result["protocolVersion"] == PROTOCOL_VERSION
    assert "serverInfo" in result
    assert "capabilities" in result


def test_mcp_tools_list_handler():
    from llmwiki.mcp.server import handle_tools_list

    result = handle_tools_list({})
    assert "tools" in result
    assert len(result["tools"]) >= 6


def test_mcp_tool_call_unknown_tool():
    from llmwiki.mcp.server import handle_tools_call

    result = handle_tools_call({"name": "does_not_exist", "arguments": {}})
    assert result.get("isError") is True


def test_mcp_tool_wiki_list_sources():
    from llmwiki.mcp.server import tool_wiki_list_sources

    result = tool_wiki_list_sources({})
    assert result["isError"] is False
    text = result["content"][0]["text"]
    data = json.loads(text)
    assert isinstance(data, list)


def test_mcp_tool_wiki_lint():
    from llmwiki.mcp.server import tool_wiki_lint

    result = tool_wiki_lint({})
    if result["isError"]:
        pytest.skip("wiki/ not present")
    data = json.loads(result["content"][0]["text"])
    for key in ("total_pages", "orphans", "orphan_count", "broken_links", "broken_link_count"):
        assert key in data


def test_mcp_tool_wiki_read_page_path_traversal_guard():
    from llmwiki.mcp.server import tool_wiki_read_page

    result = tool_wiki_read_page({"path": "../../../etc/passwd"})
    assert result["isError"] is True


# ─── watch module ─────────────────────────────────────────────────────────


def test_watch_module_imports():
    from llmwiki.watch import watch, scan_mtimes, run_sync
    assert callable(watch)
    assert callable(scan_mtimes)
    assert callable(run_sync)


def test_watch_scan_mtimes_returns_dict():
    from llmwiki.watch import scan_mtimes

    mtimes = scan_mtimes(adapters=None)
    assert isinstance(mtimes, dict)
    # Every value should be a float (mtime)
    for path, mtime in mtimes.items():
        assert isinstance(path, str)
        assert isinstance(mtime, float)


# ─── CLI subcommands ──────────────────────────────────────────────────────


def test_cli_has_v02_subcommands():
    from llmwiki.cli import build_parser

    parser = build_parser()
    help_text = parser.format_help()
    for cmd in ("graph", "watch", "export-obsidian"):
        assert cmd in help_text, f"missing CLI subcommand: {cmd}"
