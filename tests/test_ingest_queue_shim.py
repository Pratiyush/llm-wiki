"""Tests for #491 — `llmwiki/queue.py` rename to `llmwiki/ingest_queue.py`.

The original `llmwiki/queue.py` shadowed the Python stdlib `queue`
module, breaking any code inside `llmwiki/` that wanted to import
`queue.Queue` for thread-safe primitives. Renamed to
`llmwiki.ingest_queue` (matches the actual purpose — pending-source
ingest queue, not a generic queue). Old name kept as a deprecation
shim through one minor cycle.
"""

from __future__ import annotations

import warnings


def test_canonical_module_imports_cleanly():
    """The new home is `llmwiki.ingest_queue`."""
    from llmwiki import ingest_queue
    assert hasattr(ingest_queue, "enqueue")
    assert hasattr(ingest_queue, "dequeue")
    assert hasattr(ingest_queue, "queue_size")


def test_legacy_shim_re_exports_with_deprecation_warning():
    """`llmwiki.queue` still imports — but warns."""
    # Drop any prior cached import so the shim's warnings.warn fires.
    import importlib
    import sys

    sys.modules.pop("llmwiki.queue", None)

    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        from llmwiki import queue as legacy_queue  # noqa: F401
        importlib.reload(legacy_queue)
    msgs = [str(w.message) for w in caught if issubclass(w.category, DeprecationWarning)]
    assert any("llmwiki.queue" in m for m in msgs), (
        f"expected DeprecationWarning mentioning llmwiki.queue, got {msgs}"
    )
    # Public API still works through the shim
    assert hasattr(legacy_queue, "enqueue")
    assert hasattr(legacy_queue, "queue_size")


def test_stdlib_queue_import_unshadowed():
    """A bare `import queue` from inside `llmwiki/` resolves to stdlib.

    This is the reason for the rename — before #491, this test would
    have surfaced the shim instead of the stdlib's thread-safe Queue.
    """
    import queue as stdlib_queue
    # The stdlib `queue` module has `Queue`, `LifoQueue`, `PriorityQueue` —
    # none of which the llmwiki shim exposes.
    assert hasattr(stdlib_queue, "Queue")
    assert hasattr(stdlib_queue, "LifoQueue")
    assert hasattr(stdlib_queue, "PriorityQueue")
