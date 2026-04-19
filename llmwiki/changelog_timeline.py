"""Append-only page changelog + timeline renderer (v0.7 · closes #56).

An entity page (especially AI-model pages from #55) can declare a
`changelog:` list in its frontmatter. Each entry records a dated change
to a specific field, so llmwiki can render:

1. A **timeline widget** on the page showing what changed when
2. An inline **pricing sparkline** if the changelog contains ≥2 numeric
   price changes
3. A **"Recently updated"** list on the home page surfacing entities
   that changed in the last 30 days

Append-only by design — entries are never edited, only added. If a
change is wrong, you add a new correcting entry rather than rewriting
history. The wiki log doubles as an audit trail.

Schema (inline JSON per entry, list of objects in YAML):

```yaml
changelog: [
  {"date": "2026-01-15", "event": "Input pricing reduced", "field": "model.pricing.input_per_1m", "from": 4.00, "to": 3.00},
  {"date": "2026-02-02", "event": "Context window expanded", "field": "model.context_window", "from": 100000, "to": 200000}
]
```

Stdlib-only. No new dependencies.
"""

from __future__ import annotations

import html
import json
from datetime import date, datetime, timedelta, timezone
from typing import Any, Iterable, Mapping, Optional, TypedDict

# ─── types ───────────────────────────────────────────────────────────────


class ChangelogEntry(TypedDict, total=False):
    date: str     # ISO date
    event: str    # Human-readable description
    field: str    # Dotted path into the entity's schema
    # `from` and `to` can be numeric OR string — e.g. a license change
    # goes from `"proprietary"` to `"apache-2.0"`, pricing goes from 4.00
    # to 3.00. We keep them as raw values and leave interpretation to the
    # renderer.
    from_value: Any
    to_value: Any


# ─── parsing ─────────────────────────────────────────────────────────────


def parse_changelog(meta: Mapping[str, Any]) -> tuple[list[ChangelogEntry], list[str]]:
    """Pull a `changelog` list from frontmatter.

    Returns `(entries, warnings)`. Entries are sorted ascending by date.
    Malformed entries (missing date, unparseable date, missing event)
    are dropped with a warning — the rest still render.

    The frontmatter parser stores the value as either a JSON string
    (our inline-JSON convention) or a Python list (tests / programmatic
    callers). Both are handled.
    """
    raw = meta.get("changelog")
    if not raw:
        return [], []

    data: Any = raw
    if isinstance(raw, str):
        try:
            data = json.loads(raw)
        except (ValueError, json.JSONDecodeError):
            return [], ["changelog must be a JSON list"]

    # The lightweight frontmatter parser in `build.py` (and
    # `models_page._parse_frontmatter`) naively splits bracketed list
    # values on commas. That mangles a JSON array of objects like
    # `[{"a":1, "b":2}, {"c":3}]` into
    # `['{"a":1', '"b":2}', '{"c":3}']`. If we see a list of
    # string fragments that don't parse as JSON objects on their own,
    # stitch them back together and re-parse as a JSON array.
    if (
        isinstance(data, list)
        and data
        and all(isinstance(x, str) for x in data)
    ):
        stitched = "[" + ", ".join(data) + "]"
        try:
            reparsed = json.loads(stitched)
            if isinstance(reparsed, list):
                data = reparsed
        except (ValueError, json.JSONDecodeError):
            pass  # fall through; the element-level validator will reject

    if not isinstance(data, list):
        return [], ["changelog must be a list"]

    warnings: list[str] = []
    entries: list[ChangelogEntry] = []
    for i, item in enumerate(data):
        if not isinstance(item, dict):
            warnings.append(f"changelog[{i}] must be an object")
            continue
        raw_date = item.get("date")
        if not raw_date:
            warnings.append(f"changelog[{i}] missing required field: date")
            continue
        try:
            date.fromisoformat(str(raw_date)[:10])
        except (ValueError, TypeError):
            warnings.append(f"changelog[{i}].date is not a valid ISO date")
            continue
        event = item.get("event")
        if not event:
            warnings.append(f"changelog[{i}] missing required field: event")
            continue
        entry: ChangelogEntry = {
            "date": str(raw_date)[:10],
            "event": str(event),
        }
        if "field" in item:
            entry["field"] = str(item["field"])
        if "from" in item:
            entry["from_value"] = item["from"]
        if "to" in item:
            entry["to_value"] = item["to"]
        entries.append(entry)

    entries.sort(key=lambda e: e["date"])
    return entries, warnings


# ─── timeline render ─────────────────────────────────────────────────────


