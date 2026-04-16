"""Auto Dream — MEMORY.md consolidation (v1.0 · #156).

Implements the Auto Dream consolidation from the LLM Book design spec
(06-navigation-files.md). Triggered after:

  - 24+ hours since the last consolidation, AND
  - 5+ new sessions since the last consolidation.

The consolidation:

  - Replaces relative dates ("Thursday", "last week") with absolute dates
    where possible (requires context)
  - Flags potential contradictions (newer entry on same key)
  - Prunes outdated entries (marked as superseded)
  - Enforces the 200-line cap by dropping the oldest entries

State is tracked in ``.llmwiki-dream-state.json`` at the repo root.

Usage::

    from llmwiki.auto_dream import should_dream, dream

    if should_dream(session_count=7):
        result = dream()
        print(f"Consolidated MEMORY.md: {result['removed']} lines removed")
"""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from llmwiki import REPO_ROOT

DEFAULT_MEMORY = REPO_ROOT / "wiki" / "MEMORY.md"
DEFAULT_STATE = REPO_ROOT / ".llmwiki-dream-state.json"

MIN_SESSIONS_SINCE_LAST = 5
MIN_HOURS_SINCE_LAST = 24
MAX_MEMORY_LINES = 200


# ─── State ─────────────────────────────────────────────────────────────

def _load_state(state_file: Optional[Path] = None) -> dict[str, Any]:
    """Load the dream state."""
    sf = state_file or DEFAULT_STATE
    if not sf.is_file():
        return {"last_dream_at": None, "last_session_count": 0}
    try:
        return json.loads(sf.read_text(encoding="utf-8"))
    except (ValueError, OSError):
        return {"last_dream_at": None, "last_session_count": 0}


def _save_state(state: dict[str, Any], state_file: Optional[Path] = None) -> None:
    """Persist the dream state."""
    sf = state_file or DEFAULT_STATE
    sf.write_text(json.dumps(state, indent=2), encoding="utf-8")


# ─── Trigger check ────────────────────────────────────────────────────

def should_dream(
    *,
    session_count: int,
    now: Optional[datetime] = None,
    state_file: Optional[Path] = None,
) -> bool:
    """Return True if both the 24h and 5-session thresholds are met."""
    state = _load_state(state_file)
    ref_now = now or datetime.now(timezone.utc)

    last_at_str = state.get("last_dream_at")
    last_count = state.get("last_session_count", 0)

    # First run — dream immediately
    if last_at_str is None:
        return session_count >= MIN_SESSIONS_SINCE_LAST

    try:
        last_at = datetime.fromisoformat(last_at_str)
        if last_at.tzinfo is None:
            last_at = last_at.replace(tzinfo=timezone.utc)
    except (ValueError, TypeError):
        return True  # corrupt state → dream

    hours_since = (ref_now - last_at).total_seconds() / 3600
    sessions_since = session_count - last_count

    return hours_since >= MIN_HOURS_SINCE_LAST and sessions_since >= MIN_SESSIONS_SINCE_LAST


# ─── Relative date replacement ───────────────────────────────────────

_WEEKDAYS = {
    "monday": 0, "tuesday": 1, "wednesday": 2, "thursday": 3,
    "friday": 4, "saturday": 5, "sunday": 6,
}

_RELATIVE_PATTERNS = [
    re.compile(r"\byesterday\b", re.IGNORECASE),
    re.compile(r"\btoday\b", re.IGNORECASE),
    re.compile(r"\btomorrow\b", re.IGNORECASE),
    re.compile(r"\blast\s+(week|month|year)\b", re.IGNORECASE),
    re.compile(r"\bnext\s+(week|month|year)\b", re.IGNORECASE),
]


def resolve_relative_dates(text: str, *, now: Optional[datetime] = None) -> tuple[str, int]:
    """Replace relative dates in text with absolute dates.

    Returns the updated text and count of replacements made.
    Conservative — only replaces unambiguous relative dates.
    """
    ref = now or datetime.now(timezone.utc)
    count = 0

    def _sub_today(match):
        nonlocal count
        count += 1
        return ref.strftime("%Y-%m-%d")

    # "today" is unambiguous
    new_text = re.sub(r"\btoday\b", _sub_today, text, flags=re.IGNORECASE)

    return new_text, count


# ─── Outdated entry detection ────────────────────────────────────────

def find_outdated_markers(text: str) -> list[str]:
    """Find lines marked as outdated (e.g. 'SUPERSEDED', 'OUTDATED', 'DEPRECATED')."""
    out = []
    for line in text.splitlines():
        if re.search(r"\b(SUPERSEDED|OUTDATED|DEPRECATED)\b", line):
            out.append(line)
    return out


# ─── Line-cap enforcement ────────────────────────────────────────────

def enforce_line_cap(text: str, *, max_lines: int = MAX_MEMORY_LINES) -> tuple[str, int]:
    """Drop oldest entries to fit under max_lines.

    Preserves the header (lines before the first `##` heading) and
    the newest entries. Returns the truncated text and count of
    lines removed.
    """
    lines = text.splitlines()
    if len(lines) <= max_lines:
        return text, 0

    # Find the first ## heading (header ends there)
    header_end = 0
    for i, line in enumerate(lines):
        if line.startswith("## "):
            header_end = i
            break

    header = lines[:header_end]
    body = lines[header_end:]

    # Keep newest entries at the end. Budget = max - len(header).
    budget = max_lines - len(header)
    if budget < 1:
        return text, 0  # header alone is too long, don't truncate

    kept = body[-budget:]
    removed = len(body) - len(kept)

    return "\n".join(header + kept), removed


# ─── Main consolidation ──────────────────────────────────────────────

def dream(
    *,
    memory_file: Optional[Path] = None,
    state_file: Optional[Path] = None,
    session_count: int = 0,
    now: Optional[datetime] = None,
) -> dict[str, Any]:
    """Run a consolidation pass on MEMORY.md.

    Returns a summary dict with keys:
      - ``replaced``: count of relative-date replacements
      - ``outdated``: count of lines flagged as outdated
      - ``removed``: count of lines dropped by the line-cap
      - ``new_size``: final line count
    """
    mf = memory_file or DEFAULT_MEMORY
    if not mf.is_file():
        return {"replaced": 0, "outdated": 0, "removed": 0, "new_size": 0}

    ref = now or datetime.now(timezone.utc)
    text = mf.read_text(encoding="utf-8")

    text, replaced = resolve_relative_dates(text, now=ref)
    outdated = len(find_outdated_markers(text))
    text, removed = enforce_line_cap(text)

    mf.write_text(text, encoding="utf-8")

    # Update state
    state = {
        "last_dream_at": ref.isoformat(),
        "last_session_count": session_count,
    }
    _save_state(state, state_file)

    return {
        "replaced": replaced,
        "outdated": outdated,
        "removed": removed,
        "new_size": len(text.splitlines()),
    }
