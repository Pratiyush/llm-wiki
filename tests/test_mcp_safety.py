"""MCP server safety + cap regressions (closes #413, #431).

These tests pin two properties that are easy to regress on:

1. ``wiki_search`` returns at most 200 hits **across all roots**, not
   per-root. The old loop had three nested terminators with `break`
   statements that only exited the inner two — `include_raw=True`
   could double the cap.
2. ``wiki_list_sources``'s ``project=`` filter is unsanitized
   substring match by design, but no test guards against the
   refactor where someone replaces it with `path.join(...)`. Add
   coverage so a path-traversal regression fails loudly.
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest

from llmwiki.mcp.server import (
    tool_wiki_search,
    tool_wiki_list_sources,
)


# ─── Helpers ─────────────────────────────────────────────────────────


def _result_text(result: dict) -> str:
    return result["content"][0]["text"]


def _result_json(result: dict):
    return json.loads(_result_text(result))


def _seed_wiki(root: Path, n_files: int, hits_per_file: int, term: str = "needle") -> None:
    wiki = root / "wiki"
    wiki.mkdir(exist_ok=True, parents=True)
    body = "\n".join([f"line {i} {term}" for i in range(hits_per_file)])
    for i in range(n_files):
        (wiki / f"page-{i:03d}.md").write_text(body + "\n", encoding="utf-8")


def _seed_raw_sessions(root: Path, n_files: int, hits_per_file: int, term: str = "needle") -> None:
    raw = root / "raw" / "sessions" / "demo-proj"
    raw.mkdir(exist_ok=True, parents=True)
    body = "\n".join([f"line {i} {term}" for i in range(hits_per_file)])
    for i in range(n_files):
        (raw / f"session-{i:03d}.md").write_text(body + "\n", encoding="utf-8")


# ─── #413: wiki_search hit cap ──────────────────────────────────────


def test_search_caps_at_200_hits(tmp_path: Path):
    """A single search must not return more than 200 hits regardless
    of corpus size (#413)."""
    _seed_wiki(tmp_path, n_files=20, hits_per_file=50)  # 1000 potential
    with patch("llmwiki.mcp.server.REPO_ROOT", tmp_path):
        result = tool_wiki_search({"term": "needle"})
    payload = _result_json(result)
    assert len(payload["matches"]) == 200, payload["matches"][:3]
    assert payload["truncated"] is True


def test_search_with_include_raw_still_caps_at_200(tmp_path: Path):
    """Regression for #413: include_raw=True used to push the cap to
    400 because the per-root break didn't truly terminate the outer
    loop."""
    _seed_wiki(tmp_path, n_files=20, hits_per_file=50)
    _seed_raw_sessions(tmp_path, n_files=20, hits_per_file=50)
    with patch("llmwiki.mcp.server.REPO_ROOT", tmp_path):
        result = tool_wiki_search({"term": "needle", "include_raw": True})
    payload = _result_json(result)
    assert len(payload["matches"]) == 200, (
        f"expected ≤200 hits, got {len(payload['matches'])}"
    )
    assert payload["truncated"] is True


def test_search_under_cap_returns_all(tmp_path: Path):
    """Under the cap, every match must come back (no early termination)."""
    _seed_wiki(tmp_path, n_files=3, hits_per_file=10)  # 30 hits total
    with patch("llmwiki.mcp.server.REPO_ROOT", tmp_path):
        result = tool_wiki_search({"term": "needle"})
    payload = _result_json(result)
    assert len(payload["matches"]) == 30
    assert payload["truncated"] is False


def test_search_term_case_insensitive(tmp_path: Path):
    """Case-insensitive match still works after the lowercase-once
    refactor (#413)."""
    _seed_wiki(tmp_path, n_files=2, hits_per_file=5, term="NeEdLe")
    with patch("llmwiki.mcp.server.REPO_ROOT", tmp_path):
        result = tool_wiki_search({"term": "needle"})
    payload = _result_json(result)
    assert len(payload["matches"]) == 10


def test_search_empty_term_errors(tmp_path: Path):
    with patch("llmwiki.mcp.server.REPO_ROOT", tmp_path):
        result = tool_wiki_search({"term": ""})
    text = _result_text(result)
    assert "term is required" in text


def test_search_whitespace_only_term_errors(tmp_path: Path):
    """Whitespace-only term must be rejected the same as empty."""
    with patch("llmwiki.mcp.server.REPO_ROOT", tmp_path):
        result = tool_wiki_search({"term": "   "})
    text = _result_text(result)
    assert "term is required" in text


def test_search_term_with_regex_metacharacters_treated_literally(tmp_path: Path):
    """`.` `*` `[` etc. must be substring-matched, not regex-matched."""
    wiki = tmp_path / "wiki"
    wiki.mkdir(parents=True)
    (wiki / "p.md").write_text(
        "line 1 normal text\nline 2 has [a literal] bracket\n",
        encoding="utf-8",
    )
    with patch("llmwiki.mcp.server.REPO_ROOT", tmp_path):
        result = tool_wiki_search({"term": "[a literal]"})
    payload = _result_json(result)
    assert len(payload["matches"]) == 1


def test_search_unicode_term(tmp_path: Path):
    """CJK / emoji terms must round-trip via the lowercase pipeline."""
    wiki = tmp_path / "wiki"
    wiki.mkdir(parents=True)
    (wiki / "p.md").write_text("café 🚀 中文\n", encoding="utf-8")
    with patch("llmwiki.mcp.server.REPO_ROOT", tmp_path):
        result = tool_wiki_search({"term": "🚀"})
    assert len(_result_json(result)["matches"]) == 1
    with patch("llmwiki.mcp.server.REPO_ROOT", tmp_path):
        result = tool_wiki_search({"term": "中文"})
    assert len(_result_json(result)["matches"]) == 1


def test_search_one_file_with_many_hits_caps(tmp_path: Path):
    """A single file with 1000 hits must cap at 200 (the inner break
    has to fire)."""
    wiki = tmp_path / "wiki"
    wiki.mkdir(parents=True)
    (wiki / "big.md").write_text("\n".join([f"needle {i}" for i in range(1000)]),
                                  encoding="utf-8")
    with patch("llmwiki.mcp.server.REPO_ROOT", tmp_path):
        result = tool_wiki_search({"term": "needle"})
    payload = _result_json(result)
    assert len(payload["matches"]) == 200
    assert payload["truncated"] is True


# ─── #431: wiki_list_sources project= filter safety ─────────────────


def _seed_sessions(root: Path, projects: list[tuple[str, list[str]]]) -> None:
    for proj, names in projects:
        d = root / "raw" / "sessions" / proj
        d.mkdir(parents=True, exist_ok=True)
        for name in names:
            (d / name).write_text("body\n", encoding="utf-8")


@pytest.mark.parametrize("filter_value", [
    "../",
    "../..",
    "../../etc",
    "..\\",  # Windows traversal
    "..\\..\\Windows",
    "/etc/passwd",
    "/etc",
    "..%2F..%2Fetc",  # URL-encoded
    "demo-blog-engine; rm -rf /",  # command injection (must not reach shell)
    "demo-blog-engine && cat /etc/passwd",
    "$(whoami)",
    "`id`",
])
def test_list_sources_project_filter_is_substring_only_no_traversal(
    tmp_path: Path, filter_value: str
):
    """Regression for #431: the ``project=`` filter is substring match
    over the parent dir name, not a path-join. Hostile values must
    therefore return zero matches (because no project dir contains
    those substrings) instead of escaping ``raw/sessions/``.
    """
    _seed_sessions(tmp_path, [
        ("demo-blog-engine", ["s1.md"]),
        ("demo-todo-api", ["s2.md"]),
    ])
    with patch("llmwiki.mcp.server.REPO_ROOT", tmp_path):
        result = tool_wiki_list_sources({"project": filter_value})
    payload = _result_json(result)
    assert payload == [], (
        f"hostile filter {filter_value!r} returned data: {payload}"
    )


def test_list_sources_legitimate_filter_still_works(tmp_path: Path):
    """Sanity: real project filter returns matching sessions only."""
    _seed_sessions(tmp_path, [
        ("demo-blog-engine", ["s1.md", "s2.md"]),
        ("demo-todo-api", ["s3.md"]),
    ])
    with patch("llmwiki.mcp.server.REPO_ROOT", tmp_path):
        result = tool_wiki_list_sources({"project": "demo-blog"})
    payload = _result_json(result)
    assert len(payload) == 2
    for item in payload:
        assert "demo-blog-engine" in item["path"]


def test_list_sources_empty_project_returns_all(tmp_path: Path):
    """No filter (or empty string) returns every session."""
    _seed_sessions(tmp_path, [
        ("demo-blog-engine", ["s1.md"]),
        ("demo-todo-api", ["s2.md"]),
    ])
    with patch("llmwiki.mcp.server.REPO_ROOT", tmp_path):
        result = tool_wiki_list_sources({})
    payload = _result_json(result)
    assert len(payload) == 2


def test_list_sources_unicode_project_filter(tmp_path: Path):
    """Unicode project names work; hostile unicode (e.g. RTL override)
    doesn't escape."""
    _seed_sessions(tmp_path, [
        ("café-proj", ["s1.md"]),
        ("normal-proj", ["s2.md"]),
    ])
    with patch("llmwiki.mcp.server.REPO_ROOT", tmp_path):
        result = tool_wiki_list_sources({"project": "café"})
    payload = _result_json(result)
    assert len(payload) == 1
    assert "café-proj" in payload[0]["path"]


def test_list_sources_filter_does_not_glob(tmp_path: Path):
    """Substring match is documented: `demo*` matches `demo*` literally,
    not as a glob. Regression guard so anyone refactoring to fnmatch
    has to update this test deliberately."""
    _seed_sessions(tmp_path, [
        ("demo-blog-engine", ["s1.md"]),
    ])
    with patch("llmwiki.mcp.server.REPO_ROOT", tmp_path):
        result = tool_wiki_list_sources({"project": "demo*"})
    payload = _result_json(result)
    assert payload == []
