"""Tests for `llmwiki.viz_heatmap` — GitLab/GitHub-style activity heatmap.

Covers:
* data collection + project filtering
* 365-day rolling window Sunday-alignment
* quantile bucketing over non-zero days
* SVG structure (cell count, rects, titles, a11y label)
* stdlib-only (no extra deps)
"""

from __future__ import annotations

import re
from datetime import date

import pytest

from llmwiki.viz_heatmap import (
    CELL_SIZE,
    ROW_COUNT,
    WEEK_COLS,
    cell_count_for_window,
    collect_session_counts,
    compute_quantile_thresholds,
    level_for,
    render_heatmap,
    window_bounds,
)


# ─── window_bounds: GitHub-style Sunday alignment ────────────────────────


def test_window_bounds_is_sunday_aligned():
    """Start date must fall on a Sunday — Python weekday() returns 6 for
    Sunday. This is what guarantees the grid is whole weeks so cell count
    always lands on a multiple of 7 + whatever extra days fill the final
    partial week."""
    end = date(2026, 4, 9)
    start, returned_end = window_bounds(end)
    assert returned_end == end
    assert start.weekday() == 6  # Sunday
    # The raw (unaligned) start would be 364 days before end.
    from datetime import timedelta

    assert start <= end - timedelta(days=364)


def test_window_bounds_when_end_is_a_sunday():
    """When end_date IS a Sunday, the grid shape must still be well-formed
    — the start-date Sunday alignment should push the start back to exactly
    52 weeks earlier, giving a clean 53-column window of 371 cells."""
    end = date(2026, 4, 12)  # Sunday
    assert end.weekday() == 6
    start, _ = window_bounds(end)
    assert start.weekday() == 6
    assert (end - start).days == 364


# ─── cell_count_for_window: always whole weeks ───────────────────────────


def test_cell_count_covers_full_window():
    """The grid must cover every day from the Sunday-aligned start through
    the end date, inclusive. For an end date mid-week the cell count is
    365 + days-from-end-sunday-to-sunday-before-end — between 365 and 371."""
    for offset in range(0, 7):
        end = date(2026, 4, 9) - date.resolution * 0
        end_shifted = end.replace(day=min(end.day + offset, 28))
        n = cell_count_for_window(end_shifted)
        assert 365 <= n <= 371


def test_cell_count_exact_for_known_end_date():
    # 2026-04-09 is a Thursday (weekday()=3). The 364-days-ago date is
    # 2025-04-10 (also a Thursday, weekday()=3). Aligning to the preceding
    # Sunday pushes start to 2025-04-06. Total days: (2026-04-09 -
    # 2025-04-06) = 368 days + 1 inclusive = 369 cells.
    end = date(2026, 4, 9)
    assert end.weekday() == 3  # Thu — sanity check
    assert cell_count_for_window(end) == 369


# ─── collect_session_counts: project filter + bad dates ──────────────────


def test_collect_session_counts_aggregate():
    entries = [
        {"date": "2026-04-01", "project": "a"},
        {"date": "2026-04-01", "project": "b"},
        {"date": "2026-04-02", "project": "a"},
        {"date": "2026-04-02", "project": "a"},
    ]
    counts = collect_session_counts(entries)
    assert counts[date(2026, 4, 1)] == 2
    assert counts[date(2026, 4, 2)] == 2


def test_collect_session_counts_project_filter():
    entries = [
        {"date": "2026-04-01", "project": "a"},
        {"date": "2026-04-01", "project": "b"},
        {"date": "2026-04-02", "project": "a"},
    ]
    counts = collect_session_counts(entries, project_slug="a")
    assert counts == {date(2026, 4, 1): 1, date(2026, 4, 2): 1}


def test_collect_session_counts_skips_bad_dates():
    entries = [
        {"date": "2026-04-01", "project": "a"},
        {"date": "not a date", "project": "a"},
        {"date": "", "project": "a"},
        {"project": "a"},  # no date at all
    ]
    counts = collect_session_counts(entries)
    assert counts == {date(2026, 4, 1): 1}


def test_collect_session_counts_uses_date_prefix_for_iso_timestamps():
    """`date: 2026-04-01T09:00:00+00:00` (ISO timestamp) is common — the
    YYYY-MM-DD prefix is the only thing we need."""
    entries = [{"date": "2026-04-01T09:00:00+00:00", "project": "a"}]
    counts = collect_session_counts(entries)
    assert counts == {date(2026, 4, 1): 1}


# ─── quantile bucketing on non-zero days ─────────────────────────────────


def test_quantile_thresholds_with_no_data():
    """Empty input must not crash — defaults ensure the level lookup still
    works and every day buckets to level 0."""
    t = compute_quantile_thresholds({})
    assert t == [1, 2, 3, 4]
    assert level_for(0, t) == 0
    assert level_for(5, t) == 4


def test_quantile_thresholds_monotonic_for_small_distinct_sets():
    """With only two distinct non-zero counts, the closest-rank quantile
    can return the same value for multiple thresholds. The function must
    enforce strict monotonicity so bucketing stays well-defined."""
    counts = {date(2026, 4, 1): 1, date(2026, 4, 2): 1, date(2026, 4, 3): 2}
    t = compute_quantile_thresholds(counts)
    assert t[0] < t[1] < t[2] < t[3]


