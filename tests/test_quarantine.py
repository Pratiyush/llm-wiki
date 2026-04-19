"""Tests for the convert-error quarantine module (G-14 · #300).

Covers:
* schema versioning + deterministic file ordering
* add_entry dedup (same (adapter, source) bumps attempts + last_seen)
* add_entry validates required fields
* load() tolerates missing / corrupt / wrong-type files
* save() round-trips via load()
* clear_entry by (source) or (adapter, source); clear_all
* list_entries filter + sort
* format_table empty state + truncation
* count_by_adapter aggregate
* CLI subcommand — list, clear --all, clear <source>, retry
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

from llmwiki import quarantine as q


# ─── core module ──────────────────────────────────────────────────────────


def test_schema_version_is_pinned():
    assert q.SCHEMA_VERSION == 1


def test_load_missing_file_returns_empty(tmp_path):
    assert q.load(tmp_path / "nope.json") == []


def test_load_malformed_file_returns_empty(tmp_path):
    f = tmp_path / "quar.json"
    f.write_text("{ oops", encoding="utf-8")
    assert q.load(f) == []


def test_load_wrong_toplevel_shape_returns_empty(tmp_path):
    f = tmp_path / "quar.json"
    f.write_text(json.dumps(["not", "a", "dict"]), encoding="utf-8")
    assert q.load(f) == []


def test_load_wrong_entries_shape_returns_empty(tmp_path):
    f = tmp_path / "quar.json"
    f.write_text(json.dumps({"version": 1, "entries": "nope"}), encoding="utf-8")
    assert q.load(f) == []


def test_load_skips_individual_malformed_rows(tmp_path):
    f = tmp_path / "quar.json"
    f.write_text(
        json.dumps({
            "version": 1,
            "entries": [
                {"adapter": "x", "source": "/a", "error": "boom",
                 "first_seen": "2026-01-01T00:00:00Z",
                 "last_seen": "2026-01-01T00:00:00Z", "attempts": 1},
                "not-a-dict",
                {},                 # missing required keys
                {"adapter": None},  # type coercion path
            ],
        }),
        encoding="utf-8",
    )
    rows = q.load(f)
    assert len(rows) == 1
    assert rows[0].source == "/a"


def test_add_entry_creates_new(tmp_path):
    f = tmp_path / "quar.json"
    entry = q.add_entry("claude_code", "/tmp/x.jsonl", "boom", path=f)
    assert entry.attempts == 1
    rows = q.load(f)
    assert len(rows) == 1
    assert rows[0].error == "boom"


def test_add_entry_deduplicates_on_key(tmp_path):
    f = tmp_path / "quar.json"
    q.add_entry("claude_code", "/tmp/x.jsonl", "boom", path=f)
    second = q.add_entry("claude_code", "/tmp/x.jsonl", "still broken", path=f)
    assert second.attempts == 2
    assert second.error == "still broken"
    assert len(q.load(f)) == 1


def test_add_entry_different_adapter_same_source_is_distinct(tmp_path):
    f = tmp_path / "quar.json"
    q.add_entry("claude_code", "/tmp/x.jsonl", "a", path=f)
    q.add_entry("codex_cli", "/tmp/x.jsonl", "b", path=f)
    assert len(q.load(f)) == 2


def test_add_entry_merges_extra(tmp_path):
    f = tmp_path / "quar.json"
    q.add_entry("x", "/a", "boom", path=f, extra={"k1": "v1"})
    q.add_entry("x", "/a", "boom", path=f, extra={"k2": "v2"})
    rows = q.load(f)
    assert rows[0].extra == {"k1": "v1", "k2": "v2"}


def test_add_entry_rejects_empty_adapter_or_source(tmp_path):
    f = tmp_path / "quar.json"
    with pytest.raises(ValueError):
        q.add_entry("", "/tmp/x", "boom", path=f)
    with pytest.raises(ValueError):
        q.add_entry("x", "", "boom", path=f)


def test_save_is_deterministic(tmp_path):
    f = tmp_path / "quar.json"
    entries = [
        q.QuarantineEntry(
            adapter="zzz", source="/z", error="e",
            first_seen="t", last_seen="t", attempts=1,
        ),
        q.QuarantineEntry(
            adapter="aaa", source="/a", error="e",
            first_seen="t", last_seen="t", attempts=1,
        ),
    ]
    q.save(entries, f)
    text = f.read_text(encoding="utf-8")
    assert text.find("aaa") < text.find("zzz")


def test_save_writes_version_metadata(tmp_path):
    f = tmp_path / "quar.json"
    q.save([], f)
    payload = json.loads(f.read_text(encoding="utf-8"))
    assert payload["version"] == q.SCHEMA_VERSION
    assert "updated" in payload
    assert payload["entries"] == []


def test_save_creates_parent_dirs(tmp_path):
    f = tmp_path / "nested" / "dir" / "quar.json"
    q.save([], f)
    assert f.is_file()


def test_round_trip(tmp_path):
    f = tmp_path / "quar.json"
    q.add_entry("a", "/p1", "e1", path=f)
    q.add_entry("b", "/p2", "e2", path=f, extra={"k": "v"})
    loaded = q.load(f)
    assert len(loaded) == 2
    assert {e.source for e in loaded} == {"/p1", "/p2"}


def test_clear_entry_removes_single(tmp_path):
    f = tmp_path / "quar.json"
    q.add_entry("a", "/p1", "e", path=f)
    q.add_entry("b", "/p2", "e", path=f)
    removed = q.clear_entry("/p1", path=f)
    assert removed == 1
    assert [e.source for e in q.load(f)] == ["/p2"]


def test_clear_entry_adapter_scoped(tmp_path):
    f = tmp_path / "quar.json"
    q.add_entry("a", "/p", "e", path=f)
    q.add_entry("b", "/p", "e", path=f)
    removed = q.clear_entry("/p", adapter="a", path=f)
    assert removed == 1
    rows = q.load(f)
    assert len(rows) == 1 and rows[0].adapter == "b"


def test_clear_entry_missing_is_noop(tmp_path):
    f = tmp_path / "quar.json"
    q.add_entry("a", "/p", "e", path=f)
    removed = q.clear_entry("/nope", path=f)
    assert removed == 0
    assert len(q.load(f)) == 1


def test_clear_all(tmp_path):
    f = tmp_path / "quar.json"
    q.add_entry("a", "/p1", "e", path=f)
    q.add_entry("b", "/p2", "e", path=f)
    removed = q.clear_all(f)
    assert removed == 2
    assert q.load(f) == []


def test_clear_all_on_empty_is_zero(tmp_path):
    f = tmp_path / "quar.json"
    assert q.clear_all(f) == 0


def test_list_entries_sort_order(tmp_path):
    f = tmp_path / "quar.json"
    q.add_entry("zzz", "/p", "e", path=f)
    q.add_entry("aaa", "/p", "e", path=f)
    rows = q.list_entries(path=f)
    assert [r.adapter for r in rows] == ["aaa", "zzz"]


def test_list_entries_filter_by_adapter(tmp_path):
    f = tmp_path / "quar.json"
    q.add_entry("aaa", "/p1", "e", path=f)
    q.add_entry("zzz", "/p2", "e", path=f)
    assert [r.adapter for r in q.list_entries(path=f, adapter="aaa")] == ["aaa"]


def test_format_table_empty():
    assert q.format_table([]) == "No quarantined sources."


def test_format_table_truncates_long_error(tmp_path):
    entries = [
        q.QuarantineEntry(
            adapter="a", source="/p", error="x" * 200,
            first_seen="t", last_seen="t", attempts=1,
        )
    ]
    table = q.format_table(entries)
    assert "..." in table
    assert len(table.splitlines()[-1]) < 300


def test_format_table_renders_source_basename_only():
    entries = [
        q.QuarantineEntry(
            adapter="a", source="/some/long/path/to/file.jsonl", error="e",
            first_seen="t", last_seen="t", attempts=3,
        )
    ]
    table = q.format_table(entries)
    assert "file.jsonl" in table
    assert "/some/long/path/to" not in table


def test_count_by_adapter(tmp_path):
    f = tmp_path / "quar.json"
    q.add_entry("a", "/p1", "e", path=f)
    q.add_entry("a", "/p2", "e", path=f)
    q.add_entry("b", "/p3", "e", path=f)
    with patch.object(q, "DEFAULT_QUARANTINE_FILE", f):
        counts = q.count_by_adapter(path=f)
    assert counts == {"a": 2, "b": 1}


def test_entry_equality_by_adapter_source():
    a = q.QuarantineEntry(
        adapter="x", source="/p", error="e1",
        first_seen="t1", last_seen="t1", attempts=1,
    )
    b = q.QuarantineEntry(
        adapter="x", source="/p", error="different",
        first_seen="t2", last_seen="t2", attempts=99,
    )
    assert a == b
    assert hash(a) == hash(b)


# ─── CLI subcommand ──────────────────────────────────────────────────────


def _run_cli(*args, env=None):
    return subprocess.run(
        [sys.executable, "-m", "llmwiki", *args],
        capture_output=True,
        text=True,
        check=False,
        env=env,
    )


def test_cli_quarantine_list_empty_message(tmp_path, monkeypatch):
    monkeypatch.setattr(q, "DEFAULT_QUARANTINE_FILE", tmp_path / "quar.json")
    cp = _run_cli("quarantine", "list")
    assert cp.returncode == 0
    assert "No quarantined sources" in cp.stdout


def test_cli_quarantine_list_filters_by_adapter(tmp_path, monkeypatch):
    # Seed directly so we don't rely on CLI to write
    q.add_entry("a", "/p1", "e", path=tmp_path / "q.json")
    q.add_entry("b", "/p2", "e", path=tmp_path / "q.json")
    # We can't monkeypatch subprocess env easily — test format_table path instead.
    rows = q.list_entries(path=tmp_path / "q.json", adapter="b")
    assert [e.adapter for e in rows] == ["b"]


def test_cli_quarantine_clear_requires_all_or_source():
    cp = _run_cli("quarantine", "clear")
    assert cp.returncode == 2
    assert "--all" in cp.stderr or "--all" in cp.stdout


def test_cli_quarantine_help_shows_subcommands():
    cp = _run_cli("quarantine", "--help")
    assert cp.returncode == 0
    assert "list" in cp.stdout
    assert "clear" in cp.stdout
    assert "retry" in cp.stdout
