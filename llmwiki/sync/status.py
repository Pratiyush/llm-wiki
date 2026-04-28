"""Sync observability — last run, per-adapter counters, quarantined sources.

G-03 (#289): emits a one-screen status report so operators can see
*what synced / what didn't / why*. Reads ``.llmwiki-state.json`` for
the last-sync timestamp + per-adapter counters (written there by
``convert_all``) and ``.llmwiki-quarantine.json`` for the failing
sources.

#691 / #arch-h8: extracted from ``cli.py`` because it's sync-domain
logic, not argparse glue. ``cli.py`` re-exports ``cmd_sync_status``
+ ``resolve_key_exists`` for back-compat.
"""

from __future__ import annotations

import argparse
import json as _json
import sys
from datetime import datetime, timezone
from pathlib import Path

from llmwiki import REPO_ROOT


def resolve_key_exists(key: str) -> bool:
    """Check whether a portable state-file key points at an extant file.

    Renamed from `_resolve_key_exists` (no leading underscore at the new
    canonical home; cli.py re-exports under the underscored name).
    """
    if "::" not in key:
        return Path(key).exists()
    _, rel = key.split("::", 1)
    candidate = Path.home() / rel
    return candidate.exists() or Path(rel).exists()


def cmd_sync_status(args: argparse.Namespace) -> int:
    """Report sync observability — last run, per-adapter counters, quarantined sources."""
    from llmwiki import quarantine as _q
    from llmwiki.convert import DEFAULT_STATE_FILE

    state: dict = {}
    if DEFAULT_STATE_FILE.is_file():
        try:
            state = _json.loads(DEFAULT_STATE_FILE.read_text(encoding="utf-8"))
        except (ValueError, OSError):
            state = {}

    meta = state.pop("_meta", {}) if isinstance(state, dict) else {}
    counters = state.pop("_counters", {}) if isinstance(state, dict) else {}

    last_sync = meta.get("last_sync")
    if last_sync:
        try:
            ts = datetime.fromisoformat(last_sync.replace("Z", "+00:00"))
            delta = datetime.now(timezone.utc) - ts
            human = f"{int(delta.total_seconds() // 3600)}h ago"
            print(f"Last sync: {last_sync} ({human})")
        except ValueError:
            print(f"Last sync: {last_sync}")
    else:
        print("Last sync: never (or pre-upgrade state file)")

    print()
    if counters:
        print("Adapters:")
        header = (
            f"  {'adapter':<16}  {'discovered':>10}  {'converted':>9}  "
            f"{'unchanged':>9}  {'live':>5}  {'filtered':>8}  {'errored':>7}"
        )
        print(header)
        print("  " + "-" * (len(header) - 2))
        for name, c in sorted(counters.items()):
            print(
                f"  {name:<16}  {c.get('discovered', 0):>10}  "
                f"{c.get('converted', 0):>9}  "
                f"{c.get('unchanged', 0):>9}  "
                f"{c.get('live', 0):>5}  "
                f"{c.get('filtered', 0):>8}  "
                f"{c.get('errored', 0):>7}"
            )
    else:
        print("No per-adapter counters recorded (run `llmwiki sync` first).")

    print()
    orphans = [
        k for k in state.keys()
        if isinstance(k, str) and k.startswith(tuple(f"{n}::" for n in counters))
        and not resolve_key_exists(k)
    ]
    if orphans:
        print(f"Orphan state entries: {len(orphans)} (source path no longer on disk)")

    # Read the module-level default at call time so monkeypatches take effect.
    quar_counts = _q.count_by_adapter(_q.DEFAULT_QUARANTINE_FILE)
    if quar_counts:
        total = sum(quar_counts.values())
        print(f"Quarantined sources: {total} "
              f"({', '.join(f'{k}:{v}' for k, v in sorted(quar_counts.items()))})")
    else:
        print("Quarantined sources: 0")

    if args.recent:
        from llmwiki.log_reader import recent_events
        log_path = REPO_ROOT / "wiki" / "log.md"
        events = recent_events(log_path, limit=args.recent, operations={"sync", "synthesize"})
        if events:
            print()
            print(f"Recent activity (last {len(events)}):")
            for e in events:
                print(f"  [{e.date.isoformat()}] {e.operation:<12} {e.title}")

    return 0
