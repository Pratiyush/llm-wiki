"""Tests for the agent-delegate synthesizer (#316).

Covers:

* ``is_available()`` heuristic for agent runtime detection
* ``synthesize_source_page()`` writes the prompt + returns a sentinel
* Re-synthesize reuses the same uuid (idempotent)
* ``complete_pending`` replaces the placeholder + cleans up prompt file
* ``list_pending`` enumerates prompts with metadata
* Backend is wired into ``resolve_backend`` for ``synthesis.backend: "agent"``
* No network calls happen during synthesis (socket guard)
"""

from __future__ import annotations

import os
import socket
from pathlib import Path
from typing import Any

import pytest

from llmwiki.synth.agent_delegate import (
    AgentDelegateSynthesizer,
    complete_pending,
    extract_pending_uuid,
    is_pending,
    list_pending,
    pending_dir,
    sentinel_for,
    _agent_runtime_detected,
)
from llmwiki.synth.pipeline import resolve_backend


@pytest.fixture
def clean_env(monkeypatch):
    """Clear every agent-detection env var so tests get a known state."""
    for v in (
        "LLMWIKI_AGENT_MODE",
        "CLAUDE_CODE",
        "CLAUDECODE",
        "CODEX_CLI",
        "CURSOR_AGENT",
    ):
        monkeypatch.delenv(v, raising=False)


@pytest.fixture
def agent_env(monkeypatch):
    """Simulate being inside Claude Code for tests that need it."""
    for v in ("LLMWIKI_AGENT_MODE", "CLAUDE_CODE", "CODEX_CLI", "CURSOR_AGENT", "CLAUDECODE"):
        monkeypatch.delenv(v, raising=False)
    monkeypatch.setenv("LLMWIKI_AGENT_MODE", "1")


# ─── runtime detection ───────────────────────────────────────────────


def test_is_available_false_outside_agent(clean_env):
    assert AgentDelegateSynthesizer().is_available() is False


def test_is_available_true_with_claude_code(clean_env, monkeypatch):
    monkeypatch.setenv("CLAUDE_CODE", "1")
    assert AgentDelegateSynthesizer().is_available() is True


def test_is_available_true_with_claudecode_variant(clean_env, monkeypatch):
    monkeypatch.setenv("CLAUDECODE", "1")
    assert AgentDelegateSynthesizer().is_available() is True


def test_is_available_true_with_codex(clean_env, monkeypatch):
    monkeypatch.setenv("CODEX_CLI", "yes")
    assert AgentDelegateSynthesizer().is_available() is True


def test_is_available_true_with_cursor(clean_env, monkeypatch):
    monkeypatch.setenv("CURSOR_AGENT", "chat")
    assert AgentDelegateSynthesizer().is_available() is True


def test_explicit_env_var_wins_over_auto_detection(clean_env, monkeypatch):
    monkeypatch.setenv("CLAUDE_CODE", "1")  # would auto-detect
    monkeypatch.setenv("LLMWIKI_AGENT_MODE", "0")
    assert _agent_runtime_detected() is False


def test_explicit_true_env_works(clean_env, monkeypatch):
    monkeypatch.setenv("LLMWIKI_AGENT_MODE", "true")
    assert _agent_runtime_detected() is True


def test_unavailable_reason_is_helpful():
    reason = AgentDelegateSynthesizer().unavailable_reason
    assert "Claude Code" in reason or "Codex" in reason
    assert "LLMWIKI_AGENT_MODE" in reason


# ─── synthesize_source_page ──────────────────────────────────────────


def test_synthesize_writes_prompt_file_and_returns_sentinel(tmp_path, agent_env):
    b = AgentDelegateSynthesizer(pending_root=tmp_path)
    meta = {"slug": "test-session", "project": "llm-wiki", "date": "2026-04-21"}
    prompt_template = "Prompt says: {body}\n\nMeta:\n{meta}"
    result = b.synthesize_source_page("raw body here", meta, prompt_template)

    # Return value carries a sentinel.
    assert is_pending(result)
    uid = extract_pending_uuid(result)
    assert uid is not None

    # The prompt file exists and contains the rendered template.
    prompt_file = tmp_path / f"{uid}.md"
    assert prompt_file.exists()
    text = prompt_file.read_text(encoding="utf-8")
    assert "Prompt says: raw body here" in text
    assert "slug: test-session" in text


