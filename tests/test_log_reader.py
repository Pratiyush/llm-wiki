"""Tests for llmwiki.log_reader (G-18 · #304).

Exercises parse_log / recent_events against synthetic log.md fixtures
covering the happy path, malformed entries, operation filters, and
empty/missing inputs.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path

from llmwiki.log_reader import LogEvent, parse_log, recent_events


SAMPLE_LOG = """# Wiki Log

## [2026-04-19] synthesize | 3 sessions across 2 projects
- Processed: 3
- Created: proj-a, proj-b
- Errors: 0

## [2026-04-18] lint | auto-check
- Processed: 714
- Errors: 0

## [2026-04-18] sync | pull from adapters
- Processed: 12

not-a-heading line
- stray bullet with no parent heading

## [bad-date] synthesize | ignored
- Processed: 99
"""


def test_parse_log_extracts_structured_events(tmp_path: Path):
    log = tmp_path / "log.md"
    log.write_text(SAMPLE_LOG, encoding="utf-8")
    events = parse_log(log)
    # 3 valid headings; the bad-date one is skipped.
    assert len(events) == 3
    assert events[0].date == date(2026, 4, 19)
    assert events[0].operation == "synthesize"
    assert events[0].title == "3 sessions across 2 projects"
    assert events[0].details == {
        "Processed": "3",
        "Created": "proj-a, proj-b",
        "Errors": "0",
    }


def test_parse_log_missing_file_returns_empty(tmp_path: Path):
    assert parse_log(tmp_path / "nope.md") == []


def test_parse_log_empty_file_returns_empty(tmp_path: Path):
    log = tmp_path / "log.md"
    log.write_text("", encoding="utf-8")
    assert parse_log(log) == []


def test_recent_events_returns_newest_first(tmp_path: Path):
    log = tmp_path / "log.md"
    log.write_text(SAMPLE_LOG, encoding="utf-8")
    events = recent_events(log, limit=2)
    # Newest first (2026-04-19 before 2026-04-18)
    assert [e.date for e in events] == [
        date(2026, 4, 19),
        date(2026, 4, 18),
    ]


def test_recent_events_filter_by_operation(tmp_path: Path):
    log = tmp_path / "log.md"
    log.write_text(SAMPLE_LOG, encoding="utf-8")
    events = recent_events(log, limit=10, operations={"lint"})
    assert len(events) == 1
    assert events[0].operation == "lint"


def test_recent_events_limit_clamps_size(tmp_path: Path):
    log = tmp_path / "log.md"
    log.write_text(SAMPLE_LOG, encoding="utf-8")
    events = recent_events(log, limit=1)
    assert len(events) == 1
    assert events[0].date == date(2026, 4, 19)


def test_log_event_summary_uses_processed_when_present():
    ev = LogEvent(
        date=date(2026, 4, 19),
        operation="synthesize",
        title="batch",
        details={"Processed": "5"},
    )
    assert ev.summary() == "synthesize: 5 processed"


def test_log_event_summary_falls_back_to_title():
    ev = LogEvent(
        date=date(2026, 4, 19),
        operation="sync",
        title="pull from adapters",
        details={},
    )
    assert ev.summary() == "sync: pull from adapters"
