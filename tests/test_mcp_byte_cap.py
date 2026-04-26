"""Tests for #483 — MCP wiki_search / wiki_query must cap input bytes
to prevent OOM on huge files / huge corpora.

The bug: both tools called p.read_text() on every .md with no
size guard. `_SEARCH_HIT_CAP=200` capped output, not input. A
vault user with a 100MB Obsidian transcript thrashed the server
on every call.

The fix: `_read_capped(p, remaining_budget)` enforces a 4 MiB
per-file cap and a 50 MiB aggregate budget per call. Oversize
files are skipped entirely (no partial-read).
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest

from llmwiki.mcp.server import (
    _MCP_SCAN_AGGREGATE_BYTES,
    _MCP_SCAN_PER_FILE_BYTES,
    _read_capped,
    tool_wiki_search,
)


def test_read_capped_returns_text_under_cap(tmp_path: Path):
    p = tmp_path / "small.md"
    p.write_text("hello world\n", encoding="utf-8")
    text, consumed = _read_capped(p, remaining_budget=100_000)
    assert text == "hello world\n"
    assert consumed == len("hello world\n")


def test_read_capped_skips_oversize_file_entirely(tmp_path: Path):
    """Oversize files must be skipped (consumed=0) NOT partial-read."""
    p = tmp_path / "huge.md"
    big_content = "x" * (_MCP_SCAN_PER_FILE_BYTES + 1)
    p.write_text(big_content, encoding="utf-8")
    text, consumed = _read_capped(p, remaining_budget=_MCP_SCAN_AGGREGATE_BYTES)
    assert text == ""
    assert consumed == 0


def test_read_capped_respects_remaining_budget(tmp_path: Path):
    """File bigger than remaining budget but smaller than per-file
    cap → skip (cap is min of the two)."""
    p = tmp_path / "medium.md"
    p.write_text("y" * 1000, encoding="utf-8")
    text, consumed = _read_capped(p, remaining_budget=500)
    assert text == ""
    assert consumed == 0


def test_read_capped_zero_budget_skips(tmp_path: Path):
    p = tmp_path / "any.md"
    p.write_text("anything", encoding="utf-8")
    text, consumed = _read_capped(p, remaining_budget=0)
    assert text == ""
    assert consumed == 0


def test_read_capped_unreadable_file_returns_zero(tmp_path: Path):
    """Missing file returns ('', 0) gracefully — no exception."""
    p = tmp_path / "missing.md"
    text, consumed = _read_capped(p, remaining_budget=100_000)
    assert text == ""
    assert consumed == 0


def test_search_response_includes_skipped_oversize_counter(tmp_path: Path):
    """Surface the skipped count so callers know we didn't silently
    miss content."""
    wiki = tmp_path / "wiki"
    raw = tmp_path / "raw"
    wiki.mkdir()
    raw.mkdir()
    (wiki / "small.md").write_text("findme appears here\n", encoding="utf-8")
    (wiki / "huge.md").write_text("x" * (_MCP_SCAN_PER_FILE_BYTES + 100),
                                   encoding="utf-8")
    with patch("llmwiki.mcp.server.REPO_ROOT", tmp_path):
        res = tool_wiki_search({"term": "findme"})
    body = res.get("content", [{}])[0].get("text", "")
    payload = json.loads(body)
    assert payload["term"] == "findme"
    assert payload["skipped_oversize_files"] >= 1, (
        f"expected ≥1 oversize file skipped, got {payload}"
    )
    assert any("findme" in m.get("text", "") for m in payload["matches"])


def test_search_normal_corpus_no_skips(tmp_path: Path):
    """Sanity: small-corpus calls should not report any skips."""
    wiki = tmp_path / "wiki"
    raw = tmp_path / "raw"
    wiki.mkdir()
    raw.mkdir()
    (wiki / "a.md").write_text("apple\n", encoding="utf-8")
    (wiki / "b.md").write_text("banana\n", encoding="utf-8")
    with patch("llmwiki.mcp.server.REPO_ROOT", tmp_path):
        res = tool_wiki_search({"term": "apple"})
    body = res.get("content", [{}])[0].get("text", "")
    payload = json.loads(body)
    assert payload["skipped_oversize_files"] == 0
    assert payload["truncated"] is False


def test_per_file_cap_constants_documented():
    """The cap values are part of the contract — make a future
    refactor that changes them notice this test."""
    assert _MCP_SCAN_PER_FILE_BYTES == 4 * 1024 * 1024
    assert _MCP_SCAN_AGGREGATE_BYTES == 50 * 1024 * 1024