def test_synthesize_reuses_uuid_for_same_slug(tmp_path, agent_env):
    b = AgentDelegateSynthesizer(pending_root=tmp_path)
    meta = {"slug": "dup-session", "project": "p", "date": "2026-04-21"}

    r1 = b.synthesize_source_page("first body", meta, "body: {body}")
    uid1 = extract_pending_uuid(r1)

    r2 = b.synthesize_source_page("different body", meta, "body: {body}")
    uid2 = extract_pending_uuid(r2)

    assert uid1 == uid2
    # Prompt file was overwritten with the latest body.
    text = (tmp_path / f"{uid1}.md").read_text(encoding="utf-8")
    assert "different body" in text
    assert "first body" not in text


def test_synthesize_returns_distinct_uuids_for_distinct_slugs(tmp_path, agent_env):
    b = AgentDelegateSynthesizer(pending_root=tmp_path)
    r1 = b.synthesize_source_page("a", {"slug": "one"}, "{body}")
    r2 = b.synthesize_source_page("b", {"slug": "two"}, "{body}")
    assert extract_pending_uuid(r1) != extract_pending_uuid(r2)


def test_synthesize_handles_empty_meta(tmp_path, agent_env):
    b = AgentDelegateSynthesizer(pending_root=tmp_path)
    result = b.synthesize_source_page("body", {}, "{body}")
    assert is_pending(result)


def test_synthesize_handles_empty_body(tmp_path, agent_env):
    b = AgentDelegateSynthesizer(pending_root=tmp_path)
    result = b.synthesize_source_page("", {"slug": "empty"}, "body: {body}")
    uid = extract_pending_uuid(result)
    text = (tmp_path / f"{uid}.md").read_text(encoding="utf-8")
    assert "body: " in text


def test_synthesize_truncates_large_body(tmp_path, agent_env):
    b = AgentDelegateSynthesizer(pending_root=tmp_path)
    huge = "x" * 20000
    result = b.synthesize_source_page(huge, {"slug": "big"}, "{body}")
    uid = extract_pending_uuid(result)
    text = (tmp_path / f"{uid}.md").read_text(encoding="utf-8")
    # 8000-char cap (matches the pipeline's own truncation).
    assert text.count("x") <= 8000


# ─── network isolation ──────────────────────────────────────────────


def test_no_network_during_synthesize(tmp_path, agent_env, monkeypatch):
    """Hard guard: neutralise socket.socket so any HTTP call raises."""
    class _Blocked:
        def __init__(self, *a, **kw):
            raise RuntimeError("network disabled in agent backend")
    monkeypatch.setattr(socket, "socket", _Blocked)
    b = AgentDelegateSynthesizer(pending_root=tmp_path)
    # Must NOT raise — implementation has no network path.
    result = b.synthesize_source_page("body", {"slug": "net"}, "{body}")
    assert is_pending(result)


# ─── complete_pending ────────────────────────────────────────────────


def test_complete_pending_rewrites_placeholder_with_synthesis(tmp_path, agent_env):
    b = AgentDelegateSynthesizer(pending_root=tmp_path)
    meta = {"slug": "page", "project": "p", "date": "2026-04-21"}
    body = b.synthesize_source_page("raw", meta, "{body}")
    uid = extract_pending_uuid(body)

    # Caller writes the full page with frontmatter.
    page = tmp_path / "wiki-page.md"
    page.write_text(
        "---\n"
        "title: \"Session: page\"\n"
        "tags: [claude-code]\n"
        "---\n\n"
        + body,
        encoding="utf-8",
    )

    synthesized = "## Summary\n\nActual content produced by the agent.\n"
    complete_pending(uid, synthesized, page, pending_root=tmp_path)

    final = page.read_text(encoding="utf-8")
    # Frontmatter preserved.
    assert "tags: [claude-code]" in final
    # Placeholder gone.
    assert not is_pending(final)
    # Synthesized body in place.
    assert "Actual content produced by the agent." in final
    # Prompt file cleaned up.
    assert not (tmp_path / f"{uid}.md").exists()


def test_complete_pending_raises_if_page_missing(tmp_path):
    with pytest.raises(FileNotFoundError):
        complete_pending("deadbeef", "body", tmp_path / "nope.md")


