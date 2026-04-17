"""Tests for the ChatGPT conversation-export adapter (v1.1, #44)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from llmwiki.adapters.chatgpt import (
    ChatGPTAdapter,
    _linearize,
    _role,
    _content_parts,
    parse_conversations_json,
    render_conversation_markdown,
    _fmt_ts,
)


# ─── Fixtures ──────────────────────────────────────────────────────────


SAMPLE_EXPORT = [
    {
        "title": "Debugging my FastAPI route",
        "create_time": 1730246400.0,
        "update_time": 1730250000.0,
        "current_node": "leaf-1",
        "mapping": {
            "root-1": {
                "id": "root-1",
                "parent": None,
                "children": ["user-1"],
                "message": None,
            },
            "user-1": {
                "id": "user-1",
                "parent": "root-1",
                "children": ["assistant-1"],
                "message": {
                    "author": {"role": "user"},
                    "content": {"parts": ["Why is my route returning 404?"]},
                    "create_time": 1730246402.0,
                },
            },
            "assistant-1": {
                "id": "assistant-1",
                "parent": "user-1",
                "children": ["leaf-1"],
                "message": {
                    "author": {"role": "assistant"},
                    "content": {"parts": ["Check your path prefix..."]},
                    "create_time": 1730246500.0,
                },
            },
            "leaf-1": {
                "id": "leaf-1",
                "parent": "assistant-1",
                "children": [],
                "message": {
                    "author": {"role": "user"},
                    "content": {"parts": ["Thanks, that fixed it!"]},
                    "create_time": 1730246600.0,
                },
            },
        },
    },
]


def _write_export(tmp_path: Path, data=None) -> Path:
    d = tmp_path / "chatgpt-export"
    d.mkdir()
    path = d / "conversations.json"
    path.write_text(json.dumps(data if data is not None else SAMPLE_EXPORT), encoding="utf-8")
    return d


# ─── _role ────────────────────────────────────────────────────────────


def test_role_user():
    assert _role({"author": {"role": "user"}}) == "user"


def test_role_assistant():
    assert _role({"author": {"role": "assistant"}}) == "assistant"


def test_role_missing_returns_unknown():
    assert _role({}) == "unknown"
    assert _role({"author": {}}) == "unknown"


# ─── _content_parts ───────────────────────────────────────────────────


def test_parts_string_list():
    msg = {"content": {"parts": ["a", "b"]}}
    assert _content_parts(msg) == ["a", "b"]


def test_parts_handles_dict_entries():
    msg = {"content": {"parts": ["hello", {"text": "world"}]}}
    assert _content_parts(msg) == ["hello", "world"]


def test_parts_empty_when_missing():
    assert _content_parts({}) == []
    assert _content_parts({"content": None}) == []
    assert _content_parts({"content": {}}) == []


# ─── _linearize ───────────────────────────────────────────────────────


def test_linearize_walks_parent_chain():
    conv = SAMPLE_EXPORT[0]
    msgs = list(_linearize(conv))
    # 4 nodes total, but root has message=None so _linearize skips it.
    # Order yielded: user → assistant → user
    assert len(msgs) == 3
    roles = [_role(m) for m in msgs]
    assert roles == ["user", "assistant", "user"]


def test_linearize_no_current_node():
    conv = {"mapping": {"a": {}}}
    assert list(_linearize(conv)) == []


def test_linearize_empty_mapping():
    conv = {"current_node": "x", "mapping": {}}
    assert list(_linearize(conv)) == []


# ─── parse_conversations_json ────────────────────────────────────────


def test_parse_valid_export(tmp_path: Path):
    d = _write_export(tmp_path)
    sessions = parse_conversations_json(d / "conversations.json")
    assert len(sessions) == 1
    s = sessions[0]
    assert s["title"] == "Debugging my FastAPI route"
    assert len(s["messages"]) == 3  # root has no message → excluded
    assert s["messages"][0]["role"] == "user"
    assert s["messages"][1]["role"] == "assistant"


def test_parse_missing_file(tmp_path: Path):
    assert parse_conversations_json(tmp_path / "nonexistent.json") == []


def test_parse_malformed_json(tmp_path: Path):
    path = tmp_path / "bad.json"
    path.write_text("NOT JSON", encoding="utf-8")
    assert parse_conversations_json(path) == []


def test_parse_not_a_list(tmp_path: Path):
    path = tmp_path / "wrong.json"
    path.write_text('{"not": "a list"}', encoding="utf-8")
    assert parse_conversations_json(path) == []


def test_parse_empty_array(tmp_path: Path):
    path = tmp_path / "empty.json"
    path.write_text("[]", encoding="utf-8")
    assert parse_conversations_json(path) == []


def test_parse_skips_malformed_conversation(tmp_path: Path):
    path = tmp_path / "mixed.json"
    path.write_text(json.dumps([
        "not a dict",  # skipped
        SAMPLE_EXPORT[0],
    ]), encoding="utf-8")
    sessions = parse_conversations_json(path)
    assert len(sessions) == 1


# ─── _fmt_ts ──────────────────────────────────────────────────────────


def test_fmt_ts_valid():
    # 2024-10-30 unix timestamp
    result = _fmt_ts(1730246400.0)
    assert result.startswith("2024-")


def test_fmt_ts_none():
    assert _fmt_ts(None) == ""


def test_fmt_ts_invalid():
    assert _fmt_ts("not-a-number") == ""


# ─── render_conversation_markdown ────────────────────────────────────


def test_render_has_frontmatter():
    session = parse_conversations_json(
        _write_export(Path(__file__).parent.parent / "tmp-chat") / "conversations.json"
    ) if False else {
        "title": "Test",
        "created": 1730246400.0,
        "updated": None,
        "messages": [
            {"role": "user", "text": "hi", "created": 1730246400.0},
            {"role": "assistant", "text": "hello", "created": 1730246500.0},
        ],
    }
    md = render_conversation_markdown(session)
    assert md.startswith("---\n")
    assert "type: source" in md
    assert "tags: [chatgpt, session-transcript]" in md
    assert "# Test" in md


def test_render_has_message_count():
    session = {
        "title": "X",
        "created": None,
        "updated": None,
        "messages": [
            {"role": "user", "text": "a", "created": None},
        ],
    }
    md = render_conversation_markdown(session)
    assert "message_count: 1" in md


def test_render_includes_conversation_turns():
    session = {
        "title": "X",
        "created": None,
        "updated": None,
        "messages": [
            {"role": "user", "text": "Q1", "created": None},
            {"role": "assistant", "text": "A1", "created": None},
        ],
    }
    md = render_conversation_markdown(session)
    assert "### User" in md
    assert "### Assistant" in md
    assert "Q1" in md
    assert "A1" in md


def test_render_empty_conversation():
    session = {"title": "Empty", "created": None, "updated": None, "messages": []}
    md = render_conversation_markdown(session)
    assert "message_count: 0" in md


def test_render_collects_unique_roles():
    session = {
        "title": "X",
        "created": None,
        "updated": None,
        "messages": [
            {"role": "user", "text": "a", "created": None},
            {"role": "assistant", "text": "b", "created": None},
            {"role": "user", "text": "c", "created": None},
        ],
    }
    md = render_conversation_markdown(session)
    assert "roles: [assistant, user]" in md


# ─── Adapter class ────────────────────────────────────────────────────


def test_adapter_not_available_by_default():
    assert ChatGPTAdapter.is_available() is False


def test_adapter_disabled_by_config():
    a = ChatGPTAdapter(config={"chatgpt": {"enabled": False}})
    assert a.is_available_with_config() is False


def test_adapter_enabled_but_no_file(tmp_path: Path):
    a = ChatGPTAdapter(config={
        "chatgpt": {"enabled": True, "export_dirs": [str(tmp_path / "missing")]}
    })
    assert a.is_available_with_config() is False


def test_adapter_enabled_with_valid_export(tmp_path: Path):
    d = _write_export(tmp_path)
    a = ChatGPTAdapter(config={
        "chatgpt": {"enabled": True, "export_dirs": [str(d)]}
    })
    assert a.is_available_with_config() is True
    sessions = a.discover_sessions()
    assert len(sessions) == 1
    assert sessions[0].name == "conversations.json"


def test_adapter_returns_empty_when_no_exports(tmp_path: Path):
    a = ChatGPTAdapter(config={
        "chatgpt": {"enabled": True, "export_dirs": [str(tmp_path)]}
    })
    assert a.discover_sessions() == []
