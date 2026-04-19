"""Convert-error quarantine (G-14 · #300).

When ``llmwiki sync`` hits a converter exception we used to just print
``error: <file>: <reason>`` to stderr and move on — one bad source was
enough to silently drop a session from the corpus with no audit trail.

This module introduces a persistent quarantine file
(``.llmwiki-quarantine.json``) so:

1. Every failing source gets recorded once with the error, adapter, and
   both first/last-seen timestamps.
2. ``llmwiki quarantine list`` surfaces the queue so operators can see
   what didn't sync and why.
3. ``llmwiki quarantine clear --all|<path>`` wipes entries after the
   underlying bug is fixed so the next sync retries them.
4. ``llmwiki quarantine retry`` prints a plan for targeted re-sync.
5. ``llmwiki sync --status`` (G-03 · #289) reads the same file.

Stdlib-only and schema-versioned (``"version": 1``) so future changes
stay backwards-compatible.  File format is deterministic — entries are
sorted by ``adapter, source`` so diffs stay small and git-friendly if a
user ever chooses to commit the file (the repo ``.gitignore`` keeps it
local by default).
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Optional

from llmwiki import REPO_ROOT


DEFAULT_QUARANTINE_FILE = REPO_ROOT / ".llmwiki-quarantine.json"
SCHEMA_VERSION = 1


@dataclass
class QuarantineEntry:
    """One record in ``.llmwiki-quarantine.json``.

    Equality is by ``(adapter, source)`` — the pair uniquely identifies
    a failing source regardless of when it failed.
    """

    adapter: str
    source: str
    error: str
    first_seen: str  # ISO-8601 UTC
    last_seen: str   # ISO-8601 UTC
    attempts: int = 1
    extra: dict[str, Any] = field(default_factory=dict)

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, QuarantineEntry):
            return NotImplemented
        return (self.adapter, self.source) == (other.adapter, other.source)

    def __hash__(self) -> int:
        return hash((self.adapter, self.source))


def _now_utc_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def load(path: Path = DEFAULT_QUARANTINE_FILE) -> list[QuarantineEntry]:
    """Load the quarantine file. Returns ``[]`` on missing/corrupt file.

    Never raises — the caller treats the quarantine as best-effort UI.
    Malformed entries are skipped individually so one bad row doesn't
    blow up the whole file.
    """
    if not path.is_file():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    if not isinstance(data, dict):
        return []
    raw_entries = data.get("entries", [])
    if not isinstance(raw_entries, list):
        return []
    out: list[QuarantineEntry] = []
    for row in raw_entries:
        if not isinstance(row, dict):
            continue
        try:
            out.append(
                QuarantineEntry(
                    adapter=str(row["adapter"]),
                    source=str(row["source"]),
                    error=str(row.get("error", "")),
                    first_seen=str(row.get("first_seen", _now_utc_iso())),
                    last_seen=str(row.get("last_seen", _now_utc_iso())),
                    attempts=int(row.get("attempts", 1)),
                    extra=row.get("extra", {}) or {},
                )
            )
        except (KeyError, TypeError, ValueError):
            continue
    return out


def save(
    entries: Iterable[QuarantineEntry],
    path: Path = DEFAULT_QUARANTINE_FILE,
) -> Path:
    """Write the quarantine file. Sorts deterministically for stable diffs."""
    items = sorted(set(entries), key=lambda e: (e.adapter, e.source))
    payload = {
        "version": SCHEMA_VERSION,
        "updated": _now_utc_iso(),
        "entries": [asdict(e) for e in items],
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return path


def add_entry(
    adapter: str,
    source: str,
    error: str,
    *,
    path: Path = DEFAULT_QUARANTINE_FILE,
    extra: Optional[dict[str, Any]] = None,
) -> QuarantineEntry:
    """Add or refresh a quarantine entry.

    If ``(adapter, source)`` already exists the call bumps ``attempts``,
    updates ``last_seen`` + ``error``, and merges ``extra`` — callers
    can retry a failing source and each failure is counted without
    creating duplicate rows.
    """
    if not adapter or not source:
        raise ValueError("adapter and source are required")
    now = _now_utc_iso()
    entries = load(path)
    by_key = {(e.adapter, e.source): e for e in entries}
    key = (adapter, source)
    if key in by_key:
        e = by_key[key]
        e.attempts += 1
        e.last_seen = now
        e.error = error or e.error
        if extra:
            e.extra = {**(e.extra or {}), **extra}
        updated = e
    else:
        updated = QuarantineEntry(
            adapter=adapter,
            source=source,
            error=error,
            first_seen=now,
            last_seen=now,
            attempts=1,
            extra=dict(extra or {}),
        )
        entries.append(updated)
    save(entries, path)
    return updated


def clear_entry(
    source: str,
    *,
    adapter: Optional[str] = None,
    path: Path = DEFAULT_QUARANTINE_FILE,
) -> int:
    """Remove matching entries.  Returns count removed.

    If ``adapter`` is ``None`` every entry whose ``source`` matches is
    removed (useful when the operator passes an absolute path without
    remembering which adapter produced it).
    """
    entries = load(path)
    keep: list[QuarantineEntry] = []
    removed = 0
    for e in entries:
        match_adapter = adapter is None or e.adapter == adapter
        if match_adapter and e.source == source:
            removed += 1
            continue
        keep.append(e)
    if removed:
        save(keep, path)
    return removed


def clear_all(path: Path = DEFAULT_QUARANTINE_FILE) -> int:
    """Drop every entry. Returns count removed."""
    entries = load(path)
    n = len(entries)
    if n:
        save([], path)
    return n


def list_entries(
    path: Path = DEFAULT_QUARANTINE_FILE,
    *,
    adapter: Optional[str] = None,
) -> list[QuarantineEntry]:
    """Return entries filtered by adapter (stable ordering)."""
    out = load(path)
    if adapter:
        out = [e for e in out if e.adapter == adapter]
    return sorted(out, key=lambda e: (e.adapter, e.last_seen), reverse=False)


def format_table(entries: list[QuarantineEntry]) -> str:
    """Human-readable table — used by the CLI + ``sync --status``."""
    if not entries:
        return "No quarantined sources."
    widths = {
        "adapter": max(8, max(len(e.adapter) for e in entries)),
        "error": 48,
        "source": max(20, max(len(Path(e.source).name) for e in entries)),
    }
    header = (
        f"  {'adapter':<{widths['adapter']}}  "
        f"{'source':<{widths['source']}}  "
        f"{'attempts':>8}  {'last_seen':<20}  error"
    )
    sep = "  " + "-" * (widths["adapter"] + widths["source"] + 8 + 20 + 48 + 10)
    rows = [header, sep]
    for e in entries:
        err = e.error
        if len(err) > widths["error"]:
            err = err[: widths["error"] - 3] + "..."
        rows.append(
            f"  {e.adapter:<{widths['adapter']}}  "
            f"{Path(e.source).name:<{widths['source']}}  "
            f"{e.attempts:>8}  {e.last_seen:<20}  {err}"
        )
    return "\n".join(rows)


def count_by_adapter(
    path: Path = DEFAULT_QUARANTINE_FILE,
) -> dict[str, int]:
    """Aggregate helper for ``llmwiki sync --status``."""
    out: dict[str, int] = {}
    for e in load(path):
        out[e.adapter] = out.get(e.adapter, 0) + 1
    return out
