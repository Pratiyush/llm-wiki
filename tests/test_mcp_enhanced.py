"""Tests for the 5 enhanced MCP tools (v1.0, #159)."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest


from llmwiki.mcp.server import (
    TOOLS,
    TOOL_IMPLS,
    tool_wiki_confidence,
    tool_wiki_lifecycle,
    tool_wiki_dashboard,
    tool_wiki_entity_search,
    tool_wiki_category_browse,
)


# ─── Registration ─────────────────────────────────────────────────────


def test_all_12_tools_registered():
    assert len(TOOLS) == 12
    names = {t["name"] for t in TOOLS}
    for required in ["wiki_query", "wiki_search", "wiki_list_sources",
                      "wiki_read_page", "wiki_lint", "wiki_sync", "wiki_export",
                      "wiki_confidence", "wiki_lifecycle", "wiki_dashboard",
                      "wiki_entity_search", "wiki_category_browse"]:
        assert required in names


def test_all_tools_have_impl():
    for tool in TOOLS:
        assert tool["name"] in TOOL_IMPLS


# ─── wiki_confidence ─────────────────────────────────────────────────


def test_confidence_filter_by_min(tmp_path: Path):
    wiki = tmp_path / "wiki"
    wiki.mkdir()
    (wiki / "a.md").write_text(
        '---\ntitle: "A"\ntype: entity\nconfidence: 0.9\n---\n', encoding="utf-8"
    )
    (wiki / "b.md").write_text(
        '---\ntitle: "B"\ntype: entity\nconfidence: 0.3\n---\n', encoding="utf-8"
    )
    with patch("llmwiki.mcp.server.REPO_ROOT", tmp_path):
        result = tool_wiki_confidence({"min_confidence": 0.8})
    text = result["content"][0]["text"]
    assert "a.md" in text
    assert "b.md" not in text


def test_confidence_filter_by_max(tmp_path: Path):
    wiki = tmp_path / "wiki"
    wiki.mkdir()
    (wiki / "low.md").write_text(
        '---\ntitle: "L"\ntype: entity\nconfidence: 0.3\n---\n', encoding="utf-8"
    )
    with patch("llmwiki.mcp.server.REPO_ROOT", tmp_path):
        result = tool_wiki_confidence({"max_confidence": 0.5})
    assert "low.md" in result["content"][0]["text"]


def test_confidence_skips_pages_without_field(tmp_path: Path):
    wiki = tmp_path / "wiki"
    wiki.mkdir()
    (wiki / "a.md").write_text(
        '---\ntitle: "A"\ntype: entity\n---\n', encoding="utf-8"
    )
    with patch("llmwiki.mcp.server.REPO_ROOT", tmp_path):
        result = tool_wiki_confidence({})
    assert "0 pages" in result["content"][0]["text"]


def test_confidence_handles_invalid_value(tmp_path: Path):
    wiki = tmp_path / "wiki"
    wiki.mkdir()
    (wiki / "a.md").write_text(
        '---\ntitle: "A"\ntype: entity\nconfidence: high\n---\n', encoding="utf-8"
    )
    with patch("llmwiki.mcp.server.REPO_ROOT", tmp_path):
        result = tool_wiki_confidence({})
    assert "0 pages" in result["content"][0]["text"]


# ─── wiki_lifecycle ──────────────────────────────────────────────────


def test_lifecycle_requires_state():
    result = tool_wiki_lifecycle({})
    assert result.get("isError") is True


def test_lifecycle_filters_by_state(tmp_path: Path):
    wiki = tmp_path / "wiki"
    wiki.mkdir()
    (wiki / "a.md").write_text(
        '---\ntitle: "A"\nlifecycle: draft\n---\n', encoding="utf-8"
    )
    (wiki / "b.md").write_text(
        '---\ntitle: "B"\nlifecycle: verified\n---\n', encoding="utf-8"
    )
    with patch("llmwiki.mcp.server.REPO_ROOT", tmp_path):
        result = tool_wiki_lifecycle({"state": "draft"})
    text = result["content"][0]["text"]
    assert "a.md" in text
    assert "b.md" not in text


def test_lifecycle_empty_state(tmp_path: Path):
    wiki = tmp_path / "wiki"
    wiki.mkdir()
    with patch("llmwiki.mcp.server.REPO_ROOT", tmp_path):
        result = tool_wiki_lifecycle({"state": "verified"})
    assert "0 pages" in result["content"][0]["text"]


# ─── wiki_dashboard ──────────────────────────────────────────────────


def test_dashboard_counts_by_type(tmp_path: Path):
    wiki = tmp_path / "wiki"
    wiki.mkdir()
    (wiki / "a.md").write_text(
        '---\ntitle: "A"\ntype: entity\n---\n', encoding="utf-8"
    )
    (wiki / "b.md").write_text(
        '---\ntitle: "B"\ntype: concept\n---\n', encoding="utf-8"
    )
    with patch("llmwiki.mcp.server.REPO_ROOT", tmp_path):
        result = tool_wiki_dashboard({})
    text = result["content"][0]["text"]
    assert "entity" in text
    assert "concept" in text


def test_dashboard_confidence_buckets(tmp_path: Path):
    wiki = tmp_path / "wiki"
    wiki.mkdir()
    (wiki / "high.md").write_text(
        '---\ntitle: "H"\ntype: entity\nconfidence: 0.95\n---\n', encoding="utf-8"
    )
    (wiki / "low.md").write_text(
        '---\ntitle: "L"\ntype: entity\nconfidence: 0.2\n---\n', encoding="utf-8"
    )
    (wiki / "none.md").write_text(
        '---\ntitle: "N"\ntype: entity\n---\n', encoding="utf-8"
    )
    with patch("llmwiki.mcp.server.REPO_ROOT", tmp_path):
        result = tool_wiki_dashboard({})
    text = result["content"][0]["text"]
    assert "high" in text
    assert "low" in text


def test_dashboard_handles_empty_wiki(tmp_path: Path):
    wiki = tmp_path / "wiki"
    wiki.mkdir()
    with patch("llmwiki.mcp.server.REPO_ROOT", tmp_path):
        result = tool_wiki_dashboard({})
    text = result["content"][0]["text"]
    assert "0 pages" in text


# ─── wiki_entity_search ──────────────────────────────────────────────


def test_entity_search_by_type(tmp_path: Path):
    wiki = tmp_path / "wiki"
    (wiki / "entities").mkdir(parents=True)
    (wiki / "entities" / "Tool1.md").write_text(
        '---\ntitle: "Tool1"\ntype: entity\nentity_type: tool\n---\n', encoding="utf-8"
    )
    (wiki / "entities" / "Person1.md").write_text(
        '---\ntitle: "Person1"\ntype: entity\nentity_type: person\n---\n', encoding="utf-8"
    )
    with patch("llmwiki.mcp.server.REPO_ROOT", tmp_path):
        result = tool_wiki_entity_search({"entity_type": "tool"})
    text = result["content"][0]["text"]
    assert "Tool1" in text
    assert "Person1" not in text


def test_entity_search_by_name(tmp_path: Path):
    wiki = tmp_path / "wiki"
    (wiki / "entities").mkdir(parents=True)
    (wiki / "entities" / "Claude.md").write_text(
        '---\ntitle: "Claude"\ntype: entity\n---\n', encoding="utf-8"
    )
    (wiki / "entities" / "GPT.md").write_text(
        '---\ntitle: "GPT"\ntype: entity\n---\n', encoding="utf-8"
    )
    with patch("llmwiki.mcp.server.REPO_ROOT", tmp_path):
        result = tool_wiki_entity_search({"name": "claude"})
    text = result["content"][0]["text"]
    assert "Claude" in text
    assert "GPT" not in text


def test_entity_search_skips_non_entities(tmp_path: Path):
    wiki = tmp_path / "wiki"
    wiki.mkdir()
    (wiki / "concept.md").write_text(
        '---\ntitle: "Concept"\ntype: concept\n---\n', encoding="utf-8"
    )
    with patch("llmwiki.mcp.server.REPO_ROOT", tmp_path):
        result = tool_wiki_entity_search({})
    assert "0 matching" in result["content"][0]["text"]


# ─── wiki_category_browse ────────────────────────────────────────────


def test_category_browse_lists_all(tmp_path: Path):
    wiki = tmp_path / "wiki"
    wiki.mkdir()
    (wiki / "a.md").write_text(
        '---\ntitle: "A"\ntags: [flutter, mobile]\n---\n', encoding="utf-8"
    )
    (wiki / "b.md").write_text(
        '---\ntitle: "B"\ntags: [flutter]\n---\n', encoding="utf-8"
    )
    with patch("llmwiki.mcp.server.REPO_ROOT", tmp_path):
        result = tool_wiki_category_browse({})
    text = result["content"][0]["text"]
    assert "flutter" in text
    assert "mobile" in text


def test_category_browse_specific_tag(tmp_path: Path):
    wiki = tmp_path / "wiki"
    wiki.mkdir()
    (wiki / "a.md").write_text(
        '---\ntitle: "A"\ntags: [flutter]\n---\n', encoding="utf-8"
    )
    (wiki / "b.md").write_text(
        '---\ntitle: "B"\ntags: [python]\n---\n', encoding="utf-8"
    )
    with patch("llmwiki.mcp.server.REPO_ROOT", tmp_path):
        result = tool_wiki_category_browse({"tag": "flutter"})
    text = result["content"][0]["text"]
    assert "a.md" in text
    assert "b.md" not in text


def test_category_browse_min_count(tmp_path: Path):
    wiki = tmp_path / "wiki"
    wiki.mkdir()
    (wiki / "a.md").write_text(
        '---\ntitle: "A"\ntags: [popular]\n---\n', encoding="utf-8"
    )
    (wiki / "b.md").write_text(
        '---\ntitle: "B"\ntags: [popular]\n---\n', encoding="utf-8"
    )
    (wiki / "c.md").write_text(
        '---\ntitle: "C"\ntags: [lonely]\n---\n', encoding="utf-8"
    )
    with patch("llmwiki.mcp.server.REPO_ROOT", tmp_path):
        result = tool_wiki_category_browse({"min_count": 2})
    text = result["content"][0]["text"]
    assert "popular" in text
    assert "lonely" not in text
