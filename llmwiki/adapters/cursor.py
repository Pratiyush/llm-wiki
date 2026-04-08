"""Cursor adapter.

Reads conversation history from Cursor IDE's local state.

Status: v0.2 initial implementation. Cursor stores chat history in an SQLite
database under ~/Library/Application Support/Cursor/User/workspaceStorage/
(macOS) or %APPDATA%\\Cursor\\User\\workspaceStorage\\ (Windows).

v0.2 scope:
- Detects Cursor install by checking the known paths
- Discovers workspace-level conversation stores
- Marks itself available if the paths exist
- Does NOT yet parse the SQLite records (v0.3 work once we have a real Cursor
  install to test against)

The adapter registers cleanly and is listed as "available: yes" if Cursor is
installed, so users know the scaffold is present. Full record parsing is
tracked in the v0.3 milestone.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from llmwiki.adapters import register
from llmwiki.adapters.base import BaseAdapter


@register("cursor")
class CursorAdapter(BaseAdapter):
    """Cursor IDE — reads chat history from ~/Library/Application Support/Cursor/"""

    SUPPORTED_SCHEMA_VERSIONS = ["v1"]  # to be pinned against a real Cursor install

    # Cursor stores per-workspace data under these roots
    DEFAULT_ROOTS = [
        # macOS
        Path.home() / "Library" / "Application Support" / "Cursor" / "User" / "workspaceStorage",
        # Linux
        Path.home() / ".config" / "Cursor" / "User" / "workspaceStorage",
        # Windows (via %APPDATA%) — Python expands %APPDATA% only via os.environ
        Path.home() / "AppData" / "Roaming" / "Cursor" / "User" / "workspaceStorage",
    ]

    # Known file patterns to match. Cursor stores conversation data in
    # SQLite (state.vscdb) per-workspace; v0.3 will add the SQLite parser.
    SESSION_FILE_PATTERNS = ["*.jsonl", "state.vscdb"]

    def __init__(self, config: dict[str, Any] | None = None):
        super().__init__(config)
        ad_cfg = (config or {}).get("adapters", {}).get("cursor", {})
        paths = ad_cfg.get("roots") or []
        self.roots: list[Path] = (
            [Path(p).expanduser() for p in paths] if paths else self.DEFAULT_ROOTS
        )

    @property
    def session_store_path(self):  # type: ignore[override]
        return self.roots

    @classmethod
    def is_available(cls) -> bool:
        for p in cls.DEFAULT_ROOTS:
            if Path(p).expanduser().exists():
                return True
        return False

    def discover_sessions(self) -> list[Path]:
        """Find every conversation file under every configured root.

        v0.2 returns .jsonl files (if any exist — some Cursor builds export
        chat history as .jsonl). v0.3 will add SQLite state.vscdb parsing.
        """
        out: list[Path] = []
        for root in self.roots:
            root = Path(root).expanduser()
            if not root.exists():
                continue
            for pattern in self.SESSION_FILE_PATTERNS:
                out.extend(sorted(root.rglob(pattern)))
        # De-dupe while preserving order
        seen: set[Path] = set()
        unique: list[Path] = []
        for p in out:
            if p not in seen:
                seen.add(p)
                unique.append(p)
        return unique

    def derive_project_slug(self, path: Path) -> str:
        """Cursor workspace directories are hashed; fall back to the hash as the
        slug. v0.3 will read workspace.json to get the friendly project name.
        """
        # Walk up to find the workspaceStorage/<hash>/ parent
        for root in self.roots:
            root = Path(root).expanduser()
            try:
                rel = path.relative_to(root)
                if rel.parts:
                    return f"cursor-{rel.parts[0][:12]}"
            except ValueError:
                continue
        return path.parent.name