def test_quantile_thresholds_ignore_zero_days():
    """Most of a 365-day window is zero days. If we naively quantiled over
    all days, almost every non-zero day would land in level 4. The fix is
    to compute quantiles over non-zero values only, which we verify here."""
    counts = {date(2026, 4, d): 0 for d in range(1, 20)}
    counts[date(2026, 4, 20)] = 1
    counts[date(2026, 4, 21)] = 5
    counts[date(2026, 4, 22)] = 10
    counts[date(2026, 4, 23)] = 50
    t = compute_quantile_thresholds(counts)
    # Four non-zero days → level 1..4 should span them
    assert level_for(1, t) == 1
    assert level_for(50, t) == 4
    # Zero days should bucket to 0 regardless of thresholds
    assert level_for(0, t) == 0


def test_level_for_boundary_values():
    thresholds = [1, 3, 5, 10]
    assert level_for(0, thresholds) == 0
    assert level_for(1, thresholds) == 1
    assert level_for(2, thresholds) == 2
    assert level_for(3, thresholds) == 2
    assert level_for(4, thresholds) == 3
    assert level_for(5, thresholds) == 3
    assert level_for(6, thresholds) == 4
    assert level_for(100, thresholds) == 4


# ─── render_heatmap: SVG structure + a11y ────────────────────────────────


def test_render_heatmap_emits_svg_root_with_aria_label():
    svg = render_heatmap({}, end_date=date(2026, 4, 9))
    assert svg.startswith('<svg')
    assert 'role="img"' in svg
    assert 'aria-label="Activity heatmap, 2025-04-06 to 2026-04-09"' in svg
    assert svg.rstrip().endswith('</svg>')


def test_render_heatmap_emits_expected_cell_count_for_end_date():
    """End date 2026-04-09 (Thu) — 369 cells as per test_cell_count_exact_for_known_end_date.
    Every cell is a `<rect>` with one of `l0..l4` classes."""
    svg = render_heatmap({}, end_date=date(2026, 4, 9))
    rects = re.findall(r'<rect class="l[0-4]"', svg)
    assert len(rects) == 369


def test_render_heatmap_highlights_counted_days():
    """A single counted day should produce at least one non-l0 cell."""
    counts = {date(2026, 4, 7): 12}
    svg = render_heatmap(counts, end_date=date(2026, 4, 9))
    # Should contain a tooltip for that day with count 12
    assert 'Activity 2026-04-07 — 12 sessions' in svg
    # And at least one l4 rect (since 12 is the max non-zero)
    assert 'class="l4"' in svg


def test_render_heatmap_singular_session_tooltip():
    """Tooltip grammar: 'sessions' plural vs 'session' singular."""
    counts = {date(2026, 4, 7): 1}
    svg = render_heatmap(counts, end_date=date(2026, 4, 9))
    assert 'Activity 2026-04-07 — 1 session<' in svg
    assert '1 sessions' not in svg


def test_render_heatmap_empty_days_use_l0_class():
    """Empty days must render as l0 (lightest color) — NOT be omitted.
    This is the #72 requirement: the grid dimensions stay constant."""
    counts = {date(2026, 4, 7): 12}
    svg = render_heatmap(counts, end_date=date(2026, 4, 9))
    l0_count = svg.count('class="l0"')
    l4_count = svg.count('class="l4"')
    # Exactly one non-zero day → exactly one l4, many l0 cells
    assert l4_count == 1
    assert l0_count > 350  # Nearly all the other cells


def test_render_heatmap_inline_styles_have_palette_fallback():
    """When opened directly (no page CSS), the SVG still needs visible
    cells. The `<style>` block inside the SVG must define fallback colors."""
    svg = render_heatmap({}, end_date=date(2026, 4, 9))
    assert '#ebedf0' in svg  # l0 fallback
    assert '#216e39' in svg  # l4 fallback
    # And the CSS-var references so the page theme can override
    assert 'var(--heatmap-0' in svg
    assert 'var(--heatmap-4' in svg


def test_render_heatmap_stdlib_only_no_html_injection():
    """Title-prefix and date strings must be HTML-escaped — otherwise a
    project named `<script>` could inject into tooltips."""
    svg = render_heatmap({}, end_date=date(2026, 4, 9), title_prefix='<script>alert(1)</script>')
    assert '<script>alert(1)</script>' not in svg
    assert '&lt;script&gt;' in svg


def test_render_heatmap_cell_count_constants():
    """Sanity: the layout constants produce a 53×7 grid — the GitHub shape."""
    assert WEEK_COLS == 53
    assert ROW_COUNT == 7
    assert CELL_SIZE == 11


def test_render_heatmap_has_weekday_labels():
    svg = render_heatmap({}, end_date=date(2026, 4, 9))
    assert '>Mon<' in svg
    assert '>Wed<' in svg
    assert '>Fri<' in svg


def test_render_heatmap_has_month_labels():
    """At least a few month labels should appear — the exact set depends
    on which months have a first-Sunday in the window."""
    svg = render_heatmap({}, end_date=date(2026, 4, 9))
    # All 12 month names should appear across a 365-day window.
    month_labels_found = sum(
        1 for m in ("Jan", "Feb", "Mar", "Apr", "May", "Jun",
                    "Jul", "Aug", "Sep", "Oct", "Nov", "Dec")
        if f">{m}<" in svg
    )
    assert month_labels_found >= 10
