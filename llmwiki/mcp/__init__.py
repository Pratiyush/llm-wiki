"""llmwiki MCP server.

Exposes llmwiki operations as Model Context Protocol (MCP) tools that any
MCP-capable client (Claude Desktop, Claude Code, Codex, Cline, Cursor, ChatGPT
desktop, etc.) can call directly.

Seven production tools:

    - wiki_query(question)       — keyword search + page content
    - wiki_search(term)          — raw grep over wiki/ (+ optional raw/)
    - wiki_list_sources(project) — list raw source files with metadata
    - wiki_read_page(path)       — read one page (path-traversal guarded)
    - wiki_lint()                — orphans + broken-wikilinks report
    - wiki_sync(dry_run)         — trigger the converter
    - wiki_export(format)        — return any AI-consumable export

Protocol: Model Context Protocol, stdio transport, JSON-RPC 2.0.
See the MCP spec at: https://modelcontextprotocol.io/

Run with:

    python3 -m llmwiki.mcp
"""

from __future__ import annotations

from llmwiki.mcp.server import main

__all__ = ["main"]
