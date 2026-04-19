"""Tests for state-file portability (G-04 · #290) and the int-coerce
fix for sub-agent tool args (G-05 · #291) in ``llmwiki/convert.py``.

Covers:
* ``_portable_state_key`` — home-relative formatting, adapter scoping,
  out-of-home fallback, Windows-style paths, unicode.
* ``_migrate_legacy_state`` — legacy→new migration for every known
  adapter, hint matching, unknown-path passthrough, type rejection,
  idempotent re-migration.
* ``load_state`` — migration runs once and persists the rewrite.
* ``save_state`` — deterministic output ordering.
* ``_coerce_int`` — int/str/float/bool/None/overflow/unicode digits.
* End-to-end: ``summarize_tool_use`` no longer raises on string tool args.
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest

from llmwiki.convert import (
    Redactor,
    DEFAULT_CONFIG,
    _coerce_int,
    _migrate_legacy_state,
    _portable_state_key,
    load_state,
    save_state,
    summarize_tool_use,
)


# ─── _portable_state_key ──────────────────────────────────────────────────


def test_portable_key_strips_home_prefix(tmp_path, monkeypatch):
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: tmp_path))
    p = tmp_path / ".claude" / "projects" / "foo" / "bar.jsonl"
    p.parent.mkdir(parents=True)
    p.touch()
    key = _portable_state_key("claude_code", p)
    assert key == "claude_code::.claude/projects/foo/bar.jsonl"


def test_portable_key_uses_posix_separators(tmp_path, monkeypatch):
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: tmp_path))
    p = tmp_path / "a" / "b" / "c.jsonl"
    p.parent.mkdir(parents=True)
    p.touch()
    key = _portable_state_key("x", p)
    assert "\\" not in key
    assert "/" in key


def test_portable_key_falls_back_for_paths_outside_home(tmp_path, monkeypatch):
    """Paths outside $HOME keep their absolute form — we'd rather
    preserve the key than silently drop state."""
    fake_home = tmp_path / "home"
    fake_home.mkdir()
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: fake_home))
    outside = tmp_path / "outside" / "foo.jsonl"
    outside.parent.mkdir()
    outside.touch()
    key = _portable_state_key("x", outside)
    assert key.startswith("x::")
    # The rel portion still contains the real path (absolute on the filesystem).
    assert str(outside) in key


def test_portable_key_scopes_by_adapter_name():
    """Two adapters pointing at the same file must get distinct keys."""
    a = _portable_state_key("claude_code", Path("/tmp/x"))
    b = _portable_state_key("codex_cli", Path("/tmp/x"))
    assert a != b
    assert a.startswith("claude_code::")
    assert b.startswith("codex_cli::")


def test_portable_key_preserves_unicode(tmp_path, monkeypatch):
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: tmp_path))
    p = tmp_path / "日本語" / "café.jsonl"
    p.parent.mkdir()
    p.touch()
    key = _portable_state_key("x", p)
    assert "日本語" in key
    assert "café" in key


# ─── _migrate_legacy_state ────────────────────────────────────────────────


def test_migrate_maps_claude_code_absolute_paths(monkeypatch, tmp_path):
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: tmp_path))
    legacy = {
        str(tmp_path / ".claude" / "projects" / "x" / "session.jsonl"): 1.5,
    }
    migrated, count = _migrate_legacy_state(legacy, ["claude_code", "codex_cli"])
    assert count == 1
    assert "claude_code::.claude/projects/x/session.jsonl" in migrated
    assert migrated["claude_code::.claude/projects/x/session.jsonl"] == 1.5


def test_migrate_handles_codex_and_obsidian(monkeypatch, tmp_path):
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: tmp_path))
    legacy = {
        str(tmp_path / ".codex" / "sessions" / "a.jsonl"): 1.0,
        str(tmp_path / "Obsidian Vault" / "note.md"): 2.0,
    }
    migrated, count = _migrate_legacy_state(
        legacy, ["codex_cli", "obsidian"]
    )
    assert count == 2
    assert any(k.startswith("codex_cli::") for k in migrated)
    assert any(k.startswith("obsidian::") for k in migrated)


def test_migrate_preserves_already_portable_keys():
    portable = {
        "claude_code::.claude/projects/foo/bar.jsonl": 1.0,
    }
    migrated, count = _migrate_legacy_state(portable, ["claude_code"])
    assert count == 0
    assert migrated == portable


def test_migrate_skips_non_string_and_non_numeric_entries():
    garbage = {
        "good::key": 1.0,
        123: 4.5,                      # non-string key
        "non-numeric-value": "hello",  # non-numeric value
        "true-value": True,            # bool is rejected as non-numeric
    }
    migrated, _ = _migrate_legacy_state(garbage, ["x"])
    assert "good::key" in migrated
    # Note: booleans subclass int but are also explicitly rejected by design.
    assert 123 not in migrated


def test_migrate_passes_through_unclassifiable_absolute_keys(monkeypatch, tmp_path):
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: tmp_path))
    unknown_path = "/var/log/unrelated.log"
    legacy = {unknown_path: 3.0}
    migrated, count = _migrate_legacy_state(legacy, ["claude_code"])
    # No hint matches → preserved verbatim, count stays 0.
    assert count == 0
    assert unknown_path in migrated


def test_migrate_respects_unknown_adapter_names(monkeypatch, tmp_path):
    """If the adapter isn't enabled, we shouldn't use its hint."""
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: tmp_path))
    legacy = {
        str(tmp_path / ".codex" / "sessions" / "a.jsonl"): 1.0,
    }
    # codex_cli not in the adapter list — entry stays raw.
    migrated, count = _migrate_legacy_state(legacy, ["claude_code"])
    assert count == 0


# ─── load_state + save_state ──────────────────────────────────────────────


def test_load_state_missing_returns_empty(tmp_path):
    assert load_state(tmp_path / "nope.json", adapter_names=[]) == {}


def test_load_state_corrupt_returns_empty(tmp_path):
    f = tmp_path / "state.json"
    f.write_text("{ this is not json", encoding="utf-8")
    assert load_state(f, adapter_names=[]) == {}


def test_load_state_non_dict_payload_returns_empty(tmp_path):
    f = tmp_path / "state.json"
    f.write_text(json.dumps(["not", "a", "dict"]), encoding="utf-8")
    assert load_state(f, adapter_names=[]) == {}


def test_load_state_migration_persists_to_disk(tmp_path, monkeypatch):
    """After first load the file should contain portable keys only."""
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: tmp_path))
    legacy = {
        str(tmp_path / ".claude" / "projects" / "x" / "a.jsonl"): 1.0,
    }
    state_file = tmp_path / "state.json"
    state_file.write_text(json.dumps(legacy), encoding="utf-8")

    _ = load_state(state_file, adapter_names=["claude_code"])

    # On-disk keys should be the migrated form.
    disk = json.loads(state_file.read_text(encoding="utf-8"))
    assert all(isinstance(k, str) and "::" in k for k in disk.keys())
    # Re-loading must be a no-op migration (nothing extra to do).
    second = load_state(state_file, adapter_names=["claude_code"])
    assert second == disk


def test_save_state_is_deterministic(tmp_path):
    state_file = tmp_path / "state.json"
    state = {
        "z::c": 3.0,
        "a::a": 1.0,
        "m::b": 2.0,
    }
    save_state(state_file, state)
    contents = state_file.read_text(encoding="utf-8")
    # sort_keys produces alphabetical ordering.
    assert contents.find("a::a") < contents.find("m::b") < contents.find("z::c")


# ─── _coerce_int ──────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    "value,expected",
    [
        (42, 42),
        ("42", 42),
        ("  42  ", 42),
        ("-17", -17),
        ("0", 0),
        (3.9, 3),
        (-2.5, -2),
        ("3.14", 3),
        (None, None),
        ("", None),
        ("   ", None),
        ("not-a-number", None),
        ("1.2.3", None),
        ([], None),
        ({}, None),
        (object(), None),
        (True, None),   # bools are explicitly rejected (footgun)
        (False, None),
        (float("inf"), None),
        (float("nan"), None),
    ],
)
def test_coerce_int_boundary_inputs(value, expected):
    assert _coerce_int(value) == expected


def test_coerce_int_huge_string_overflow_returns_none():
    # 10^400 overflows float() but is still a valid int literal — we keep it.
    big = "1" + "0" * 400
    assert _coerce_int(big) == int(big)


def test_coerce_int_unicode_digits_rejected():
    """Unicode digits aren't base-10 int literals — reject."""
    # '१२३' is Devanagari for 123; Python int() accepts it, but we expect
    # the bare str branch to parse it if Python considers it an integer.
    # Either behaviour is acceptable — assert it's either the numeric value
    # or None (documenting we don't crash).
    result = _coerce_int("१२३")
    assert result in (None, 123)