def test_complete_pending_raises_if_no_sentinel(tmp_path):
    page = tmp_path / "clean.md"
    page.write_text("---\ntitle: x\n---\n\n## Summary\n", encoding="utf-8")
    with pytest.raises(ValueError, match="no pending sentinel"):
        complete_pending("00000000-0000-0000-0000-000000000000", "body", page)


def test_complete_pending_raises_on_uuid_mismatch(tmp_path, agent_env):
    b = AgentDelegateSynthesizer(pending_root=tmp_path)
    body = b.synthesize_source_page("raw", {"slug": "x"}, "{body}")
    uid = extract_pending_uuid(body)

    page = tmp_path / "p.md"
    page.write_text("---\ntitle: x\n---\n\n" + body, encoding="utf-8")

    with pytest.raises(ValueError, match="uuid mismatch"):
        complete_pending("wrong-uuid", "body", page, pending_root=tmp_path)


def test_complete_pending_survives_missing_prompt_file(tmp_path, agent_env):
    b = AgentDelegateSynthesizer(pending_root=tmp_path)
    body = b.synthesize_source_page("raw", {"slug": "x"}, "{body}")
    uid = extract_pending_uuid(body)

    # Delete the prompt file before completion.
    (tmp_path / f"{uid}.md").unlink()

    page = tmp_path / "p.md"
    page.write_text("---\ntitle: x\n---\n\n" + body, encoding="utf-8")
    # Must NOT raise — cleanup is best-effort.
    complete_pending(uid, "## Summary\n\nSynth.\n", page, pending_root=tmp_path)
    assert "## Summary" in page.read_text(encoding="utf-8")


# ─── list_pending ────────────────────────────────────────────────────


def test_list_pending_empty_when_no_dir(tmp_path):
    assert list_pending(tmp_path / "nope") == []


def test_list_pending_returns_metadata(tmp_path, agent_env):
    b = AgentDelegateSynthesizer(pending_root=tmp_path)
    b.synthesize_source_page("a", {"slug": "one", "project": "proj-a", "date": "2026-04-21"}, "{body}")
    b.synthesize_source_page("b", {"slug": "two", "project": "proj-b", "date": "2026-04-20"}, "{body}")

    rows = list_pending(tmp_path)
    assert len(rows) == 2
    slugs = {r["slug"] for r in rows}
    assert slugs == {"one", "two"}
    projects = {r["project"] for r in rows}
    assert projects == {"proj-a", "proj-b"}
    for r in rows:
        assert r["uuid"]
        assert r["path"].endswith(".md")


# ─── resolve_backend integration ─────────────────────────────────────


def test_resolve_backend_returns_agent_when_configured():
    cfg = {"synthesis": {"backend": "agent"}}
    backend = resolve_backend(cfg)
    assert isinstance(backend, AgentDelegateSynthesizer)


def test_resolve_backend_accepts_hyphenated_name():
    cfg = {"synthesis": {"backend": "agent-delegate"}}
    assert isinstance(resolve_backend(cfg), AgentDelegateSynthesizer)


def test_resolve_backend_accepts_underscored_name():
    cfg = {"synthesis": {"backend": "agent_delegate"}}
    assert isinstance(resolve_backend(cfg), AgentDelegateSynthesizer)


def test_resolve_backend_case_insensitive():
    cfg = {"synthesis": {"backend": "Agent"}}
    assert isinstance(resolve_backend(cfg), AgentDelegateSynthesizer)


# ─── sentinel parsing ────────────────────────────────────────────────


def test_sentinel_roundtrip():
    import uuid as _uuid
    uid = str(_uuid.uuid4())
    body = f"{sentinel_for(uid)}\n\n## Summary\n"
    assert is_pending(body)
    assert extract_pending_uuid(body) == uid


def test_sentinel_not_present_returns_none():
    assert extract_pending_uuid("## Summary\n") is None
    assert is_pending("## Summary\n") is False


def test_sentinel_tolerates_extra_whitespace():
    body = "   <!--   llmwiki-pending: 12345678-1234-1234-1234-123456789abc   -->   \n\n## Summary"
    assert extract_pending_uuid(body) == "12345678-1234-1234-1234-123456789abc"
