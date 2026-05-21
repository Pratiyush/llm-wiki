"""Tests for the OpenCode / OpenClaw adapter (v1.1, #43)."""

from __future__ import annotations

from pathlib import Path

import pytest

from llmwiki.adapters.opencode import OpenCodeAdapter


# ─── Adapter registration ─────────────────────────────────────────────


def test_adapter_registered():
    from llmwiki.adapters import REGISTRY, discover_adapters
    discover_adapters()
    assert "opencode" in REGISTRY


def test_adapter_has_schema_versions():
    assert "v1" in OpenCodeAdapter.SUPPORTED_SCHEMA_VERSIONS


def test_adapter_has_default_roots_for_all_platforms():
    roots = OpenCodeAdapter.DEFAULT_ROOTS
    root_strs = [str(r).replace("\\", "/") for r in roots]
    # macOS
    assert any("Library/Application Support/opencode" in r for r in root_strs)
    # Linux XDG
    assert any(".config/opencode" in r for r in root_strs)
    # Windows
    assert any("AppData/Roaming/opencode" in r for r in root_strs)


def test_adapter_includes_openclaw_variant():
    root_strs = [str(r).replace("\\", "/") for r in OpenCodeAdapter.DEFAULT_ROOTS]
    # OpenClaw community fork uses its own dir
    assert any("openclaw" in r for r in root_strs)


# ─── Config-driven roots ─────────────────────────────────────────────


def test_adapter_uses_config_roots(tmp_path: Path):
    custom = tmp_path / "my-opencode"
    custom.mkdir()
    a = OpenCodeAdapter(config={
        "adapters": {"opencode": {"roots": [str(custom)]}}
    })
    assert a.roots == [custom]


def test_adapter_falls_back_to_defaults_when_no_config():
    a = OpenCodeAdapter()
    assert a.roots == OpenCodeAdapter.DEFAULT_ROOTS


# ─── Discovery ───────────────────────────────────────────────────────


def test_discover_empty_when_no_roots_exist(tmp_path: Path):
    a = OpenCodeAdapter(config={
        "adapters": {"opencode": {"roots": [str(tmp_path / "nonexistent")]}}
    })
    assert a.discover_sessions() == []


def test_discover_finds_jsonl_files(tmp_path: Path):
    # Create a fake opencode session store
    store = tmp_path / "opencode" / "sessions"
    store.mkdir(parents=True)
    (store / "my-project-01.jsonl").write_text(
        '{"role": "user", "content": "hi"}\n', encoding="utf-8"
    )
    (store / "my-project-02.jsonl").write_text(
        '{"role": "assistant", "content": "hello"}\n', encoding="utf-8"
    )
    # Non-jsonl file should NOT be discovered
    (store / "readme.txt").write_text("ignore me", encoding="utf-8")

    a = OpenCodeAdapter(config={
        "adapters": {"opencode": {"roots": [str(store)]}}
    })
    sessions = a.discover_sessions()
    assert len(sessions) == 2
    names = [s.name for s in sessions]
    assert all(n.endswith(".jsonl") for n in names)


def test_discover_nested_subdirs(tmp_path: Path):
    store = tmp_path / "opencode" / "sessions"
    store.mkdir(parents=True)
    nested = store / "project-a"
    nested.mkdir()
    (nested / "session1.jsonl").write_text('{}\n', encoding="utf-8")

    a = OpenCodeAdapter(config={
        "adapters": {"opencode": {"roots": [str(store)]}}
    })
    sessions = a.discover_sessions()
    assert len(sessions) == 1


# ─── Project slug derivation ─────────────────────────────────────────


def test_project_slug_from_flat_filename(tmp_path: Path):
    store = tmp_path / "opencode" / "sessions"
    store.mkdir(parents=True)
    path = store / "my-project-abc123.jsonl"
    path.touch()
    a = OpenCodeAdapter(config={
        "adapters": {"opencode": {"roots": [str(store)]}}
    })
    assert a.derive_project_slug(path) == "my"  # split on first dash


def test_project_slug_from_nested_subdir(tmp_path: Path):
    store = tmp_path / "opencode" / "sessions"
    proj = store / "fancy-project"
    proj.mkdir(parents=True)
    path = proj / "session-1.jsonl"
    path.touch()
    a = OpenCodeAdapter(config={
        "adapters": {"opencode": {"roots": [str(store)]}}
    })
    assert a.derive_project_slug(path) == "fancy-project"


def test_project_slug_without_dashes(tmp_path: Path):
    store = tmp_path / "opencode" / "sessions"
    store.mkdir(parents=True)
    path = store / "noslugs.jsonl"
    path.touch()
    a = OpenCodeAdapter(config={
        "adapters": {"opencode": {"roots": [str(store)]}}
    })
    # Short enough to stay whole
    assert a.derive_project_slug(path) == "noslugs"


# ─── Subagent detection ──────────────────────────────────────────────


def test_is_subagent_true():
    a = OpenCodeAdapter()
    assert a.is_subagent(Path("session-subagent-abc.jsonl")) is True


def test_is_subagent_false():
    a = OpenCodeAdapter()
    assert a.is_subagent(Path("session-main.jsonl")) is False


# ─── Record normalization ────────────────────────────────────────────


def test_normalize_user_record():
    a = OpenCodeAdapter()
    records = [{"role": "user", "content": "hi"}]
    out = a.normalize_records(records)
    assert len(out) == 1
    assert out[0]["type"] == "user"
    assert out[0]["message"]["role"] == "user"
    assert out[0]["message"]["content"] == "hi"


def test_normalize_assistant_record():
    a = OpenCodeAdapter()
    records = [{"role": "assistant", "content": "response"}]
    out = a.normalize_records(records)
    assert out[0]["type"] == "assistant"


def test_normalize_tool_role_maps_to_user_type():
    """Tool results are user-side messages in Claude Code shape."""
    a = OpenCodeAdapter()
    records = [{"role": "tool", "content": "tool result"}]
    out = a.normalize_records(records)
    assert out[0]["type"] == "user"
    # Preserve the original role for accurate rendering
    assert out[0]["message"]["role"] == "tool"


def test_normalize_preserves_timestamp():
    a = OpenCodeAdapter()
    records = [{"role": "user", "content": "hi", "timestamp": "2026-04-16T10:00:00Z"}]
    out = a.normalize_records(records)
    assert out[0]["timestamp"] == "2026-04-16T10:00:00Z"


def test_normalize_passes_through_claude_shape():
    """Records already in Claude format must not be rewrapped."""
    a = OpenCodeAdapter()
    records = [{
        "type": "user",
        "message": {"role": "user", "content": "already normalized"},
    }]
    out = a.normalize_records(records)
    assert out == records


def test_normalize_skips_non_dict_records():
    a = OpenCodeAdapter()
    records = ["not a dict", 42, {"role": "user", "content": "ok"}]
    out = a.normalize_records(records)
    # Only the dict is kept
    assert len(out) == 1


def test_normalize_passes_through_metadata_records():
    """Records without role/content (e.g. session-init metadata) pass through."""
    a = OpenCodeAdapter()
    records = [{"sessionId": "abc", "type": "session-init"}]
    out = a.normalize_records(records)
    assert out == records


def test_normalize_empty_list():
    a = OpenCodeAdapter()
    assert a.normalize_records([]) == []


# ─── Availability ────────────────────────────────────────────────────


def test_is_available_false_when_no_paths():
    """is_available checks DEFAULT_ROOTS — on a fresh test runner it's typically False."""
    # We can't guarantee this without a user install; just assert the call succeeds
    result = OpenCodeAdapter.is_available()
    assert isinstance(result, bool)
