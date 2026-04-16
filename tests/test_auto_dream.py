"""Tests for Auto Dream MEMORY.md consolidation (v1.0, #156)."""

from __future__ import annotations

from datetime import datetime, timezone, timedelta
from pathlib import Path

import pytest

from llmwiki.auto_dream import (
    should_dream,
    dream,
    resolve_relative_dates,
    find_outdated_markers,
    enforce_line_cap,
    MAX_MEMORY_LINES,
    MIN_SESSIONS_SINCE_LAST,
    MIN_HOURS_SINCE_LAST,
)


# ─── should_dream trigger ─────────────────────────────────────────────


def test_first_run_triggers_with_enough_sessions(tmp_path: Path):
    sf = tmp_path / "state.json"
    assert should_dream(session_count=10, state_file=sf) is True


def test_first_run_no_trigger_below_threshold(tmp_path: Path):
    sf = tmp_path / "state.json"
    assert should_dream(session_count=2, state_file=sf) is False


def test_requires_both_thresholds(tmp_path: Path):
    sf = tmp_path / "state.json"
    # Set state: last dream 1 hour ago, 100 sessions
    sf.write_text(
        '{"last_dream_at": "2026-04-16T08:00:00+00:00", "last_session_count": 100}',
        encoding="utf-8",
    )
    now = datetime(2026, 4, 16, 9, 0, tzinfo=timezone.utc)  # 1 hour later
    # 10 new sessions but only 1 hour — no dream
    assert should_dream(session_count=110, now=now, state_file=sf) is False


def test_triggers_when_both_thresholds_met(tmp_path: Path):
    sf = tmp_path / "state.json"
    sf.write_text(
        '{"last_dream_at": "2026-04-15T08:00:00+00:00", "last_session_count": 100}',
        encoding="utf-8",
    )
    now = datetime(2026, 4, 16, 9, 0, tzinfo=timezone.utc)  # 25h later
    # 25h + 10 new sessions → dream
    assert should_dream(session_count=110, now=now, state_file=sf) is True


def test_no_trigger_with_few_new_sessions(tmp_path: Path):
    sf = tmp_path / "state.json"
    sf.write_text(
        '{"last_dream_at": "2026-04-10T08:00:00+00:00", "last_session_count": 100}',
        encoding="utf-8",
    )
    now = datetime(2026, 4, 16, 9, 0, tzinfo=timezone.utc)  # many days later
    # Many hours but only 2 new sessions → no dream
    assert should_dream(session_count=102, now=now, state_file=sf) is False


def test_corrupt_state_triggers_dream(tmp_path: Path):
    sf = tmp_path / "state.json"
    sf.write_text("NOT JSON", encoding="utf-8")
    assert should_dream(session_count=10, state_file=sf) is True


# ─── Relative date resolution ─────────────────────────────────────────


def test_today_replaced():
    text = "Meeting is today at 3pm"
    now = datetime(2026, 4, 16, tzinfo=timezone.utc)
    result, count = resolve_relative_dates(text, now=now)
    assert "2026-04-16" in result
    assert count == 1


def test_today_case_insensitive():
    text = "TODAY was productive. Today's wins: foo."
    now = datetime(2026, 4, 16, tzinfo=timezone.utc)
    result, count = resolve_relative_dates(text, now=now)
    assert count == 2


def test_no_relative_dates():
    text = "Meeting is on 2026-04-20"
    result, count = resolve_relative_dates(text)
    assert count == 0
    assert result == text


def test_empty_text():
    result, count = resolve_relative_dates("")
    assert result == ""
    assert count == 0


# ─── Outdated markers ────────────────────────────────────────────────


def test_find_superseded():
    text = "- This is the old setup [SUPERSEDED]\n- Still relevant\n"
    outdated = find_outdated_markers(text)
    assert len(outdated) == 1


def test_find_all_markers():
    text = "a SUPERSEDED\nb OUTDATED\nc DEPRECATED\nd normal\n"
    outdated = find_outdated_markers(text)
    assert len(outdated) == 3


