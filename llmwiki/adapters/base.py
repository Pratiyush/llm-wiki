"""Base class for session-store adapters.

An adapter knows two things about one coding agent:
  1. WHERE its .jsonl session transcripts live on disk
  2. HOW to discover them (walking the directory tree)

Everything else — record filtering, markdown rendering, redaction, state
tracking — is shared in `llmwiki.convert` and operates on the iterator this
class returns.
"""

from __future__ import annotations

import re as _re
from pathlib import Path
from typing import Any, Iterator

# #sec-7 (#551): project slugs flow into raw/ + site/ paths. The same
# sanitiser regex is used by build.py for project_slug rendering — keep
# them aligned. Anything outside [A-Za-z0-9._-] gets replaced with `_`,
# leading dots are stripped so the slug can't form a hidden directory.
_PROJECT_SLUG_RE = _re.compile(r"[^A-Za-z0-9._-]")


def _safe_project_slug(raw: str) -> str:
    """Drop path traversal + non-portable characters from a project slug."""
    s = _PROJECT_SLUG_RE.sub("_", raw)
    s = s.lstrip(".")
    return s or "unnamed"


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

    #: True if this adapter wraps an **AI coding-agent session store**
    #: (Claude Code, Codex CLI, Copilot, Cursor, Gemini, etc.).  False
    #: for adapters over user content (Obsidian vaults, Jira tickets,
    #: meeting transcripts, PDFs) — those are opt-in only so
    #: ``llmwiki sync`` never silently ingests non-session content.
    #: See #326.
    is_ai_session: bool = True

    #: #arch-m9 (#621): canonical declaration on BaseAdapter so subclasses
    #: don't redeclare with format drift (`["v1"]` vs `["v1.0"]` vs
    #: `["1.x"]`). Default is ``["v1"]`` — the schema version the
    #: built-in adapters target. Subclasses that consume a different
    #: agent-native format override (or extend) this list.
    SUPPORTED_SCHEMA_VERSIONS: list[str] = ["v1"]

    def __init__(self, config: dict[str, Any] | None = None):
        self.config = config or {}

    # ─── classmethods used by the registry + UI ────────────────────────

    # #py-l3 (#601): subclasses can override _DESCRIPTION_OVERRIDE so
    # `python3 -OO` (which strips __doc__) doesn't degrade the adapter
    # listing to bare class names. The default reads __doc__ where
    # available and falls back to a stable explicit string when not.
    _DESCRIPTION_OVERRIDE: str = ""

    @classmethod
    def description(cls) -> str:
        """One-line description shown in `llmwiki adapters`."""
        if cls._DESCRIPTION_OVERRIDE:
            return cls._DESCRIPTION_OVERRIDE
        if cls.__doc__:
            return cls.__doc__.split("\n")[0]
        return cls.__name__

    @classmethod
    def is_available(cls) -> bool:
        """True if the session store exists on this machine.

        #496: previously read ``cls.session_store_path`` directly. That
        worked for ``ClaudeCodeAdapter`` (class attribute) but returned
        the *property descriptor object* for the 8 contrib adapters
        which override ``session_store_path`` as a ``@property`` — so
        every contrib adapter had to re-implement its own
        ``is_available()`` classmethod reading ``cls.DEFAULT_ROOTS``.

        Fix: instantiate a config-less temp instance and read
        ``self.session_store_path`` through the same code path
        ``discover_sessions()`` uses. Both class-attribute and
        ``@property``-overriding patterns now flow through this single
        method; the 8 duplicate contrib overrides go away.

        Adapters with expensive ``__init__()`` should override this
        method directly, but no current adapter needs to.
        """
        try:
            inst = cls()
        except Exception:
            # Defensive: an adapter whose __init__ raises (e.g.
            # missing imports surfaced eagerly) is "unavailable" by
            # definition rather than crashing the whole `adapters`
            # listing.
            return False
        paths = inst.session_store_path
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

        #sec-7 (#551): the returned slug is used downstream as a path
        component (`raw/sessions/<slug>-...md`, `site/projects/<slug>.html`).
        A user whose session store contains a directory named `..` or
        `foo/bar` could traverse out of `raw/` or smuggle a sub-path.
        Sanitise via the same regex rule the rest of the build uses.
        """
        stores = self.session_store_path
        if isinstance(stores, Path):
            stores = [stores]
        raw = None
        for store in stores:
            store = Path(store).expanduser()
            try:
                rel = jsonl_path.relative_to(store)
                raw = rel.parts[0] if rel.parts else jsonl_path.parent.name
                break
            except ValueError:
                continue
        if raw is None:
            raw = jsonl_path.parent.name
        return _safe_project_slug(raw)

    def is_subagent(self, jsonl_path: Path) -> bool:
        """Default: no adapter has a sub-agent concept — only Claude Code does
        (#406). Subclasses that DO have sub-agents (currently only the
        Claude Code adapter) override this method.

        Why the default returned True for any path containing the substring
        "subagent": that was a holdover from a Claude-specific assumption
        when the adapter abstraction was introduced. It mis-tagged every
        session in any user project named e.g. ``subagent-runner``,
        demoting them on the project page and excluding them from session
        counts. Subclassing fixes the bug at the source.
        """
        return False

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
