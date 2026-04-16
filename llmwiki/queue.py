"""Pending ingest queue (v1.0 · #148).

Tracks files that have been converted to raw/ but not yet ingested
into wiki/. The SessionStart hook adds files here after conversion;
``/wiki-sync`` processes and clears the queue.

State is stored in ``.llmwiki-queue.json`` — a simple JSON array of
file paths relative to the repo root.

Usage::

    from llmwiki.queue import enqueue, dequeue, peek, clear, queue_path

    # Hook adds after conversion
    enqueue(["raw/sessions/2026-04-16T10-30-proj-slug.md"])

    # /wiki-sync reads and processes
    pending = dequeue()   # returns list and clears queue
    for path in pending:
        ingest(path)

    # Or peek without consuming
    pending = peek()
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

from llmwiki import REPO_ROOT

DEFAULT_QUEUE_FILE = REPO_ROOT / ".llmwiki-queue.json"


def _load(queue_file: Optional[Path] = None) -> list[str]:
    """Load the queue file. Returns list of relative paths."""
    qf = queue_file or DEFAULT_QUEUE_FILE
    if not qf.is_file():
        return []
    try:
        data = json.loads(qf.read_text(encoding="utf-8"))
        if isinstance(data, list):
            return [str(p) for p in data if isinstance(p, str)]
    except (json.JSONDecodeError, OSError):
        pass
    return []


def _save(items: list[str], queue_file: Optional[Path] = None) -> None:
    """Save the queue file."""
    qf = queue_file or DEFAULT_QUEUE_FILE
    qf.write_text(
        json.dumps(sorted(set(items)), indent=2), encoding="utf-8"
    )


def enqueue(
    paths: list[str],
    *,
    queue_file: Optional[Path] = None,
) -> int:
    """Add paths to the pending ingest queue.

    Deduplicates automatically. Returns the new queue length.
    """
    current = _load(queue_file)
    combined = list(set(current) | set(paths))
    _save(combined, queue_file)
    return len(combined)


def dequeue(*, queue_file: Optional[Path] = None) -> list[str]:
    """Return all pending paths and clear the queue.

    This is the consume operation — after calling this, the queue
    is empty. Process the returned paths, then they're done.
    """
    items = _load(queue_file)
    qf = queue_file or DEFAULT_QUEUE_FILE
    if qf.is_file():
        qf.write_text("[]", encoding="utf-8")
    return items


def peek(*, queue_file: Optional[Path] = None) -> list[str]:
    """Return pending paths without consuming them."""
    return _load(queue_file)


def clear(*, queue_file: Optional[Path] = None) -> None:
    """Clear the queue without reading."""
    qf = queue_file or DEFAULT_QUEUE_FILE
    if qf.is_file():
        qf.write_text("[]", encoding="utf-8")


def queue_size(*, queue_file: Optional[Path] = None) -> int:
    """Return the number of pending items."""
    return len(_load(queue_file))
