"""Tests for `llmwiki.viz_tools` — tool-calling bar chart (v0.8 · #65)."""

from __future__ import annotations

import re

import pytest

from llmwiki.viz_tools import (
    _category_for,
    _TOOL_CATEGORIES,
    _CATEGORY_PALETTE,
    aggregate_tool_counts,
    parse_tool_counts,
    render_project_tool_chart,
    render_session_tool_chart,
    render_tool_chart,
)


# ─── parse_tool_counts handles all the shapes converter/parser produce ───


def test_parse_tool_counts_from_json_string():
    """frontmatter parser stores `tool_counts: {"Bash": 5}` as a string."""
    meta = {"tool_counts": '{"Bash": 5, "Read": 2}'}
    assert parse_tool_counts(meta) == {"Bash": 5, "Read": 2}


def test_parse_tool_counts_from_dict_directly():
    """Tests + programmatic callers may pass a dict directly."""
    meta = {"tool_counts": {"Bash": 5, "Read": 2}}
    assert parse_tool_counts(meta) == {"Bash": 5, "Read": 2}


def test_parse_tool_counts_empty_returns_empty_dict():
    for value in ("", "{}", None, {}):
        assert parse_tool_counts({"tool_counts": value}) == {}


def test_parse_tool_counts_missing_key_returns_empty_dict():
    assert parse_tool_counts({}) == {}


def test_parse_tool_counts_malformed_json_returns_empty_dict():
    assert parse_tool_counts({"tool_counts": "{bad json"}) == {}


def test_parse_tool_counts_skips_non_numeric_values():
    meta = {"tool_counts": '{"Bash": 5, "Read": "not a number"}'}
    assert parse_tool_counts(meta) == {"Bash": 5}


# ─── aggregate_tool_counts sums across sessions ─────────────────────────


def test_aggregate_tool_counts_sums_across_sessions():
    metas = [
        {"tool_counts": '{"Bash": 3, "Read": 5}'},
        {"tool_counts": '{"Bash": 1, "Edit": 2}'},
        {"tool_counts": '{}'},
        {"tool_counts": None},
    ]
    out = aggregate_tool_counts(metas)
    assert out == {"Bash": 4, "Read": 5, "Edit": 2}


def test_aggregate_tool_counts_ignores_zero_counts():
    metas = [{"tool_counts": '{"Bash": 0, "Read": 3}'}]
    assert aggregate_tool_counts(metas) == {"Read": 3}


# ─── category mapping covers the standard ECC + mcp tools ───────────────


@pytest.mark.parametrize(
    "name,expected",
    [
        ("Read", "io"),
        ("Write", "io"),
        ("Edit", "io"),
        ("Grep", "search"),
        ("Glob", "search"),
        ("WebSearch", "search"),
        ("Bash", "exec"),
        ("TaskOutput", "exec"),
        ("Skill", "exec"),
        ("WebFetch", "network"),
        ("mcp__Claude_Preview__preview_start", "network"),
        ("mcp__computer-use__screenshot", "network"),
        ("Agent", "plan"),
        ("TodoWrite", "plan"),
        ("ExitPlanMode", "plan"),
        ("SomeUnknownTool", "other"),
    ],
)
def test_category_for(name, expected):
    assert _category_for(name) == expected


def test_palette_covers_every_category():
    """Every category defined in _TOOL_CATEGORIES must have a palette
    entry, plus the catch-all 'other'. Missing entries would break render."""
    categories = {cat for cat, _ in _TOOL_CATEGORIES}
    categories.add("other")
    assert set(_CATEGORY_PALETTE.keys()) == categories


# ─── render_tool_chart: SVG structure + overflow collapse ───────────────


def test_render_tool_chart_empty_input_returns_empty_string():
    assert render_tool_chart({}) == ""
    assert render_tool_chart({"Bash": 0}) == ""


def test_render_tool_chart_emits_svg_root():
    svg = render_tool_chart({"Bash": 5, "Read": 3})
    assert svg.startswith('<svg')
    assert 'role="img"' in svg
    assert svg.rstrip().endswith('</svg>')


