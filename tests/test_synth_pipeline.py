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
    # G-12 (#298): body mentions are surfaced in `## Raw Mentions` as
    # plain text, not wikilinks. Only real entity pages (the project
    # entity) are linked. pytest/FastAPI are mentioned, not linked.
    assert "## Raw Mentions" in result
    assert "pytest" in result
    assert "FastAPI" in result
    # Assert no fabricated wikilinks — the ONLY wikilink should be the
    # project entity, which the ingest workflow guarantees exists.
    assert "[[pytest]]" not in result
    assert "[[FastAPI]]" not in result
    assert "[[Demo]]" in result  # title-cased project name


def test_dummy_synthesizer_handles_empty_body():
    backend = DummySynthesizer()
    result = backend.synthesize_source_page("", {"slug": "empty"}, "template")
    assert "## Summary" in result
    assert "## Raw Mentions" in result
    assert "(no mentions detected)" in result


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
    log_file = tmp_path / "wiki" / "log.md"
    log_file.write_text("# Log\n", encoding="utf-8")

    summary = synthesize_new_sessions(
        backend=DummySynthesizer(),
        raw_dir=raw,
        wiki_sources_dir=wiki_sources,
        log_path=log_file,
    )
    assert summary["total_scanned"] == 1
    assert summary["new_files"] == 1
    assert summary["synthesized"] == 1
    assert summary["errors"] == []
    # G-06 (#292): output filename is date-prefixed to prevent silent
    # slug collisions across sessions with identical haiku-style slugs.
    out_file = wiki_sources / "test-proj" / "2026-04-09-test-synth.md"
    assert out_file.exists(), f"expected date-prefixed file at {out_file}"
    content = out_file.read_text(encoding="utf-8")
    assert "type: source" in content
    assert "## Summary" in content


def test_synthesize_idempotent_rerun_is_noop(tmp_path: Path):
    raw = _seed_raw(tmp_path)
    wiki_sources = tmp_path / "wiki" / "sources"
    wiki_sources.mkdir(parents=True)
    log_file = tmp_path / "wiki" / "log.md"
    log_file.write_text("# Log\n", encoding="utf-8")

    # First run
    s1 = synthesize_new_sessions(
        backend=DummySynthesizer(), raw_dir=raw, wiki_sources_dir=wiki_sources,
        log_path=log_file,
    )
    assert s1["synthesized"] == 1

    # Second run — should be a no-op (mtime hasn't changed)
    s2 = synthesize_new_sessions(
        backend=DummySynthesizer(), raw_dir=raw, wiki_sources_dir=wiki_sources,
        log_path=log_file,
    )
    assert s2["new_files"] == 0
    assert s2["synthesized"] == 0