def render_changelog_timeline(entries: list[ChangelogEntry]) -> str:
    """Render a vertical timeline of changelog entries. Empty input
    returns an empty string so callers can `if html:` gate on whether
    to show the surrounding section."""
    if not entries:
        return ""
    # Timeline is ordered newest-first for reader flow
    rows: list[str] = []
    for entry in reversed(entries):
        delta_html = _format_delta(entry)
        field_html = (
            f'<code class="timeline-field">{html.escape(entry["field"])}</code>'
            if entry.get("field") else ""
        )
        rows.append(
            '<li class="timeline-item">'
            f'<span class="timeline-date">{html.escape(entry["date"])}</span>'
            f'<span class="timeline-dot"></span>'
            '<div class="timeline-body">'
            f'<div class="timeline-event">{html.escape(entry["event"])}</div>'
            + (f'<div class="timeline-detail">{field_html} {delta_html}</div>'
               if field_html or delta_html else "")
            + '</div>'
            '</li>'
        )
    return (
        '<ol class="changelog-timeline">'
        + "".join(rows)
        + '</ol>'
    )


def _format_delta(entry: ChangelogEntry) -> str:
    """Format a from→to delta as HTML, picking a numeric or string
    representation based on what the values look like."""
    if "from_value" not in entry and "to_value" not in entry:
        return ""
    frm = entry.get("from_value")
    to = entry.get("to_value")

    def render_value(v: Any) -> str:
        if v is None:
            return '<span class="muted">null</span>'
        if isinstance(v, bool):
            return str(v).lower()
        if isinstance(v, (int, float)):
            return _format_number(v)
        return html.escape(str(v))

    frm_html = render_value(frm)
    to_html = render_value(to)
    # Add a color hint for numeric changes: up = positive delta in
    # price is bad, in benchmark is good — so we stay neutral and
    # just show the arrow direction.
    arrow_cls = "timeline-arrow"
    if isinstance(frm, (int, float)) and isinstance(to, (int, float)):
        if to > frm:
            arrow_cls += " timeline-arrow-up"
        elif to < frm:
            arrow_cls += " timeline-arrow-down"
    return (
        f'<span class="timeline-delta">'
        f'<span class="timeline-from">{frm_html}</span>'
        f'<span class="{arrow_cls}">→</span>'
        f'<span class="timeline-to">{to_html}</span>'
        f'</span>'
    )


def _format_number(n: float) -> str:
    """Compact numeric formatting for timeline values.

    * Large counts (≥1000) get K/M suffix.
    * Small counts render as-is.
    * Floats with 2+ decimals stay as-is (pricing).
    * Whole-number floats drop the decimal.
    """
    if isinstance(n, float):
        if n.is_integer() and abs(n) < 1000:
            return str(int(n))
        if abs(n) < 1:
            return f"{n:.3f}".rstrip("0").rstrip(".")
        if abs(n) < 1000:
            return f"{n:.2f}".rstrip("0").rstrip(".")
    if abs(n) >= 1_000_000:
        return f"{n / 1_000_000:.1f}M"
    if abs(n) >= 1000:
        return f"{n / 1000:.1f}K"
    return str(n)


# ─── pricing sparkline ───────────────────────────────────────────────────


def extract_price_points(
    entries: list[ChangelogEntry],
    field_suffix: str = "pricing.input_per_1m",
) -> list[tuple[date, float]]:
    """Return `[(date, value), …]` for every numeric `to_value` whose
    `field` ends with `field_suffix`. Used to feed the pricing sparkline.

    Matches on suffix so `model.pricing.input_per_1m` and
    `pricing.input_per_1m` both hit — schema callers sometimes use
    different path roots.
    """
    out: list[tuple[date, float]] = []
    for e in entries:
        field = e.get("field", "")
        if not field.endswith(field_suffix):
            continue
        to_value = e.get("to_value")
        if to_value is None:
            continue
        try:
            val = float(to_value)
        except (TypeError, ValueError):
            continue
        try:
            d = date.fromisoformat(e["date"])
        except ValueError:
            continue
        out.append((d, val))
    return out


