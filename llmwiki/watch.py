"""File watcher — auto-resync when a new .jsonl lands in an agent's session store.

Watches the session store paths that registered adapters know about, and when
a file changes, runs `llmwiki sync` in the background. Useful as an
alternative to the SessionStart hook.

Uses polling (stdlib-only, no `watchdog` dep). Polls every N seconds; when a
file's mtime changes, debounces for M seconds before running sync.

Usage:

    python3 -m llmwiki watch                  # default 5s poll, 10s debounce
    python3 -m llmwiki watch --interval 2     # faster polling
    python3 -m llmwiki watch --adapter claude_code

Stop with Ctrl+C.
"""

from __future__ import annotations

import argparse
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

from llmwiki import REPO_ROOT
from llmwiki.adapters import REGISTRY, discover_adapters


def scan_mtimes(adapters: list[str] | None) -> dict[str, float]:
    """Return a dict of {path: mtime} for every .jsonl file visible to the
    given adapters (or all available adapters if None)."""
    discover_adapters()
    selected_cls = []
    if adapters:
        for name in adapters:
            if name in REGISTRY:
                selected_cls.append(REGISTRY[name])
    else:
        selected_cls = [c for c in REGISTRY.values() if c.is_available()]

    mtimes: dict[str, float] = {}
    for cls in selected_cls:
        adapter = cls()
        for p in adapter.discover_sessions():
            try:
                mtimes[str(p)] = p.stat().st_mtime
            except OSError:
                continue
    return mtimes


def run_sync(dry_run: bool = False) -> int:
    """Invoke `python3 -m llmwiki sync` as a subprocess."""
    cmd = [sys.executable, "-m", "llmwiki", "sync"]
    if dry_run:
        cmd.append("--dry-run")
    print(f"==> running: {' '.join(cmd)}")
    try:
        result = subprocess.run(cmd, cwd=str(REPO_ROOT), timeout=180)
        return result.returncode
    except subprocess.TimeoutExpired:
        print("  warning: sync timed out after 180s", file=sys.stderr)
        return 1
    except Exception as e:
        print(f"  warning: sync failed: {e}", file=sys.stderr)
        return 1


def watch(
    adapters: list[str] | None = None,
    interval: float = 5.0,
    debounce: float = 10.0,
    dry_run: bool = False,
) -> int:
    """Main watch loop.

    Args:
        adapters: Adapter names to watch. None = all available.
        interval: Polling interval in seconds.
        debounce: Wait this many seconds after the last change before syncing.
        dry_run: Pass --dry-run to the sync invocation.
    """
    print("==> llmwiki watch")
    print(f"    interval: {interval}s")
    print(f"    debounce: {debounce}s")
    if adapters:
        print(f"    adapters: {', '.join(adapters)}")
    else:
        discover_adapters()
        avail = [n for n, c in REGISTRY.items() if c.is_available()]
        print(f"    adapters: {', '.join(avail) or '(none available)'}")
    print("    Ctrl+C to stop.")
    print()

    baseline = scan_mtimes(adapters)
    print(f"==> baseline: {len(baseline)} files")

    last_change: float = 0.0
    pending = False

    try:
        while True:
            time.sleep(interval)
            current = scan_mtimes(adapters)

            # Detect changes
            changed_paths: list[str] = []
            for path, mtime in current.items():
                if path not in baseline or baseline[path] != mtime:
                    changed_paths.append(path)

            if changed_paths:
                last_change = time.time()
                pending = True
                print(f"==> detected {len(changed_paths)} change(s)")
                for p in changed_paths[:5]:
                    print(f"    {Path(p).name}")
                if len(changed_paths) > 5:
                    print(f"    ... and {len(changed_paths) - 5} more")

            # If a change is pending and the debounce window has elapsed, sync
            if pending and (time.time() - last_change) >= debounce:
                run_sync(dry_run=dry_run)
                pending = False
                baseline = scan_mtimes(adapters)
                print(f"==> watching {len(baseline)} files")

    except KeyboardInterrupt:
        print("\n==> stopped.")
        return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--adapter", nargs="*", help="Adapter name(s) to watch")
    parser.add_argument("--interval", type=float, default=5.0, help="Polling interval (seconds)")
    parser.add_argument("--debounce", type=float, default=10.0, help="Debounce window (seconds)")
    parser.add_argument("--dry-run", action="store_true", help="Don't write, just report")
    args = parser.parse_args(argv)
    return watch(
        adapters=args.adapter,
        interval=args.interval,
        debounce=args.debounce,
        dry_run=args.dry_run,
    )


if __name__ == "__main__":
    sys.exit(main())