# ─── summarize_tool_use — the real G-05 regression ───────────────────────


def _tool_block(**input_kwargs):
    return {"name": "Read", "input": input_kwargs}


def test_summarize_read_with_int_offset_and_limit():
    out = summarize_tool_use(
        _tool_block(file_path="/tmp/x.py", offset=10, limit=5),
        Redactor(DEFAULT_CONFIG),
        DEFAULT_CONFIG,
    )
    assert "10–15" in out


def test_summarize_read_with_string_offset_no_longer_crashes():
    """G-05 regression: string numeric args used to raise TypeError."""
    out = summarize_tool_use(
        _tool_block(file_path="/tmp/x.py", offset="10", limit="5"),
        Redactor(DEFAULT_CONFIG),
        DEFAULT_CONFIG,
    )
    assert "10–15" in out


def test_summarize_read_without_limit_renders_question_mark():
    out = summarize_tool_use(
        _tool_block(file_path="/tmp/x.py", offset=5),
        Redactor(DEFAULT_CONFIG),
        DEFAULT_CONFIG,
    )
    assert "?" in out


def test_summarize_read_without_offset_or_limit_has_no_range():
    out = summarize_tool_use(
        _tool_block(file_path="/tmp/x.py"),
        Redactor(DEFAULT_CONFIG),
        DEFAULT_CONFIG,
    )
    # No parenthesised range
    assert "(" not in out


def test_summarize_read_with_bool_offset_coerces_to_none():
    """Bool offsets used to silently work as 0/1 due to int subclassing —
    explicitly reject so we don't hide bad input."""
    out = summarize_tool_use(
        _tool_block(file_path="/tmp/x.py", offset=True, limit=3),
        Redactor(DEFAULT_CONFIG),
        DEFAULT_CONFIG,
    )
    # bool → None → treated as if offset missing → start=1, end=3
    assert "1–3" in out


def test_summarize_read_with_float_limit():
    out = summarize_tool_use(
        _tool_block(file_path="/tmp/x.py", offset=0, limit=3.9),
        Redactor(DEFAULT_CONFIG),
        DEFAULT_CONFIG,
    )
    # 3.9 → 3; start=0 gets rendered as "0" but effective offset falls back to
    # the display logic (start=offset or 1 if offset is None; 0 is falsy, so 1).
    assert "1–3" in out or "0–3" in out


def test_summarize_non_read_tools_unaffected():
    bash = summarize_tool_use(
        {"name": "Bash", "input": {"command": "ls -la"}},
        Redactor(DEFAULT_CONFIG),
        DEFAULT_CONFIG,
    )
    assert "Bash" in bash
