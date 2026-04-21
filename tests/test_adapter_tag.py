"""Regression tests for #346 — adapter-specific frontmatter tag.

Before: ``render_session_markdown`` hardcoded
``tags: [claude-code, session-transcript]`` so codex_cli / cursor /
copilot-chat / gemini_cli sessions all appeared under the claude-code
chip on the compiled site.

After: the tag mirrors the calling adapter's registry name, normalised
from ``claude_code`` / ``codex_cli`` style to ``claude-code`` /
``codex-cli``.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from llmwiki.convert import _adapter_tag, render_session_markdown, Redactor, DEFAULT_CONFIG


# ─── _adapter_tag unit ────────────────────────────────────────────────


@pytest.mark.parametrize("adapter,expected", [
    ("claude_code", "claude-code"),
    ("codex_cli", "codex-cli"),
    ("gemini_cli", "gemini-cli"),
    ("cursor", "cursor"),
    ("copilot-chat", "copilot-chat"),
    ("copilot-cli", "copilot-cli"),
    ("opencode", "opencode"),
    ("chatgpt", "chatgpt"),
    ("obsidian", "obsidian"),
    ("jira", "jira"),
    ("meeting", "meeting"),
    ("pdf", "pdf"),
    # Back-compat defaults for empty / missing.
    ("", "claude-code"),
    (None, "claude-code"),
    # Whitespace trimming.
    ("  codex_cli  ", "codex-cli"),
])
def test_adapter_tag_normalisation(adapter, expected):
    assert _adapter_tag(adapter) == expected


# ─── render_session_markdown integration ─────────────────────────────


def _fake_record(ts="2026-04-21T10:00:00Z"):
    return {
        "type": "user",
        "sessionId": "abc-123",
        "timestamp": ts,
        "cwd": "/tmp/proj",
        "gitBranch": "main",
        "message": {"role": "user", "content": "hi"},
    }


def _render(adapter_name: str) -> str:
    records = [_fake_record()]
    redact = Redactor(DEFAULT_CONFIG)
    md, _, _ = render_session_markdown(
        records,
        Path("/tmp/fake.jsonl"),
        "my-proj",
        redact,
        DEFAULT_CONFIG,
        is_subagent_file=False,
        adapter_name=adapter_name,
    )
    return md


def test_render_emits_claude_code_tag_for_claude_adapter():
    md = _render("claude_code")
    assert "tags: [claude-code, session-transcript]" in md


def test_render_emits_codex_cli_tag_for_codex_adapter():
    md = _render("codex_cli")
    assert "tags: [codex-cli, session-transcript]" in md


def test_render_emits_hyphenated_copilot_chat_tag():
    md = _render("copilot-chat")
    assert "tags: [copilot-chat, session-transcript]" in md


def test_render_emits_cursor_tag():
    md = _render("cursor")
    assert "tags: [cursor, session-transcript]" in md


def test_render_defaults_to_claude_code_when_adapter_missing():
    """Older callers (tests, external scripts) that invoke
    ``render_session_markdown`` without passing ``adapter_name`` must
    still produce a valid frontmatter block."""
    records = [_fake_record()]
    md, _, _ = render_session_markdown(
        records,
        Path("/tmp/fake.jsonl"),
        "p",
        Redactor(DEFAULT_CONFIG),
        DEFAULT_CONFIG,
        is_subagent_file=False,
    )
    # Default adapter_name="claude_code" → tag "claude-code".
    assert "tags: [claude-code, session-transcript]" in md


def test_render_never_emits_empty_tag():
    """Defence-in-depth — no matter how we call it, the tag list is
    never ``tags: [, session-transcript]``.  _adapter_tag defaults to
    ``claude-code`` on any falsy input so the bracket always contains
    at least one tag before the comma."""
    for adapter in ("", "   "):
        md = _render(adapter)
        assert "tags: [, " not in md
        assert "tags: [claude-code, session-transcript]" in md


def test_render_session_transcript_tag_always_present():
    """Every sync output must carry the generic ``session-transcript``
    marker so UI filters + lint rules can target it."""
    for adapter in ("claude_code", "codex_cli", "cursor", "gemini_cli"):
        md = _render(adapter)
        assert "session-transcript" in md
