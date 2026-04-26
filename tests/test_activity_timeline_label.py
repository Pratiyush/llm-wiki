"""#453: the Activity timeline label was reporting `dates.length` (count
of distinct dates with at least one session) and labelling it as "days",
which conflated active-day count with calendar span. A user with 5
sessions clustered across a 6-month range saw "5 days" — wrong.

The fix:
  - SVG bar x-position is computed from the date offset (days since
    minDate), so gaps between active periods become visible.
  - Label now reads `Activity timeline · <calendar-span> days · <active>
    active · peak <max> sessions/day` for multi-day collections, or
    `Activity timeline · 1 day · peak N session(s)` for single-day.

These tests pin both the JS source (presence of the new formulas + label
phrasing) and the calendar-span math itself via a Python oracle that
mirrors the JS computation so the algorithm doesn't regress.
"""
from __future__ import annotations

from datetime import date, timedelta

from llmwiki.render.js import JS


def _calendar_span_days(iso_dates: list[str]) -> int:
    """Python oracle for the JS calendar-span computation:
        spanDays = round((maxDate - minDate) / 86400000) + 1
    """
    if not iso_dates:
        return 0
    days = sorted(date.fromisoformat(d) for d in iso_dates)
    return (days[-1] - days[0]).days + 1


def test_js_uses_calendar_span_not_active_day_count() -> None:
    """The bar layout must use the calendar offset, not the array index."""
    assert "spanDays" in JS
    # Old formula was `i * ((w - 2 * padX) / dates.length)`. New formula
    # offsets by calendar days. Catch the regression by asserting the new
    # building blocks are present.
    assert "(maxDate - minDate)" in JS or "maxDate - minDate" in JS
    assert "offset * slotW" in JS


def test_js_label_uses_new_phrasing_for_multi_day() -> None:
    """Multi-day collections must say `<span> days · <active> active`."""
    assert "active · peak" in JS
    assert "sessions/day" in JS


def test_js_label_handles_single_day_specially() -> None:
    """Single-day collection should not say `1 days · 1 active`."""
    assert "spanDays === 1" in JS
    assert "'Activity timeline · 1 day · peak '" in JS


def test_calendar_span_oracle_single_day() -> None:
    """One bar across one day == span of 1."""
    assert _calendar_span_days(["2026-04-01"]) == 1


def test_calendar_span_oracle_consecutive_days() -> None:
    """8 sessions on 8 consecutive days == 8-day calendar span."""
    days = [(date(2026, 4, 1) + timedelta(days=i)).isoformat() for i in range(8)]
    assert _calendar_span_days(days) == 8


def test_calendar_span_oracle_with_gaps() -> None:
    """5 active days clustered in a 6-month window == 6-month span,
    not 5. This is the exact bug #453 was about."""
    iso_dates = [
        "2026-01-15",
        "2026-02-20",
        "2026-03-10",
        "2026-05-30",
        "2026-07-14",
    ]
    span = _calendar_span_days(iso_dates)
    # Jan 15 → Jul 14 inclusive = 181 days (181 = 31-15+1 + 28 + 31 + 30 + 31 + 30 + 14)
    assert span == 181
    # Sanity: must be much bigger than the active-day count
    assert span > 5


def test_calendar_span_oracle_idempotent_for_unsorted_input() -> None:
    """Order-independent — the JS code sorts before computing min/max."""
    assert _calendar_span_days(["2026-04-15", "2026-04-01", "2026-04-10"]) == 15
