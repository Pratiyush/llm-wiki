"""Tests for llmwiki.freshness — content-freshness badges (#57)."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from llmwiki.freshness import (
    DEFAULT_GREEN_DAYS,
    DEFAULT_YELLOW_DAYS,
    format_relative_time,
    freshness_badge,
    freshness_class,
    load_freshness_config,
    parse_timestamp,
    resolve_last_updated,
)


# ─── parse_timestamp ─────────────────────────────────────────────────────


def test_parse_timestamp_iso_with_utc():
    dt = parse_timestamp("2026-04-07T21:45:13.703000+00:00")
    assert dt == datetime(2026, 4, 7, 21, 45, 13, 703000)
    assert dt.tzinfo is None  # normalised to naive UTC


def test_parse_timestamp_iso_with_z():
    dt = parse_timestamp("2026-04-07T12:00:00Z")
    assert dt == datetime(2026, 4, 7, 12, 0, 0)


def test_parse_timestamp_iso_with_offset_normalises_to_utc():
    # 10:00 in UTC+5 = 05:00 UTC
    dt = parse_timestamp("2026-04-07T10:00:00+05:00")
    assert dt == datetime(2026, 4, 7, 5, 0, 0)


def test_parse_timestamp_date_only():
    dt = parse_timestamp("2026-04-07")
    assert dt == datetime(2026, 4, 7)


def test_parse_timestamp_empty_returns_none():
    assert parse_timestamp("") is None
    assert parse_timestamp(None) is None
    assert parse_timestamp("   ") is None


def test_parse_timestamp_malformed_returns_none():
    assert parse_timestamp("not a date") is None
    assert parse_timestamp("2026-13-45") is None


# ─── resolve_last_updated ───────────────────────────────────────────────


def test_resolve_prefers_last_updated():
    meta = {
        "last_updated": "2026-04-07",
        "ended": "2026-04-01T00:00:00Z",
        "started": "2026-03-25T00:00:00Z",
        "date": "2026-03-20",
    }
    assert resolve_last_updated(meta) == datetime(2026, 4, 7)


def test_resolve_falls_back_to_ended_then_started():
    assert resolve_last_updated({"ended": "2026-04-07T10:00:00Z"}) == datetime(2026, 4, 7, 10, 0, 0)
    assert resolve_last_updated({"started": "2026-04-06T10:00:00Z"}) == datetime(2026, 4, 6, 10, 0, 0)
    assert resolve_last_updated({"date": "2026-04-05"}) == datetime(2026, 4, 5)


def test_resolve_no_fields_returns_none():
    assert resolve_last_updated({}) is None
    assert resolve_last_updated({"title": "Foo"}) is None


# ─── format_relative_time ────────────────────────────────────────────────


def test_format_relative_time_today_and_yesterday():
    assert format_relative_time(0) == "today"
    assert format_relative_time(1) == "yesterday"


def test_format_relative_time_days():
    assert format_relative_time(2) == "2 days ago"
    assert format_relative_time(13) == "13 days ago"


def test_format_relative_time_weeks():
    assert format_relative_time(14) == "2 weeks ago"
    assert format_relative_time(21) == "3 weeks ago"
    assert format_relative_time(59) == "8 weeks ago"


def test_format_relative_time_months():
    assert format_relative_time(60) == "2 months ago"
    assert format_relative_time(180) == "6 months ago"
    assert format_relative_time(364) == "12 months ago"


def test_format_relative_time_years():
    assert format_relative_time(365) == "1 year ago"
    assert format_relative_time(365 * 3) == "3 years ago"


def test_format_relative_time_negative_is_unknown():
    assert format_relative_time(-5) == "unknown"


# ─── freshness_class ────────────────────────────────────────────────────


def test_freshness_class_boundary_green():
    # Exact boundary (14) should still be green with defaults
    assert freshness_class(0) == "fresh-green"
    assert freshness_class(14) == "fresh-green"
    assert freshness_class(14, green_days=14, yellow_days=60) == "fresh-green"


def test_freshness_class_boundary_yellow():
    assert freshness_class(15) == "fresh-yellow"
    assert freshness_class(60) == "fresh-yellow"


def test_freshness_class_boundary_red():
    assert freshness_class(61) == "fresh-red"
    assert freshness_class(1000) == "fresh-red"


def test_freshness_class_none_or_negative_is_unknown():
    assert freshness_class(None) == "fresh-unknown"
    assert freshness_class(-1) == "fresh-unknown"
    assert freshness_class(-9999) == "fresh-unknown"  # clock skew / future


def test_freshness_class_custom_thresholds():
    assert freshness_class(7, green_days=7, yellow_days=30) == "fresh-green"
    assert freshness_class(8, green_days=7, yellow_days=30) == "fresh-yellow"
    assert freshness_class(31, green_days=7, yellow_days=30) == "fresh-red"


# ─── freshness_badge ────────────────────────────────────────────────────


def test_badge_with_recent_ended_is_green():
    now = datetime(2026, 4, 8, 12, 0, 0)
    meta = {"ended": "2026-04-07T12:00:00Z"}
    html_str = freshness_badge(meta, now=now)
    assert "fresh-green" in html_str
    assert "yesterday" in html_str
    assert "Last updated 2026-04-07" in html_str


def test_badge_with_30_day_old_ended_is_yellow():
    now = datetime(2026, 4, 8, 12, 0, 0)
    meta = {"ended": "2026-03-08T12:00:00Z"}  # ~31 days ago
    html_str = freshness_badge(meta, now=now)
    assert "fresh-yellow" in html_str


def test_badge_with_365_day_old_ended_is_red():
    now = datetime(2026, 4, 8, 12, 0, 0)
    meta = {"ended": "2025-04-08T12:00:00Z"}
    html_str = freshness_badge(meta, now=now)
    assert "fresh-red" in html_str
    assert "1 year ago" in html_str


def test_badge_future_date_is_unknown_due_to_clock_skew():
    now = datetime(2026, 4, 8, 12, 0, 0)
    meta = {"ended": "2026-04-15T12:00:00Z"}  # 7 days in the future
    html_str = freshness_badge(meta, now=now)
    assert "fresh-unknown" in html_str


def test_badge_no_timestamp_is_unknown():
    html_str = freshness_badge({})
    assert "fresh-unknown" in html_str
    assert "updated unknown" in html_str
    assert "No last-updated timestamp" in html_str


def test_badge_exact_boundary_green_to_yellow():
    # Exactly 14 days ago — still green
    now = datetime(2026, 4, 8, 12, 0, 0)
    meta = {"ended": (now - timedelta(days=14)).isoformat() + "Z"}
    html_str = freshness_badge(meta, now=now)
    assert "fresh-green" in html_str

    # 15 days ago — yellow
    meta = {"ended": (now - timedelta(days=15)).isoformat() + "Z"}
    html_str = freshness_badge(meta, now=now)
    assert "fresh-yellow" in html_str


def test_badge_exact_boundary_yellow_to_red():
    now = datetime(2026, 4, 8, 12, 0, 0)
    # 60 days ago — still yellow
    meta = {"ended": (now - timedelta(days=60)).isoformat() + "Z"}
    html_str = freshness_badge(meta, now=now)
    assert "fresh-yellow" in html_str

    # 61 days ago — red
    meta = {"ended": (now - timedelta(days=61)).isoformat() + "Z"}
    html_str = freshness_badge(meta, now=now)
    assert "fresh-red" in html_str


def test_badge_custom_thresholds_override():
    now = datetime(2026, 4, 8, 12, 0, 0)
    meta = {"ended": (now - timedelta(days=10)).isoformat() + "Z"}
    html_str = freshness_badge(meta, now=now, green_days=7, yellow_days=30)
    assert "fresh-yellow" in html_str  # 10 > 7, ≤ 30


def test_badge_html_is_wellformed():
    now = datetime(2026, 4, 8, 12, 0, 0)
    meta = {"ended": (now - timedelta(days=5)).isoformat() + "Z"}
    html_str = freshness_badge(meta, now=now)
    assert html_str.startswith('<span class="freshness')
    assert html_str.endswith("</span>")
    assert "title=" in html_str


# ─── load_freshness_config ──────────────────────────────────────────────


def test_load_freshness_config_defaults_when_missing(tmp_path):
    green, yellow = load_freshness_config(tmp_path)
    assert green == DEFAULT_GREEN_DAYS
    assert yellow == DEFAULT_YELLOW_DAYS


def test_load_freshness_config_reads_custom_thresholds(tmp_path):
    (tmp_path / "config.json").write_text(
        '{"freshness": {"green_days": 7, "yellow_days": 30}}', encoding="utf-8"
    )
    green, yellow = load_freshness_config(tmp_path)
    assert green == 7
    assert yellow == 30


def test_load_freshness_config_rejects_inverted_thresholds(tmp_path):
    # yellow < green is nonsense; should fall back to defaults
    (tmp_path / "config.json").write_text(
        '{"freshness": {"green_days": 60, "yellow_days": 14}}', encoding="utf-8"
    )
    green, yellow = load_freshness_config(tmp_path)
    assert green == DEFAULT_GREEN_DAYS
    assert yellow == DEFAULT_YELLOW_DAYS


def test_load_freshness_config_handles_bad_json(tmp_path):
    (tmp_path / "config.json").write_text("{ not json }", encoding="utf-8")
    green, yellow = load_freshness_config(tmp_path)
    assert green == DEFAULT_GREEN_DAYS
    assert yellow == DEFAULT_YELLOW_DAYS


def test_load_freshness_config_missing_section_keeps_defaults(tmp_path):
    (tmp_path / "config.json").write_text('{"redaction": {}}', encoding="utf-8")
    green, yellow = load_freshness_config(tmp_path)
    assert green == DEFAULT_GREEN_DAYS
    assert yellow == DEFAULT_YELLOW_DAYS
