"""Base class for session-store adapters.

An adapter knows two things about one coding agent:
  1. WHERE its .jsonl session transcripts live on disk
  2. HOW to discover them (walking the directory tree)

Everything else — record filtering, markdown rendering, redaction, state
tracking — is shared in `llmwiki.convert` and operates on the iterator this
class returns.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Iterator


class BaseAdapter:
    """Adapter interface.

    Subclasses must set `session_store_path` (a Path or list of Paths) and
    implement `is_available()`. The default `discover_sessions()` does a
    recursive glob for `*.jsonl`; override only if your agent uses a different
    extension or layout.
    """

    #: Unique adapter name (set by @register decorator).
    name: str = "base"

    #: Path or list of paths where this agent writes session transcripts.
    #: Subclasses MUST override.
    session_store_path: Path | list[Path] = Path("/dev/null")

    def __init__(self, config: dict[str, Any] | None = None):
        self.config = config or {}

    # ─── classmethods used by the registry + UI ────────────────────────

    @classmethod
    def description(cls) -> str:
        """One-line description shown in `llmwiki adapters`."""
        return cls.__doc__.split("\n")[0] if cls.__doc__ else cls.__name__

    @classmethod
    def is_available(cls) -> bool:
        """True if the session store exists on this machine."""
        paths = cls.session_store_path
        if isinstance(paths, Path):
            paths = [paths]
        return any(Path(p).expanduser().exists() for p in paths)

    # ─── discovery ─────────────────────────────────────────────────────

    def discover_sessions(self) -> list[Path]:
        """Return a sorted list of all .jsonl files under the session store."""
        paths: list[Path] = []
        stores = self.session_store_path
        if isinstance(stores, Path):
            stores = [stores]
        for store in stores:
            store = Path(store).expanduser()
            if store.exists():
                paths.extend(sorted(store.rglob("*.jsonl")))
        return paths

    # ─── per-agent helpers ─────────────────────────────────────────────

    def derive_project_slug(self, jsonl_path: Path) -> str:
        """Derive a friendly project slug from a .jsonl file path.

        Default: the immediate parent directory name under the store.
        Override for agents that use flat or encoded directory names.
        """
        stores = self.session_store_path
        if isinstance(stores, Path):
            stores = [stores]
        for store in stores:
            store = Path(store).expanduser()
            try:
                rel = jsonl_path.relative_to(store)
                return rel.parts[0] if rel.parts else jsonl_path.parent.name
            except ValueError:
                continue
        return jsonl_path.parent.name

    def is_subagent(self, jsonl_path: Path) -> bool:
        """Default: filenames or paths containing 'subagent' are sub-agent runs."""
        return "subagent" in jsonl_path.parts or "subagent" in jsonl_path.name

    def normalize_records(self, records: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Normalize agent-specific JSONL records into the shared Claude-style
        format that ``llmwiki.convert`` expects.

        The shared renderer expects records shaped as:
        - ``{"type": "user", "message": {"role": "user", "content": "..."}}``
        - ``{"type": "assistant", "message": {"role": "assistant", "content": [...]}}``

        The default implementation is a no-op (pass-through) — Claude Code
        sessions already use this format. Adapters for agents with a different
        schema (e.g. Codex CLI, Copilot) override this method to translate
        their native records into the shared shape.

        Called by ``convert.py`` after ``parse_jsonl()`` and before the
        renderer, so the normalization is transparent to the rest of the
        pipeline.
        """
        return records
