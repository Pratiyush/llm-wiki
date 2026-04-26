"""Tests for #487 — parse_jsonl re-raises OSError so the caller can
quarantine the file instead of silently classifying it as 'filtered'.

Bug: ``try: … except OSError: pass`` at the top of parse_jsonl
swallowed every I/O failure, returned an empty list, and downstream
``convert_all`` then bucketed the file as 'filtered' (legitimate
empty session). The file disappeared from `llmwiki sync --status`
and from the quarantine, so operators never saw it.

Fix: parse_jsonl re-raises OSError; convert_all wraps the call in
its own try/except that routes through `_quarantine_add` + the
'errored' counter, matching every other I/O write path.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from llmwiki.convert import parse_jsonl


def test_oserror_now_propagates_to_caller(tmp_path: Path):
    """Reading from a path that doesn't exist must raise FileNotFoundError
    (an OSError subclass) — was silently swallowed before #487."""
    missing = tmp_path / "does-not-exist.jsonl"
    with pytest.raises(OSError):
        parse_jsonl(missing)


def test_oserror_on_permission_denied(tmp_path: Path):
    """On Unix, a chmod 000 file raises PermissionError (OSError subclass).
    Skip on Windows where chmod semantics differ."""
    import os
    if os.name == "nt":
        pytest.skip("chmod 000 doesn't simulate denial on Windows")
    p = tmp_path / "denied.jsonl"
    p.write_text('{"type": "user"}\n', encoding="utf-8")
    p.chmod(0o000)
    try:
        with pytest.raises(OSError):
            parse_jsonl(p)
    finally:
        # Restore so pytest's tmp_path cleanup can remove the file.
        p.chmod(0o644)


def test_jsondecodeerror_per_line_still_tolerated(tmp_path: Path):
    """Per-line JSON decode failures must NOT raise — just skip that line.
    JSONL allows partial / corrupt lines from a still-running session."""
    p = tmp_path / "mixed.jsonl"
    p.write_text(
        '{"type": "good", "id": 1}\n'
        'this is not json\n'
        '{"type": "good", "id": 2}\n',
        encoding="utf-8",
    )
    out = parse_jsonl(p)
    assert len(out) == 2
    assert out[0]["id"] == 1
    assert out[1]["id"] == 2


def test_non_dict_records_dropped(tmp_path: Path):
    """A scalar (number / string) on its own line is valid JSON but not
    a record — drop it (otherwise downstream filter_records crashes)."""
    p = tmp_path / "scalars.jsonl"
    p.write_text(
        '{"type": "good"}\n'
        '42\n'
        '"not-a-record"\n'
        '{"type": "another"}\n',
        encoding="utf-8",
    )
    out = parse_jsonl(p)
    assert len(out) == 2
    assert all(isinstance(r, dict) for r in out)


def test_empty_lines_skipped(tmp_path: Path):
    """Blank lines (common when a tool printed a trailing newline) are
    skipped without raising."""
    p = tmp_path / "blanks.jsonl"
    p.write_text(
        '\n\n{"type": "good"}\n\n{"type": "another"}\n\n',
        encoding="utf-8",
    )
    out = parse_jsonl(p)
    assert len(out) == 2
