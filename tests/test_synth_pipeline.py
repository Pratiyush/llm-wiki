"""Tests for the auto-ingest synthesis pipeline (v0.5 · #36)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from llmwiki.synth.base import BaseSynthesizer, DummySynthesizer
from llmwiki.synth.pipeline import (
    _build_source_page,
    _discover_raw_sessions,
    _load_prompt_template,
    synthesize_new_sessions,
)


# ─── fixtures ────────────────────────────────────────────────────────────


DEMO_SESSION = """---
title: "Session: test-synth — 2026-04-09"
type: source
tags: [claude-code, session-transcript]
date: 2026-04-09
source_file: raw/sessions/test-proj/2026-04-09-test-synth.md
slug: test-synth
project: test-proj
model: claude-sonnet-4-6
user_messages: 3
tool_calls: 5
---

# Session: test-synth — 2026-04-09

## Summary

Built a test fixture for the synthesis pipeline.

## Conversation

### Turn 1 — User

Write a test.

### Turn 1 — Assistant

Done. Used [[pytest]] and [[FastAPI]].
"""


def _seed_raw(tmp_path: Path) -> Path:
    raw = tmp_path / "raw" / "sessions" / "test-proj"
    raw.mkdir(parents=True)
    (raw / "2026-04-09-test-synth.md").write_text(DEMO_SESSION, encoding="utf-8")
    return tmp_path / "raw" / "sessions"


# ─── DummySynthesizer ────────────────────────────────────────────────────


def test_dummy_synthesizer_is_always_available():
    assert DummySynthesizer().is_available() is True


def test_dummy_synthesizer_produces_valid_markdown():
    backend = DummySynthesizer()
    meta = {"slug": "test", "project": "demo", "date": "2026-04-09",
            "model": "claude-sonnet-4-6", "user_messages": 3, "tool_calls": 5}
    body = "# Test session\n\nSome content with [[pytest]] and [[FastAPI]].\n"
    result = backend.synthesize_source_page(body, meta, "template")
    assert "## Summary" in result
    assert "## Key Claims" in result
    assert "## Connections" in result
    assert "[[pytest]]" in result
    assert "[[FastAPI]]" in result


def test_dummy_synthesizer_handles_empty_body():
    backend = DummySynthesizer()
    result = backend.synthesize_source_page("", {"slug": "empty"}, "template")
    assert "## Summary" in result
    assert "(no connections detected)" in result


# ─── prompt template loading ─────────────────────────────────────────────


def test_load_prompt_template_returns_string():
    template = _load_prompt_template()
    assert isinstance(template, str)
    assert "{body}" in template
    assert "{meta}" in template
    assert "## Summary" in template


# ─── _discover_raw_sessions ─────────────────────────────────────────────


def test_discover_raw_sessions_finds_md_files(tmp_path: Path):
    raw = _seed_raw(tmp_path)
    sessions = _discover_raw_sessions(raw)
    assert len(sessions) == 1
    path, meta, body = sessions[0]
    assert meta["slug"] == "test-synth"
    assert meta["project"] == "test-proj"


def test_discover_raw_sessions_skips_underscore_files(tmp_path: Path):
    raw = _seed_raw(tmp_path)
    (raw / "test-proj" / "_context.md").write_text("# context\n", encoding="utf-8")
    sessions = _discover_raw_sessions(raw)
    assert len(sessions) == 1  # only the real session, not _context.md


def test_discover_raw_sessions_empty_dir(tmp_path: Path):
    empty = tmp_path / "empty"
    empty.mkdir()
    assert _discover_raw_sessions(empty) == []


def test_discover_raw_sessions_missing_dir(tmp_path: Path):
    assert _discover_raw_sessions(tmp_path / "nonexistent") == []


# ─── _build_source_page ─────────────────────────────────────────────────


def test_build_source_page_has_frontmatter():
    meta = {"slug": "test", "title": "Session: test", "project": "demo",
            "date": "2026-04-09", "model": "claude-sonnet-4-6",
            "tags": ["claude-code"], "source_file": "raw/sessions/demo/test.md"}
    page = _build_source_page(meta, "## Summary\n\nTest body.\n")
    assert page.startswith("---\n")
    assert "type: source" in page
    assert "project: demo" in page
    assert "## Summary" in page


# ─── synthesize_new_sessions (full pipeline) ────────────────────────────


def test_synthesize_fresh_run_produces_source_pages(tmp_path: Path):
    raw = _seed_raw(tmp_path)
    wiki_sources = tmp_path / "wiki" / "sources"
    wiki_sources.mkdir(parents=True)
    # Create log.md so _append_log doesn't fail
    (tmp_path / "wiki" / "log.md").write_text("# Log\n", encoding="utf-8")

    summary = synthesize_new_sessions(
        backend=DummySynthesizer(),
        raw_dir=raw,
        wiki_sources_dir=wiki_sources,
    )
    assert summary["total_scanned"] == 1
    assert summary["new_files"] == 1
    assert summary["synthesized"] == 1
    assert summary["errors"] == []
    # Check the output file
    out_file = wiki_sources / "test-proj" / "test-synth.md"
    assert out_file.exists()
    content = out_file.read_text(encoding="utf-8")
    assert "type: source" in content
    assert "## Summary" in content


def test_synthesize_idempotent_rerun_is_noop(tmp_path: Path):
    raw = _seed_raw(tmp_path)
    wiki_sources = tmp_path / "wiki" / "sources"
    wiki_sources.mkdir(parents=True)
    (tmp_path / "wiki" / "log.md").write_text("# Log\n", encoding="utf-8")

    # First run
    s1 = synthesize_new_sessions(
        backend=DummySynthesizer(), raw_dir=raw, wiki_sources_dir=wiki_sources,
    )
    assert s1["synthesized"] == 1

    # Second run — should be a no-op (mtime hasn't changed)
    s2 = synthesize_new_sessions(
        backend=DummySynthesizer(), raw_dir=raw, wiki_sources_dir=wiki_sources,
    )
    assert s2["new_files"] == 0
    assert s2["synthesized"] == 0


def test_synthesize_force_resynthesizes(tmp_path: Path):
    raw = _seed_raw(tmp_path)
    wiki_sources = tmp_path / "wiki" / "sources"
    wiki_sources.mkdir(parents=True)
    (tmp_path / "wiki" / "log.md").write_text("# Log\n", encoding="utf-8")

    # First run
    synthesize_new_sessions(
        backend=DummySynthesizer(), raw_dir=raw, wiki_sources_dir=wiki_sources,
    )
    # Force re-run
    s2 = synthesize_new_sessions(
        backend=DummySynthesizer(), raw_dir=raw, wiki_sources_dir=wiki_sources,
        force=True,
    )
    assert s2["new_files"] == 1
    assert s2["synthesized"] == 1


def test_synthesize_dry_run_doesnt_write(tmp_path: Path):
    raw = _seed_raw(tmp_path)
    wiki_sources = tmp_path / "wiki" / "sources"
    wiki_sources.mkdir(parents=True)

    summary = synthesize_new_sessions(
        backend=DummySynthesizer(), raw_dir=raw, wiki_sources_dir=wiki_sources,
        dry_run=True,
    )
    assert summary["new_files"] == 1
    assert summary["synthesized"] == 0
    assert summary["skipped"] == 1
    # No output file created
    assert not (wiki_sources / "test-proj" / "test-synth.md").exists()


def test_synthesize_unavailable_backend(tmp_path: Path):
    class BrokenBackend(BaseSynthesizer):
        def synthesize_source_page(self, *a, **k):
            raise RuntimeError("should not be called")
        def is_available(self):
            return False

    raw = _seed_raw(tmp_path)
    wiki_sources = tmp_path / "wiki" / "sources"
    wiki_sources.mkdir(parents=True)

    summary = synthesize_new_sessions(
        backend=BrokenBackend(), raw_dir=raw, wiki_sources_dir=wiki_sources,
    )
    assert "not available" in summary["errors"][0]
    assert summary["synthesized"] == 0


def test_synthesize_backend_error_is_graceful(tmp_path: Path):
    class CrashingBackend(BaseSynthesizer):
        def synthesize_source_page(self, *a, **k):
            raise ValueError("LLM exploded")
        def is_available(self):
            return True

    raw = _seed_raw(tmp_path)
    wiki_sources = tmp_path / "wiki" / "sources"
    wiki_sources.mkdir(parents=True)
    (tmp_path / "wiki" / "log.md").write_text("# Log\n", encoding="utf-8")

    summary = synthesize_new_sessions(
        backend=CrashingBackend(), raw_dir=raw, wiki_sources_dir=wiki_sources,
    )
    assert summary["synthesized"] == 0
    assert summary["skipped"] == 1
    assert "LLM exploded" in summary["errors"][0]
