"""Tests for `llmwiki.context_md` — folder-level `_context.md` files (v0.5 · #60)."""

from __future__ import annotations

from pathlib import Path

import pytest

from llmwiki.context_md import (
    CONTEXT_FILENAME,
    collect_folder_contexts,
    find_uncontexted_folders,
    folder_context_summary,
    is_context_file,
    load_folder_context,
)


# ─── is_context_file ─────────────────────────────────────────────────────


def test_is_context_file_matches_exact_name():
    assert is_context_file(Path("/tmp/wiki/entities/_context.md")) is True
    assert is_context_file(Path("_context.md")) is True


def test_is_context_file_rejects_similar_names():
    assert is_context_file(Path("context.md")) is False
    assert is_context_file(Path("my_context.md")) is False
    assert is_context_file(Path("_context_old.md")) is False
    assert is_context_file(Path("_context")) is False


# ─── load_folder_context ────────────────────────────────────────────────


def test_load_folder_context_returns_none_for_missing(tmp_path):
    assert load_folder_context(tmp_path) is None


def test_load_folder_context_parses_frontmatter(tmp_path):
    (tmp_path / "_context.md").write_text(
        "---\ntype: folder-context\ntitle: Entities\n---\n\n"
        "People and companies tracked by the wiki.\n",
        encoding="utf-8",
    )
    result = load_folder_context(tmp_path)
    assert result is not None
    meta, body = result
    assert meta == {"type": "folder-context", "title": "Entities"}
    assert "People and companies" in body


def test_load_folder_context_no_frontmatter_returns_empty_meta(tmp_path):
    (tmp_path / "_context.md").write_text(
        "# Some heading\n\nA body with no frontmatter.\n", encoding="utf-8"
    )
    meta, body = load_folder_context(tmp_path)
    assert meta == {}
    assert "A body" in body


def test_load_folder_context_quoted_values(tmp_path):
    (tmp_path / "_context.md").write_text(
        '---\ntitle: "Research notes"\nscope: \'global\'\n---\n\nBody.\n',
        encoding="utf-8",
    )
    meta, _ = load_folder_context(tmp_path)
    assert meta["title"] == "Research notes"
    assert meta["scope"] == "global"


# ─── folder_context_summary ─────────────────────────────────────────────


def test_folder_context_summary_first_paragraph():
    body = (
        "# Entities\n\n"
        "People, companies, projects, and libraries the wiki tracks.\n"
        "Pages here use `type: entity` frontmatter.\n\n"
        "## See also\n\n"
        "`wiki/concepts/_context.md` for ideas vs entities.\n"
    )
    summary = folder_context_summary(body)
    assert summary.startswith("People, companies, projects, and libraries")
    # Joins lines in the same paragraph
    assert "type: entity" in summary
    # Doesn't leak into the next paragraph
    assert "See also" not in summary


def test_folder_context_summary_skips_headings():
    body = "# Heading\n\n## Another heading\n\nActual content here.\n"
    assert folder_context_summary(body) == "Actual content here."


def test_folder_context_summary_truncates_long_bodies():
    long_para = "word " * 100  # 500 chars
    summary = folder_context_summary(long_para, max_chars=60)
    assert len(summary) <= 60
    assert summary.endswith("…")


def test_folder_context_summary_empty_body_returns_empty():
    assert folder_context_summary("") == ""
    assert folder_context_summary("# Just a heading\n") == ""


# ─── find_uncontexted_folders (lint) ────────────────────────────────────


def test_find_uncontexted_folders_under_threshold_is_silent(tmp_path):
    # 5 files is below the default threshold of 10 — no warning
    for i in range(5):
        (tmp_path / f"page-{i}.md").write_text("x", encoding="utf-8")
    results = list(find_uncontexted_folders(tmp_path, threshold=10))
    assert results == []


def test_find_uncontexted_folders_over_threshold_reports(tmp_path):
    for i in range(12):
        (tmp_path / f"page-{i}.md").write_text("x", encoding="utf-8")
    results = list(find_uncontexted_folders(tmp_path, threshold=10))
    assert len(results) == 1
    folder, count = results[0]
    assert folder == tmp_path
    assert count == 12


def test_find_uncontexted_folders_skips_folders_with_context(tmp_path):
    for i in range(12):
        (tmp_path / f"page-{i}.md").write_text("x", encoding="utf-8")
    (tmp_path / "_context.md").write_text("# Context\n", encoding="utf-8")
    results = list(find_uncontexted_folders(tmp_path, threshold=10))
    assert results == []


def test_find_uncontexted_folders_does_not_count_context_file(tmp_path):
    # 10 pages + 1 _context.md should NOT trip a threshold-of-10 rule,
    # because _context.md isn't a page.
    for i in range(10):
        (tmp_path / f"page-{i}.md").write_text("x", encoding="utf-8")
    (tmp_path / "_context.md").write_text("# Context\n", encoding="utf-8")
    results = list(find_uncontexted_folders(tmp_path, threshold=10))
    assert results == []


def test_find_uncontexted_folders_recurses(tmp_path):
    big = tmp_path / "entities"
    big.mkdir()
    for i in range(15):
        (big / f"entity-{i}.md").write_text("x", encoding="utf-8")
    # Parent has few files; only `entities/` should fire
    (tmp_path / "readme.md").write_text("x", encoding="utf-8")
    results = list(find_uncontexted_folders(tmp_path, threshold=10))
    assert len(results) == 1
    assert results[0][0] == big


def test_find_uncontexted_folders_skips_hidden_dirs(tmp_path):
    hidden = tmp_path / ".claude"
    hidden.mkdir()
    for i in range(20):
        (hidden / f"file-{i}.md").write_text("x", encoding="utf-8")
    results = list(find_uncontexted_folders(tmp_path, threshold=10))
    assert results == []


# ─── collect_folder_contexts ────────────────────────────────────────────


def test_collect_folder_contexts_walks_tree(tmp_path):
    (tmp_path / "_context.md").write_text(
        "---\ntitle: Root\n---\n\nRoot of the wiki.\n", encoding="utf-8"
    )
    entities = tmp_path / "entities"
    entities.mkdir()
    (entities / "_context.md").write_text(
        "---\ntitle: Entities\n---\n\nPeople and companies.\n", encoding="utf-8"
    )
    concepts = tmp_path / "concepts"
    concepts.mkdir()
    # concepts/ deliberately has NO _context.md
    (concepts / "topic.md").write_text("# Topic\n", encoding="utf-8")
    out = collect_folder_contexts(tmp_path)
    assert set(out.keys()) == {tmp_path, entities}
    assert out[tmp_path][0]["title"] == "Root"
    assert out[entities][0]["title"] == "Entities"


def test_collect_folder_contexts_empty_root_returns_empty(tmp_path):
    assert collect_folder_contexts(tmp_path) == {}


def test_collect_folder_contexts_missing_root_returns_empty(tmp_path):
    assert collect_folder_contexts(tmp_path / "nope") == {}