def test_no_outdated_markers():
    text = "Nothing outdated here\njust normal content\n"
    assert find_outdated_markers(text) == []


# ─── Line-cap enforcement ────────────────────────────────────────────


def test_no_cap_when_under_limit():
    text = "# Header\n" + "\n".join(f"line {i}" for i in range(50))
    result, removed = enforce_line_cap(text, max_lines=200)
    assert removed == 0
    assert result == text


def test_cap_drops_oldest():
    lines = ["# Header", "", "## Section"]
    # Add 300 body lines
    lines.extend(f"line {i}" for i in range(300))
    text = "\n".join(lines)

    result, removed = enforce_line_cap(text, max_lines=100)
    result_lines = result.splitlines()
    assert len(result_lines) <= 100
    assert removed > 0
    # Header preserved
    assert result_lines[0] == "# Header"


def test_cap_preserves_newest():
    lines = ["# Header", "## Section"]
    lines.extend(f"line {i}" for i in range(500))
    text = "\n".join(lines)

    result, _ = enforce_line_cap(text, max_lines=50)
    # The newest line (highest number) should be preserved
    assert "line 499" in result


def test_cap_handles_oversized_header():
    """If header alone exceeds max_lines, return as-is."""
    lines = [f"header line {i}" for i in range(300)]  # no ## heading
    text = "\n".join(lines)
    result, removed = enforce_line_cap(text, max_lines=100)
    # No ## heading means header_end=0, body is all lines
    # Budget = 100 - 0 = 100, kept = last 100
    assert len(result.splitlines()) <= 100


# ─── dream() full consolidation ──────────────────────────────────────


def test_dream_missing_file(tmp_path: Path):
    mf = tmp_path / "nonexistent.md"
    sf = tmp_path / "state.json"
    result = dream(memory_file=mf, state_file=sf)
    assert result["new_size"] == 0


def test_dream_basic_consolidation(tmp_path: Path):
    mf = tmp_path / "MEMORY.md"
    mf.write_text(
        "# MEMORY\n\n"
        "## User\n"
        "- Meeting today at 3pm\n"
        "- Old setup SUPERSEDED by new approach\n",
        encoding="utf-8",
    )
    sf = tmp_path / "state.json"
    now = datetime(2026, 4, 16, tzinfo=timezone.utc)
    result = dream(memory_file=mf, state_file=sf, session_count=5, now=now)
    assert result["replaced"] >= 1  # "today" replaced
    assert result["outdated"] >= 1  # SUPERSEDED line found
    # State saved
    assert sf.is_file()


def test_dream_writes_state(tmp_path: Path):
    mf = tmp_path / "MEMORY.md"
    mf.write_text("# MEMORY\n", encoding="utf-8")
    sf = tmp_path / "state.json"
    now = datetime(2026, 4, 16, 10, 30, tzinfo=timezone.utc)
    dream(memory_file=mf, state_file=sf, session_count=42, now=now)

    import json
    state = json.loads(sf.read_text(encoding="utf-8"))
    assert state["last_session_count"] == 42
    assert "2026-04-16" in state["last_dream_at"]


def test_dream_enforces_cap(tmp_path: Path):
    mf = tmp_path / "MEMORY.md"
    content = "# MEMORY\n## User\n" + "\n".join(
        f"- line {i}" for i in range(500)
    )
    mf.write_text(content, encoding="utf-8")
    sf = tmp_path / "state.json"
    result = dream(memory_file=mf, state_file=sf)
    assert result["removed"] > 0
    # File should now be under cap
    new_content = mf.read_text(encoding="utf-8")
    assert len(new_content.splitlines()) <= MAX_MEMORY_LINES


# ─── Constants ───────────────────────────────────────────────────────


def test_threshold_constants():
    assert MIN_SESSIONS_SINCE_LAST == 5
    assert MIN_HOURS_SINCE_LAST == 24
    assert MAX_MEMORY_LINES == 200
