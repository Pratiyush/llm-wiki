"""Tests for `llmwiki.changelog_timeline` — append-only page changelog (v0.7 · #56)."""

from __future__ import annotations

from datetime import date

import pytest

from llmwiki.changelog_timeline import (
    extract_price_points,
    find_recently_updated,
    parse_changelog,
    render_changelog_timeline,
    render_price_sparkline,
    render_recently_updated,
)


# ─── parse_changelog ─────────────────────────────────────────────────────


def test_parse_changelog_empty_returns_empty():
    assert parse_changelog({}) == ([], [])
    assert parse_changelog({"changelog": None}) == ([], [])
    assert parse_changelog({"changelog": ""}) == ([], [])


def test_parse_changelog_from_json_string():
    meta = {
        "changelog": (
            '[{"date": "2026-01-15", "event": "Price cut", '
            '"field": "pricing.input_per_1m", "from": 4.0, "to": 3.0}]'
        )
    }
    entries, warnings = parse_changelog(meta)
    assert warnings == []
    assert len(entries) == 1
    assert entries[0]["date"] == "2026-01-15"
    assert entries[0]["event"] == "Price cut"
    assert entries[0]["field"] == "pricing.input_per_1m"
    assert entries[0]["from_value"] == 4.0
    assert entries[0]["to_value"] == 3.0


def test_parse_changelog_from_list():
    meta = {
        "changelog": [
            {"date": "2026-02-01", "event": "Benchmark refresh"},
        ]
    }
    entries, warnings = parse_changelog(meta)
    assert warnings == []
    assert entries[0]["event"] == "Benchmark refresh"


def test_parse_changelog_sorts_ascending():
    meta = {
        "changelog": [
            {"date": "2026-02-01", "event": "Second"},
            {"date": "2026-01-15", "event": "First"},
        ]
    }
    entries, _ = parse_changelog(meta)
    assert [e["event"] for e in entries] == ["First", "Second"]


def test_parse_changelog_drops_entries_without_date():
    meta = {
        "changelog": [
            {"event": "Missing date"},
            {"date": "2026-01-15", "event": "OK"},
        ]
    }
    entries, warnings = parse_changelog(meta)
    assert len(entries) == 1
    assert entries[0]["event"] == "OK"
    assert any("missing required field: date" in w for w in warnings)


def test_parse_changelog_drops_entries_without_event():
    meta = {
        "changelog": [
            {"date": "2026-01-15"},
            {"date": "2026-02-01", "event": "OK"},
        ]
    }
    entries, warnings = parse_changelog(meta)
    assert len(entries) == 1
    assert any("missing required field: event" in w for w in warnings)


def test_parse_changelog_invalid_date_dropped():
    meta = {
        "changelog": [{"date": "not a date", "event": "bad"}],
    }
    entries, warnings = parse_changelog(meta)
    assert entries == []
    assert any("not a valid ISO date" in w for w in warnings)


def test_parse_changelog_malformed_json_warns():
    entries, warnings = parse_changelog({"changelog": "{not a list"})
    assert entries == []
    assert any("JSON list" in w for w in warnings)


def test_parse_changelog_handles_frontmatter_parser_mangling():
    """The llmwiki lightweight frontmatter parser naively splits
    `[{"a":1, "b":2}, {"c":3}]` on commas, producing a list of strings
    like `['{"a":1', '"b":2}', '{"c":3}']`. `parse_changelog` must
    stitch these back together before validating, otherwise every real
    entity page with a multi-entry changelog would drop every entry.
    This is the #56 bug that bit us on first integration — regression
    locked in here."""
    meta = {
        "changelog": [
            '{"date": "2026-03-18"',
            '"event": "Launched"',
            '"field": "pricing.input_per_1m"',
            '"from": null',
            '"to": 4.00}',
            '{"date": "2026-04-02"',
            '"event": "Price cut"',
            '"field": "pricing.input_per_1m"',
            '"from": 4.00',
            '"to": 3.00}',
        ]
    }
    entries, warnings = parse_changelog(meta)
    assert warnings == []
    assert len(entries) == 2
    assert entries[0]["event"] == "Launched"
    assert entries[1]["event"] == "Price cut"
    assert entries[1]["to_value"] == 3.0


# ─── render_changelog_timeline ──────────────────────────────────────────


def test_render_timeline_empty_returns_empty():
    assert render_changelog_timeline([]) == ""


def test_render_timeline_shows_newest_first():
    entries = [
        {"date": "2026-01-15", "event": "Old change"},
        {"date": "2026-02-01", "event": "New change"},
    ]
    html_out = render_changelog_timeline(entries)
    new_pos = html_out.find("New change")
    old_pos = html_out.find("Old change")
    assert new_pos != -1 and old_pos != -1
    assert new_pos < old_pos, "newest entry must render before older entries"


def test_render_timeline_includes_field_path_when_present():
    entries = [{"date": "2026-01-15", "event": "x", "field": "pricing.input_per_1m"}]
    html_out = render_changelog_timeline(entries)
    assert "pricing.input_per_1m" in html_out
    assert '<code class="timeline-field">' in html_out


def test_render_timeline_numeric_delta_has_arrow_direction():
    entries = [
        {
            "date": "2026-01-15",
            "event": "Price cut",
            "field": "pricing.input_per_1m",
            "from_value": 4.0,
            "to_value": 3.0,
        },
    ]
    html_out = render_changelog_timeline(entries)
    assert "timeline-arrow-down" in html_out
    assert "timeline-arrow-up" not in html_out


