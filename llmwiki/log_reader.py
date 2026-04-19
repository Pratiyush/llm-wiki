"""Parse ``wiki/log.md`` into structured events (G-18 · #304).

The log is a flat, append-only, grep-parseable file:

    ## [YYYY-MM-DD] operation | title
    - Processed: N
    - Created: a, b
    - Errors: 0

This module turns that stream into a list of ``LogEvent`` records so UI
surfaces (home-page "Recently active" card, a future ``llmwiki log``
CLI, etc.) can query and filter without re-implementing the tiny parser
each time.

Stdlib-only by design — ``llmwiki`` keeps the runtime dependency
surface at "python plus a markdown renderer".
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Iterable, Optional


_HEADING = re.compile(r"^##\s+\[(\d{4}-\d{2}-\d{2})\]\s+(\S+)\s*\|\s*(.+?)\s*$")
# Bullets immediately under a heading look like "- key: value" — we
# capture the key and value into a small details dict so consumers can
# show e.g. the processed count without rendering raw markdown.
_DETAIL = re.compile(r"^\s*-\s+([A-Za-z][A-Za-z0-9 ]*):\s+(.+?)\s*$")


@dataclass(frozen=True)
class LogEvent:
    """One parsed entry from ``wiki/log.md``."""

    date: date
    operation: str
    title: str
    details: dict[str, str]

    def summary(self) -> str:
        """Short one-liner used by UI widgets when details are absent."""
        if "Processed" in self.details:
            return f"{self.operation}: {self.details['Processed']} processed"
        return f"{self.operation}: {self.title}"


def parse_log(log_path: Path) -> list[LogEvent]:
    """Parse ``wiki/log.md`` and return events **oldest first**.

    An unreadable or missing log returns ``[]`` — the function never
    raises so callers can use it in best-effort UI code paths.
    """
    if not log_path.is_file():
        return []
    try:
        lines = log_path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return []

    events: list[LogEvent] = []
    current: Optional[dict] = None
    for raw in lines:
        m = _HEADING.match(raw)
        if m:
            # Flush previous event
            if current is not None:
                events.append(_finalise(current))
            try:
                d = date.fromisoformat(m.group(1))
            except ValueError:
                current = None
                continue
            current = {
                "date": d,
                "operation": m.group(2).strip(),
                "title": m.group(3).strip(),
                "details": {},
            }
            continue
        if current is None:
            continue
        d = _DETAIL.match(raw)
        if d:
            current["details"][d.group(1).strip()] = d.group(2).strip()

    if current is not None:
        events.append(_finalise(current))
    return events


def _finalise(d: dict) -> LogEvent:
    return LogEvent(
        date=d["date"],
        operation=d["operation"],
        title=d["title"],
        details=dict(d["details"]),
    )


def recent_events(
    log_path: Path,
    *,
    limit: int = 10,
    operations: Optional[Iterable[str]] = None,
) -> list[LogEvent]:
    """Return the most recent ``limit`` log entries (newest first).

    ``operations``: optional filter — e.g. ``{"synthesize", "ingest"}``
    keeps only those kinds.  When no entries match, the list is empty.

    Sorting is **stable-by-date-desc**: ties (same-day entries) preserve
    append order, so the very last bullet to land in ``log.md`` appears
    first in the list regardless of how entries are interleaved on disk.
    """
    events = parse_log(log_path)
    if operations:
        wanted = {o.lower() for o in operations}
        events = [e for e in events if e.operation.lower() in wanted]

    # Preserve same-day append order by reversing first, then stable-sort
    # by date desc — Python's ``sorted`` is stable, so same-date entries
    # keep the reversed (= latest-appended-first) order.
    events.reverse()
    events.sort(key=lambda e: e.date, reverse=True)
    return events[:limit]
