"""Tests for automatic AI-suggested tags (#351).

Covers:

* ``_extract_suggested_tags`` — parses the `<!-- suggested-tags: ... -->`
  comment the LLM emits at the top of its response, returns clean body.
* ``_merge_tags`` — merges maintainer-curated + baseline + AI sources
  with de-dup + near-duplicate rejection.
* ``_build_source_page`` — integration: frontmatter has merged tags,
  body has no suggested-tags comment.
* Re-synthesize: preserves existing maintainer-curated tags.
* LLM unavailable / malformed output: baseline tags still emitted.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from llmwiki.synth.pipeline import (
    _AI_TAG_CAP,
    _build_source_page,
    _derive_baseline_tags,
    _extract_suggested_tags,
    _merge_tags,
)


# ─── _extract_suggested_tags ──────────────────────────────────────────


def test_extract_happy_path():
    body = (
        "<!-- suggested-tags: prompt-caching, anthropic-api, token-budget -->\n"
        "\n## Summary\n\nA paragraph.\n"
    )
    tags, clean = _extract_suggested_tags(body)
    assert tags == ["prompt-caching", "anthropic-api", "token-budget"]
    assert clean.lstrip().startswith("## Summary")
    assert "suggested-tags" not in clean


def test_extract_missing_block_returns_empty_and_unchanged():
    body = "## Summary\n\nNothing special.\n"
    tags, clean = _extract_suggested_tags(body)
    assert tags == []
    assert clean == body


def test_extract_malformed_comment_returns_empty():
    # No closing `-->`
    body = "<!-- suggested-tags: foo, bar\n## Summary\n"
    tags, clean = _extract_suggested_tags(body)
    assert tags == []
    assert clean == body


def test_extract_empty_tag_list():
    body = "<!-- suggested-tags:  -->\n\n## Summary\n"
    tags, clean = _extract_suggested_tags(body)
    assert tags == []
    assert clean.lstrip().startswith("## Summary")


def test_extract_normalises_case_and_spaces():
    body = "<!-- suggested-tags: Prompt Caching, ANTHROPIC-API, token budget -->\n\n## Summary\n"
    tags, _ = _extract_suggested_tags(body)
    # Lowercased, spaces → hyphens.
    assert tags == ["prompt-caching", "anthropic-api", "token-budget"]


def test_extract_dedupes_within_suggestion():
    body = "<!-- suggested-tags: rag, rag, RAG, retrieval -->\n\n## Summary\n"
    tags, _ = _extract_suggested_tags(body)
    assert tags == ["rag", "retrieval"]


def test_extract_drops_stopwords():
    body = (
        "<!-- suggested-tags: claude, claude-code, session, rag, prompt-caching -->\n"
        "\n## Summary\n"
    )
    tags, _ = _extract_suggested_tags(body)
    # claude, claude-code, session are stop-words (pipeline already emits them).
    assert "claude" not in tags
    assert "claude-code" not in tags
    assert "session" not in tags
    assert "rag" in tags
    assert "prompt-caching" in tags


def test_extract_caps_at_five():
    body = (
        "<!-- suggested-tags: a, b, c, d, e, f, g, h -->\n\n## Summary\n"
    )
    tags, _ = _extract_suggested_tags(body)
    assert len(tags) == _AI_TAG_CAP
    assert tags == ["a", "b", "c", "d", "e"]


def test_extract_tolerates_leading_whitespace():
    body = "   \n<!-- suggested-tags: foo -->\n\n## Summary\n"
    tags, clean = _extract_suggested_tags(body)
    assert tags == ["foo"]
    assert "suggested-tags" not in clean


# ─── _merge_tags ──────────────────────────────────────────────────────


def test_merge_keeps_baseline_when_no_suggestions():
    result = _merge_tags(baseline=["claude-code", "session-transcript"], suggested=[])
    assert result == ["claude-code", "session-transcript"]


def test_merge_appends_suggestions_after_baseline():
    result = _merge_tags(
        baseline=["claude-code", "session-transcript", "llm-wiki", "claude"],
        suggested=["prompt-caching", "rag"],
    )
    # Baseline comes first, suggestions appended.
    assert result[:4] == ["claude-code", "session-transcript", "llm-wiki", "claude"]
    assert "prompt-caching" in result
    assert "rag" in result


def test_merge_dedupes_case_insensitively():
    result = _merge_tags(
        baseline=["Claude-Code"],
        suggested=["claude-code", "rag"],
    )
    # Only one "claude-code" variant survives.
    claude_matches = [t for t in result if t.lower() == "claude-code"]
    assert len(claude_matches) == 1


def test_merge_rejects_near_duplicate_suggestion():
    # "prompt-cache" is a near-dup of baseline "prompt-caching".
    result = _merge_tags(
        baseline=["claude-code", "prompt-caching"],
        suggested=["prompt-cache", "rag"],
    )
    assert "prompt-caching" in result
    assert "prompt-cache" not in result  # rejected as near-dup
    assert "rag" in result  # kept, no near-dup


def test_merge_preserves_existing_maintainer_tags_first():
    result = _merge_tags(
        baseline=["claude-code", "llm-wiki"],
        suggested=["rag"],
        existing=["hand-curated-tag", "another-curated"],
    )
    # Maintainer tags come first.
    assert result[:2] == ["hand-curated-tag", "another-curated"]
    assert "claude-code" in result
    assert "rag" in result


def test_merge_empty_everything():
    assert _merge_tags(baseline=[], suggested=[]) == []


def test_merge_ignores_whitespace_only():
    result = _merge_tags(
        baseline=["claude-code"],
        suggested=["  ", "rag", ""],
    )
    assert result == ["claude-code", "rag"]


# ─── _build_source_page integration ──────────────────────────────────


def _synth_body(tags: str, rest: str = "## Summary\n\nA summary.\n") -> str:
    return f"<!-- suggested-tags: {tags} -->\n\n{rest}"


def test_build_source_page_merges_ai_tags_into_frontmatter():
    meta = {
        "slug": "test",
        "title": "Session: test — 2026-04-21",
        "project": "llm-wiki",
        "model": "claude-sonnet-4-6",
        "date": "2026-04-21",
        "source_file": "raw/sessions/x.md",
        "tags": ["claude-code", "session-transcript"],
    }
    body = _synth_body("prompt-caching, anthropic-api, token-budget")
    page = _build_source_page(meta, body)

    # Frontmatter line present + merged.
    assert "tags: [claude-code, session-transcript, llm-wiki, claude, prompt-caching, anthropic-api, token-budget]" in page
    # Suggested-tags comment stripped from body.
    assert "<!-- suggested-tags" not in page
    # Body content preserved.
    assert "## Summary" in page
    assert "A summary." in page


def test_build_source_page_without_suggested_tags_falls_back_to_baseline():
    meta = {
        "slug": "test",
        "title": "Session: test — 2026-04-21",
        "project": "llm-wiki",
        "model": "claude-sonnet-4-6",
        "date": "2026-04-21",
        "source_file": "raw/sessions/x.md",
        "tags": ["claude-code", "session-transcript"],
    }
    # LLM didn't emit the comment.
    body = "## Summary\n\nA summary.\n"
    page = _build_source_page(meta, body)

    baseline = _derive_baseline_tags(meta)
    # Frontmatter still has all baseline tags.
    for t in baseline:
        assert t in page
    # Body preserved verbatim.
    assert "## Summary" in page


def test_build_source_page_preserves_existing_tags_on_resynthesize(tmp_path):
    existing = tmp_path / "existing.md"
    existing.write_text(
        "---\n"
        "title: \"Session: test — 2026-04-21\"\n"
        "type: source\n"
        "tags: [hand-curated-tag, claude-code, session-transcript]\n"
        "date: 2026-04-21\n"
        "source_file: raw/sessions/x.md\n"
        "project: llm-wiki\n"
        "model: claude-sonnet-4-6\n"
        "last_updated: 2026-04-20\n"
        "---\n\n"
        "## Summary\n\nOld content.\n",
        encoding="utf-8",
    )

    meta = {
        "slug": "test",
        "title": "Session: test — 2026-04-21",
        "project": "llm-wiki",
        "model": "claude-sonnet-4-6",
        "date": "2026-04-21",
        "source_file": "raw/sessions/x.md",
        "tags": ["claude-code", "session-transcript"],
    }
    body = _synth_body("prompt-caching, rag")
    page = _build_source_page(meta, body, existing_page_path=existing)

    # Hand-curated tag is preserved AT THE FRONT of the list.
    assert page.count("hand-curated-tag") == 1
    # Index of hand-curated comes before any AI tag.
    hand_idx = page.find("hand-curated-tag")
    rag_idx = page.find("rag")
    assert hand_idx < rag_idx


def test_build_source_page_missing_existing_path_is_safe(tmp_path):
    # existing_page_path points at a file that doesn't exist yet.
    meta = {
        "slug": "test",
        "title": "Session: test — 2026-04-21",
        "project": "llm-wiki",
        "model": "claude-sonnet-4-6",
        "date": "2026-04-21",
        "source_file": "raw/sessions/x.md",
        "tags": ["claude-code"],
    }
    body = _synth_body("rag")
    page = _build_source_page(
        meta, body, existing_page_path=tmp_path / "does-not-exist.md"
    )
    assert "rag" in page
    assert "## Summary" in page


def test_build_source_page_handles_malformed_existing_frontmatter(tmp_path):
    existing = tmp_path / "broken.md"
    existing.write_text("no frontmatter here\n## Summary\n", encoding="utf-8")

    meta = {
        "slug": "test",
        "title": "Session: test — 2026-04-21",
        "project": "llm-wiki",
        "model": "claude-sonnet-4-6",
        "date": "2026-04-21",
        "source_file": "raw/sessions/x.md",
        "tags": ["claude-code"],
    }
    body = _synth_body("rag")
    # Must not raise — baseline tags should still be emitted.
    page = _build_source_page(meta, body, existing_page_path=existing)
    assert "rag" in page


def test_build_source_page_strips_comment_even_without_trailing_newline():
    meta = {
        "slug": "test",
        "title": "t",
        "project": "p",
        "model": "claude-sonnet-4-6",
        "date": "2026-04-21",
        "source_file": "raw/sessions/x.md",
        "tags": [],
    }
    body = "<!-- suggested-tags: rag -->## Summary\n\nBody.\n"
    page = _build_source_page(meta, body)
    assert "<!-- suggested-tags" not in page
    assert "## Summary" in page