def render_price_sparkline(
    points: list[tuple[date, float]],
    width: int = 220,
    height: int = 40,
) -> str:
    """Render an inline SVG sparkline for a price series. Empty input
    returns an empty string. Fewer than 2 points returns an empty
    string (can't draw a line through 1 point)."""
    if len(points) < 2:
        return ""
    values = [v for _, v in points]
    min_v = min(values)
    max_v = max(values)
    pad_x = 4
    pad_y = 4
    plot_w = width - 2 * pad_x
    plot_h = height - 2 * pad_y

    if max_v == min_v:
        # Flat series — draw a horizontal line at the middle
        midy = pad_y + plot_h / 2
        path_d = f"M {pad_x} {midy:.1f} L {pad_x + plot_w} {midy:.1f}"
    else:
        n = len(points)
        xs = [pad_x + (i / (n - 1)) * plot_w for i in range(n)]
        ys = [
            pad_y + plot_h - ((v - min_v) / (max_v - min_v)) * plot_h
            for v in values
        ]
        parts = [f"M {xs[0]:.1f} {ys[0]:.1f}"]
        for x, y in zip(xs[1:], ys[1:]):
            parts.append(f"L {x:.1f} {y:.1f}")
        path_d = " ".join(parts)

    # End dots: first + last
    first_x = pad_x
    first_y = pad_y + plot_h - (
        (values[0] - min_v) / (max_v - min_v) * plot_h if max_v != min_v else plot_h / 2
    )
    last_x = pad_x + plot_w
    last_y = pad_y + plot_h - (
        (values[-1] - min_v) / (max_v - min_v) * plot_h if max_v != min_v else plot_h / 2
    )

    tooltip = (
        f"{points[0][0].isoformat()}: {values[0]:.2f} → "
        f"{points[-1][0].isoformat()}: {values[-1]:.2f}"
    )
    return (
        f'<svg class="price-sparkline" xmlns="http://www.w3.org/2000/svg" '
        f'viewBox="0 0 {width} {height}" width="{width}" height="{height}" '
        f'role="img" aria-label="{html.escape(tooltip)}">'
        f'<title>{html.escape(tooltip)}</title>'
        f'<path d="{path_d}" fill="none" '
        'stroke="var(--accent, #7C3AED)" stroke-width="1.5" '
        'stroke-linecap="round" stroke-linejoin="round"/>'
        f'<circle cx="{first_x:.1f}" cy="{first_y:.1f}" r="2.2" fill="var(--accent, #7C3AED)"/>'
        f'<circle cx="{last_x:.1f}" cy="{last_y:.1f}" r="2.2" fill="var(--accent, #7C3AED)"/>'
        '</svg>'
    )


# ─── "recently updated" aggregator ───────────────────────────────────────


def find_recently_updated(
    pages: Iterable[tuple[str, Mapping[str, Any]]],
    now: Optional[date] = None,
    within_days: int = 30,
) -> list[tuple[str, ChangelogEntry]]:
    """Given an iterable of `(slug, meta)` pairs, return a list of
    `(slug, latest_changelog_entry)` for pages that have a changelog
    entry dated within the last `within_days` days, sorted by latest
    change descending.

    Used by the home-page "Recently updated" widget so readers can see
    which model pages have had their pricing, context, or benchmark
    scores revised lately.
    """
    if now is None:
        now = datetime.now(timezone.utc).date()
    cutoff = now - timedelta(days=within_days)
    out: list[tuple[str, ChangelogEntry, date]] = []
    for slug, meta in pages:
        entries, _ = parse_changelog(meta)
        if not entries:
            continue
        latest = entries[-1]
        try:
            d = date.fromisoformat(latest["date"])
        except ValueError:
            continue
        if d < cutoff:
            continue
        out.append((slug, latest, d))
    out.sort(key=lambda x: x[2], reverse=True)
    return [(slug, entry) for slug, entry, _ in out]


def render_recently_updated(
    items: list[tuple[str, ChangelogEntry]],
    link_prefix: str = "models/",
) -> str:
    """Render the "Recently updated" home-page list from the output of
    `find_recently_updated`. Empty input returns an empty string."""
    if not items:
        return ""
    rows: list[str] = []
    for slug, entry in items:
        rows.append(
            f'<li class="recently-updated-item">'
            f'<a href="{html.escape(link_prefix)}{html.escape(slug)}.html">'
            f'<span class="recently-updated-slug">{html.escape(slug)}</span>'
            f'</a>'
            f'<span class="recently-updated-date muted">{html.escape(entry["date"])}</span>'
            f'<span class="recently-updated-event">{html.escape(entry["event"])}</span>'
            f'</li>'
        )
    return (
        '<div class="recently-updated-card">'
        '<div class="recently-updated-title muted">Recently updated · last 30 days</div>'
        '<ul class="recently-updated-list">' + "".join(rows) + '</ul>'
        '</div>'
    )


def render_recent_activity(log_events: list[Any]) -> str:
    """Render a "Recent activity" card driven from ``wiki/log.md`` (G-18 · #304).

    ``log_events`` is a list of :class:`llmwiki.log_reader.LogEvent`
    records — passed as ``Any`` here to avoid an import cycle.  The home
    page uses this as a fallback when no model-changelog updates are
    available, so the "Recently updated" surface shows real activity
    instead of sitting empty on corpora without model pages.
    """
    if not log_events:
        return ""
    rows: list[str] = []
    for ev in log_events:
        # Prefer a processed-count detail when present; otherwise show title.
        processed = ev.details.get("Processed") if hasattr(ev, "details") else None
        right_label = f"{processed} processed" if processed else ev.title
        rows.append(
            f'<li class="recently-updated-item">'
            f'<span class="recently-updated-slug">{html.escape(ev.operation)}</span>'
            f'<span class="recently-updated-date muted">{html.escape(ev.date.isoformat())}</span>'
            f'<span class="recently-updated-event">{html.escape(right_label)}</span>'
            f'</li>'
        )
    return (
        '<div class="recently-updated-card">'
        f'<div class="recently-updated-title muted">Recent activity · last {len(log_events)} operations</div>'
        '<ul class="recently-updated-list">' + "".join(rows) + '</ul>'
        '</div>'
    )