def test_render_timeline_string_delta_no_arrow_direction():
    entries = [
        {
            "date": "2026-01-15",
            "event": "License changed",
            "field": "model.license",
            "from_value": "proprietary",
            "to_value": "apache-2.0",
        },
    ]
    html_out = render_changelog_timeline(entries)
    assert "proprietary" in html_out
    assert "apache-2.0" in html_out
    assert "timeline-arrow-up" not in html_out
    assert "timeline-arrow-down" not in html_out


def test_render_timeline_escapes_html():
    entries = [{"date": "2026-01-15", "event": "<script>alert(1)</script>"}]
    html_out = render_changelog_timeline(entries)
    assert "<script>alert" not in html_out
    assert "&lt;script&gt;" in html_out


# ─── extract_price_points ───────────────────────────────────────────────


def test_extract_price_points_filters_by_field_suffix():
    entries = [
        {"date": "2026-01-01", "event": "x",
         "field": "model.pricing.input_per_1m", "to_value": 3.0},
        {"date": "2026-02-01", "event": "x",
         "field": "model.pricing.output_per_1m", "to_value": 15.0},
        {"date": "2026-03-01", "event": "x",
         "field": "model.pricing.input_per_1m", "to_value": 2.5},
    ]
    pts = extract_price_points(entries, field_suffix="pricing.input_per_1m")
    assert pts == [(date(2026, 1, 1), 3.0), (date(2026, 3, 1), 2.5)]


def test_extract_price_points_ignores_non_numeric():
    entries = [
        {"date": "2026-01-01", "event": "x",
         "field": "pricing.input_per_1m", "to_value": "free tier"},
    ]
    assert extract_price_points(entries) == []


# ─── render_price_sparkline ─────────────────────────────────────────────


def test_sparkline_empty_returns_empty():
    assert render_price_sparkline([]) == ""


def test_sparkline_single_point_returns_empty():
    assert render_price_sparkline([(date(2026, 1, 1), 3.0)]) == ""


def test_sparkline_two_points_renders_svg():
    pts = [(date(2026, 1, 1), 4.0), (date(2026, 2, 1), 3.0)]
    svg = render_price_sparkline(pts)
    assert svg.startswith('<svg')
    assert 'class="price-sparkline"' in svg
    assert 'role="img"' in svg
    # Tooltip includes both endpoints
    assert "2026-01-01" in svg
    assert "2026-02-01" in svg
    assert "4.00" in svg
    assert "3.00" in svg


def test_sparkline_flat_series_renders_horizontal_line():
    pts = [(date(2026, 1, 1), 3.0), (date(2026, 2, 1), 3.0)]
    svg = render_price_sparkline(pts)
    # Should still render without dividing-by-zero
    assert svg.startswith('<svg')


# ─── find_recently_updated ──────────────────────────────────────────────


def test_find_recently_updated_returns_entries_within_window():
    pages = [
        ("Alpha", {"changelog": '[{"date": "2026-04-01", "event": "recent"}]'}),
        ("Beta", {"changelog": '[{"date": "2025-12-01", "event": "old"}]'}),
        ("Gamma", {"changelog": None}),
    ]
    out = find_recently_updated(pages, now=date(2026, 4, 9), within_days=30)
    assert len(out) == 1
    assert out[0][0] == "Alpha"


def test_find_recently_updated_sorted_by_latest_change_desc():
    pages = [
        ("Alpha", {"changelog": '[{"date": "2026-04-01", "event": "a"}]'}),
        ("Beta", {"changelog": '[{"date": "2026-04-05", "event": "b"}]'}),
        ("Gamma", {"changelog": '[{"date": "2026-04-07", "event": "g"}]'}),
    ]
    out = find_recently_updated(pages, now=date(2026, 4, 9), within_days=30)
    assert [slug for slug, _ in out] == ["Gamma", "Beta", "Alpha"]


def test_find_recently_updated_uses_latest_entry_not_first():
    """A page with entries from 2025 AND 2026 should surface via the
    2026 entry if it's within the window."""
    pages = [
        ("Alpha", {
            "changelog": (
                '[{"date": "2025-10-01", "event": "old"},'
                ' {"date": "2026-04-05", "event": "new"}]'
            )
        }),
    ]
    out = find_recently_updated(pages, now=date(2026, 4, 9), within_days=30)
    assert len(out) == 1
    assert out[0][1]["event"] == "new"


# ─── render_recently_updated ────────────────────────────────────────────


def test_render_recently_updated_empty():
    assert render_recently_updated([]) == ""


def test_render_recently_updated_list():
    items = [
        ("Alpha", {"date": "2026-04-05", "event": "Price cut"}),
        ("Beta", {"date": "2026-04-01", "event": "Context expanded"}),
    ]
    out = render_recently_updated(items)
    assert "Alpha" in out
    assert "Beta" in out
    assert "Price cut" in out
    assert 'href="models/Alpha.html"' in out
    assert 'href="models/Beta.html"' in out


def test_render_recently_updated_respects_link_prefix():
    items = [("X", {"date": "2026-04-05", "event": "x"})]
    out = render_recently_updated(items, link_prefix="../entities/")
    assert 'href="../entities/X.html"' in out