def test_render_tool_chart_sort_descending():
    svg = render_tool_chart({"Bash": 1, "Read": 9, "Edit": 5})
    # Extract label order from the SVG
    labels = re.findall(r'<text class="label-text"[^>]*>([^<]+)</text>', svg)
    assert labels == ["Read", "Edit", "Bash"]


def test_render_tool_chart_overflow_collapses_into_other_row():
    """max_bars=3 with 5 tools should produce 3 named bars + 1 'Other (2 tools)' row."""
    counts = {f"Tool{i}": 10 - i for i in range(5)}
    svg = render_tool_chart(counts, max_bars=3)
    labels = re.findall(r'<text class="label-text"[^>]*>([^<]+)</text>', svg)
    assert labels == ["Tool0", "Tool1", "Tool2", "Other (2 tools)"]


def test_render_tool_chart_no_overflow_row_when_exact():
    counts = {f"Tool{i}": 10 - i for i in range(3)}
    svg = render_tool_chart(counts, max_bars=3)
    assert "Other (" not in svg


def test_render_tool_chart_tooltip_has_percentage():
    """Every bar's `<title>` shows count and percentage of the session total."""
    svg = render_tool_chart({"Bash": 3, "Read": 1})
    assert "Bash: 3 calls (75.0%)" in svg
    assert "Read: 1 call (25.0%)" in svg  # singular


def test_render_tool_chart_assigns_category_classes():
    svg = render_tool_chart({"Bash": 5, "Read": 3, "mcp__foo": 2})
    assert 'class="cat-exec"' in svg  # Bash
    assert 'class="cat-io"' in svg    # Read
    assert 'class="cat-network"' in svg  # mcp__foo


def test_render_tool_chart_long_names_are_shortened():
    long_name = "mcp__Claude_in_Chrome__tabs_context_mcp_with_extra_suffix"
    svg = render_tool_chart({long_name: 1})
    # The full name should appear in the tooltip, but the label-text
    # should be shortened.
    assert long_name in svg  # in tooltip
    labels = re.findall(r'<text class="label-text"[^>]*>([^<]+)</text>', svg)
    assert len(labels) == 1
    assert "…" in labels[0]
    assert len(labels[0]) <= 28


def test_render_tool_chart_bar_width_scales_to_max():
    """The largest bar should hit BAR_MAX_WIDTH (300), and a bar at half
    the count should be roughly half width."""
    svg = render_tool_chart({"Big": 100, "Small": 50})
    rects = re.findall(r'<rect class="cat-[^"]+" x="\d+" y="\d+" width="(\d+)"', svg)
    assert rects, "expected at least one <rect>"
    widths = sorted(int(w) for w in rects)
    assert widths[-1] == 300
    assert 140 <= widths[0] <= 160  # ~half of 300, allowing rounding


def test_render_tool_chart_escapes_tool_names():
    svg = render_tool_chart({"<script>": 1})
    assert "<script>" not in svg.replace('<script class', 'XX')
    assert "&lt;script&gt;" in svg


# ─── convenience wrappers ────────────────────────────────────────────────


def test_render_session_tool_chart_uses_meta_tool_counts():
    meta = {"tool_counts": '{"Bash": 2, "Edit": 1}'}
    svg = render_session_tool_chart(meta)
    assert '<svg' in svg
    assert "Bash" in svg
    assert "Edit" in svg


def test_render_session_tool_chart_empty_returns_empty():
    assert render_session_tool_chart({}) == ""
    assert render_session_tool_chart({"tool_counts": "{}"}) == ""


def test_render_project_tool_chart_sums_child_sessions():
    metas = [
        {"tool_counts": '{"Bash": 3}'},
        {"tool_counts": '{"Bash": 2, "Read": 5}'},
    ]
    svg = render_project_tool_chart(metas, "demo-proj")
    assert "Tool calls across all demo-proj sessions" in svg
    # After aggregation, Read (5) > Bash (5) tie → stable sort keeps Bash first
    # (it was seen first and counts are equal). Either order is acceptable —
    # we just check both appear.
    assert "Bash" in svg
    assert "Read" in svg