def test_synthesize_force_resynthesizes(tmp_path: Path):
    raw = _seed_raw(tmp_path)
    wiki_sources = tmp_path / "wiki" / "sources"
    wiki_sources.mkdir(parents=True)
    log_file = tmp_path / "wiki" / "log.md"
    log_file.write_text("# Log\n", encoding="utf-8")

    # First run
    synthesize_new_sessions(
        backend=DummySynthesizer(), raw_dir=raw, wiki_sources_dir=wiki_sources,
        log_path=log_file,
    )
    # Force re-run
    s2 = synthesize_new_sessions(
        backend=DummySynthesizer(), raw_dir=raw, wiki_sources_dir=wiki_sources,
        force=True, log_path=log_file,
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
    log_file = tmp_path / "wiki" / "log.md"
    log_file.write_text("# Log\n", encoding="utf-8")

    summary = synthesize_new_sessions(
        backend=CrashingBackend(), raw_dir=raw, wiki_sources_dir=wiki_sources,
        log_path=log_file,
    )
    assert summary["synthesized"] == 0
    assert summary["skipped"] == 1
    assert "LLM exploded" in summary["errors"][0]


# ─── G-06 (#292): slug-collision prevention ─────────────────────────────


def test_synthesize_date_prefix_prevents_slug_collisions(tmp_path: Path):
    """Two sessions with the same slug but different dates must BOTH
    end up on disk — no silent overwrites."""
    raw = tmp_path / "raw" / "sessions" / "proj"
    raw.mkdir(parents=True)
    # Two sessions, same slug, different dates — this was the demo-corpus
    # failure mode where 777 synthesized collapsed to 714 on disk.
    for d in ("2026-03-01", "2026-04-01"):
        (raw / f"{d}-flickering-orbiting-fern.md").write_text(
            f"---\nslug: flickering-orbiting-fern\nproject: proj\n"
            f"date: {d}\nmodel: claude-sonnet-4-6\n---\n\n# body {d}\n",
            encoding="utf-8",
        )
    wiki_sources = tmp_path / "wiki" / "sources"
    wiki_sources.mkdir(parents=True)
    log_file = tmp_path / "wiki" / "log.md"
    log_file.write_text("# Log\n", encoding="utf-8")

    summary = synthesize_new_sessions(
        backend=DummySynthesizer(),
        raw_dir=tmp_path / "raw" / "sessions",
        wiki_sources_dir=wiki_sources,
        log_path=log_file,
    )
    assert summary["synthesized"] == 2
    written = sorted((wiki_sources / "proj").glob("*.md"))
    assert len(written) == 2, f"expected 2 files, got {written}"
    # Both files must exist and be distinct
    names = {p.name for p in written}
    assert "2026-03-01-flickering-orbiting-fern.md" in names
    assert "2026-04-01-flickering-orbiting-fern.md" in names


# ─── G-21 (#307): slug normalisation ────────────────────────────────────


def test_slug_normalisation_strips_unsafe_chars():
    from llmwiki.synth.pipeline import _normalise_slug
    assert _normalise_slug("00 - Master Framework Index") == "00-Master-Framework-Index"
    assert _normalise_slug("path/with/slashes") == "path-with-slashes"
    assert _normalise_slug('bad:chars<here>|pipe"quote') == "bad-chars-here-pipe-quote"
    assert _normalise_slug("") == "unknown"
    assert _normalise_slug("   ") == "unknown"
    # Unicode + dashes preserved
    assert _normalise_slug("café-naïve") == "café-naïve"


# ─── G-09 (#295): index rebuild ─────────────────────────────────────────


def test_synthesize_rebuilds_index_md(tmp_path: Path):
    """After synthesize, wiki/index.md must list every source page."""
    raw = _seed_raw(tmp_path)
    wiki_dir = tmp_path / "wiki"
    wiki_sources = wiki_dir / "sources"
    wiki_sources.mkdir(parents=True)
    # Seed an index.md with hand-curated content that must survive.
    (wiki_dir / "index.md").write_text(
        "# Wiki Index\n\n## Overview\n- curated\n\n## Sources\n*(none)*\n"
        "\n## Entities\n- [Pratiyush](entities/Pratiyush.md) — keep me\n",
        encoding="utf-8",
    )
    log_file = wiki_dir / "log.md"
    log_file.write_text("# Log\n", encoding="utf-8")

    synthesize_new_sessions(
        backend=DummySynthesizer(), raw_dir=raw, wiki_sources_dir=wiki_sources,
        log_path=log_file,
    )

    idx = (wiki_dir / "index.md").read_text(encoding="utf-8")
    # Source is listed
    assert "sources/test-proj/2026-04-09-test-synth.md" in idx
    # Hand-curated Entities section survived
    assert "[Pratiyush](entities/Pratiyush.md)" in idx
    # Overview line survived
    assert "- curated" in idx


def test_rebuild_index_creates_index_when_missing(tmp_path: Path):
    """If wiki/index.md doesn't exist yet, _rebuild_index seeds one."""
    from llmwiki.synth.pipeline import _rebuild_index
    wiki_dir = tmp_path / "wiki"
    sources = wiki_dir / "sources" / "proj"
    sources.mkdir(parents=True)
    (sources / "2026-04-09-hello.md").write_text(
        '---\ntitle: "Session: hello"\ntype: source\n---\n# body\n',
        encoding="utf-8",
    )
    out = _rebuild_index(wiki_dir)
    assert out is not None and out.is_file()
    text = out.read_text(encoding="utf-8")
    assert "## Sources" in text
    assert "sources/proj/2026-04-09-hello.md" in text


# ─── G-20 (#306): batched log entry ─────────────────────────────────────


def test_synthesize_logs_one_summary_entry_per_run(tmp_path: Path):
    """Each synthesize invocation should append ONE log heading total,
    not one per page (old behaviour produced 60+ lines per run)."""
    raw = tmp_path / "raw" / "sessions" / "proj"
    raw.mkdir(parents=True)
    for i in range(3):
        (raw / f"2026-04-{i + 1:02d}-slug-{i}.md").write_text(
            f"---\nslug: slug-{i}\nproject: proj\ndate: 2026-04-{i + 1:02d}\n---\n"
            f"# body {i}\n",
            encoding="utf-8",
        )
    wiki_sources = tmp_path / "wiki" / "sources"
    wiki_sources.mkdir(parents=True)
    log_file = tmp_path / "wiki" / "log.md"
    log_file.write_text("# Log\n", encoding="utf-8")

    summary = synthesize_new_sessions(
        backend=DummySynthesizer(),
        raw_dir=tmp_path / "raw" / "sessions",
        wiki_sources_dir=wiki_sources,
        log_path=log_file,
    )
    assert summary["synthesized"] == 3
    log_text = log_file.read_text(encoding="utf-8")
    synth_headings = [
        ln for ln in log_text.splitlines()
        if ln.startswith("## [") and "synthesize" in ln
    ]
    assert len(synth_headings) == 1, (
        f"expected one batched synth entry, got {len(synth_headings)}:\n"
        + "\n".join(synth_headings)
    )
    # Separator check: G-08 (#294) uses "→" arrow, not raw slash
    assert "sessions across" in synth_headings[0]
