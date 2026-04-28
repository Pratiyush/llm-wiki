"""Sync subpackage — observability + status reporting (#691 / #arch-h8).

Pre-#691 ``cmd_sync_status`` and ``_resolve_key_exists`` lived inside
``cli.py``. They're sync-domain logic (state-file parsing, quarantine
counts, orphan detection) that doesn't belong in a CLI shim. Both
move under this package; ``cli.py`` re-exports them for back-compat.
"""

from __future__ import annotations

from llmwiki.sync.status import cmd_sync_status, resolve_key_exists  # noqa: F401

__all__ = ["cmd_sync_status", "resolve_key_exists"]
