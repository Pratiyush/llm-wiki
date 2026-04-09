"""Content-freshness badges — v0.6 (#57).

Computes the age of a page (in days) from its frontmatter and returns a
color-coded badge rendered as HTML. Ages are bucketed into:

- ``fresh-green``  — updated ≤ ``green_days`` ago (default 14)
- ``fresh-yellow`` — updated ≤ ``yellow_days`` ago (default 60)
- ``fresh-red``    — updated > ``yellow_days`` ago
- ``fresh-unknown`` — no resolvable timestamp OR clock skew (future)

Thresholds can be overridden via ``config.json``::

    {
      "freshness": {
        "green_days": 14,
        "yellow_days": 60
      }
    }

The badge text uses a compact relative-time formatter (today / yesterday /
N days / N weeks / N months / N years). All timestamps are normalised to
naive UTC before subtraction so timezone skew between session files and
the build host cannot move pages across buckets by accident.
"""

from __future__ import annotations

import html
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from llmwiki import REPO_ROOT

DEFAULT_GREEN_DAYS = 14
DEFAULT_YELLOW_DAYS = 60


def load_freshness_config(repo_root: Path = REPO_ROOT) -> tuple[int, int]:
    """Return ``(green_days, yellow_days)`` from ``config.json`` or defaults."""
    candidate = repo_root / "config.json"
    if not candidate.exists():
        return DEFAULT_GREEN_DAYS, DEFAULT_YELLOW_DAYS
    try:
        data = json.loads(candidate.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return DEFAULT_GREEN_DAYS, DEFAULT_YELLOW_DAYS
    fresh = data.get("freshness") or {}
    try:
        green = int(fresh.get("green_days", DEFAULT_GREEN_DAYS))
        yellow = int(fresh.get("yellow_days", DEFAULT_YELLOW_DAYS))
    except (TypeError, ValueError):
        return DEFAULT_GREEN_DAYS, DEFAULT_YELLOW_DAYS
    if green < 0 or yellow < green:
        return DEFAULT_GREEN_DAYS, DEFAULT_YELLOW_DAYS
    return green, yellow


def parse_timestamp(value: Any) -> Optional[datetime]:
    """Parse an ISO datetime or ``YYYY-MM-DD`` into a naive UTC datetime.

    Returns ``None`` for empty, missing, or malformed values.
    """
    if value is None:
        return None
    s = str(value).strip()
    if not s:
        return None
    # Try ISO datetime first (with or without timezone)
    if "T" in s or "+" in s[10:] or "Z" in s:
        clean = s.replace("Z", "+00:00")
        try:
            dt = datetime.fromisoformat(clean)
        except ValueError:
            return None
        if dt.tzinfo is not None:
            dt = dt.astimezone(timezone.utc).replace(tzinfo=None)
        return dt
    # Fall back to date-only
    try:
        return datetime.strptime(s[:10], "%Y-%m-%d")
    except ValueError:
        return None


def resolve_last_updated(meta: dict[str, Any]) -> Optional[datetime]:
    """Pick the newest timestamp available from a page's frontmatter.

    Prefers ``last_updated`` (explicit), then ``ended``, ``started``, ``date``.
    """
    for key in ("last_updated", "ended", "started", "date"):
        dt = parse_timestamp(meta.get(key))
        if dt is not None:
            return dt
    return None


def format_relative_time(age_days: int) -> str:
    """Compact human label for an age in days (never more than 2 words)."""
    if age_days < 0:
        return "unknown"
    if age_days == 0:
        return "today"
    if age_days == 1:
        return "yesterday"
    if age_days < 14:
        return f"{age_days} days ago"
    if age_days < 60:
        weeks = age_days // 7
        return f"{weeks} week{'s' if weeks != 1 else ''} ago"
    if age_days < 365:
        months = age_days // 30
        return f"{months} month{'s' if months != 1 else ''} ago"
    years = age_days // 365
    return f"{years} year{'s' if years != 1 else ''} ago"


def freshness_class(
    age_days: Optional[int],
    green_days: int = DEFAULT_GREEN_DAYS,
    yellow_days: int = DEFAULT_YELLOW_DAYS,
) -> str:
    """Return the CSS class for a given age. ``None`` or negative → unknown."""
    if age_days is None or age_days < 0:
        return "fresh-unknown"
    if age_days <= green_days:
        return "fresh-green"
    if age_days <= yellow_days:
        return "fresh-yellow"
    return "fresh-red"


def freshness_badge(
    meta: dict[str, Any],
    now: Optional[datetime] = None,
    green_days: int = DEFAULT_GREEN_DAYS,
    yellow_days: int = DEFAULT_YELLOW_DAYS,
) -> str:
    """Render a freshness badge for a page given its frontmatter.

    ``now`` lets tests inject a deterministic clock; otherwise ``utcnow()``.
    """
    dt = resolve_last_updated(meta)
    if dt is None:
        return (
            '<span class="freshness fresh-unknown" '
            'title="No last-updated timestamp">updated unknown</span>'
        )
    current = now if now is not None else datetime.now(timezone.utc).replace(tzinfo=None)
    age = (current - dt).days
    cls = freshness_class(age, green_days, yellow_days)
    label = format_relative_time(age)
    iso = dt.strftime("%Y-%m-%d")
    return (
        f'<span class="freshness {cls}" '
        f'title="Last updated {html.escape(iso)}">updated {html.escape(label)}</span>'
    )
