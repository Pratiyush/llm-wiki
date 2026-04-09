"""VS Code Copilot Chat adapter.

Reads conversation history from the GitHub Copilot Chat extension's local
storage in VS Code, VS Code Insiders, and VSCodium.

Copilot Chat stores per-workspace conversation files under:
    <editor-data>/User/workspaceStorage/<hash>/chatSessions/*.jsonl
    <editor-data>/User/workspaceStorage/<hash>/chatSessions/*.json

where <editor-data> is platform- and editor-variant-specific:
    macOS:   ~/Library/Application Support/<editor>/
    Linux:   ~/.config/<editor>/
    Windows: %APPDATA%/<editor>/

Supported editor variants: Code, Code - Insiders, VSCodium.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from llmwiki.adapters import register
from llmwiki.adapters.base import BaseAdapter

# Editor directory names for each VS Code variant.
_EDITOR_DIRS = ["Code", "Code - Insiders", "VSCodium"]


def _build_default_roots() -> list[Path]:
    """Build the full cross-platform DEFAULT_ROOTS list at import time."""
    home = Path.home()
    roots: list[Path] = []
    for editor in _EDITOR_DIRS:
        # macOS
        roots.append(home / "Library" / "Application Support" / editor / "User" / "workspaceStorage")
        # Linux
        roots.append(home / ".config" / editor / "User" / "workspaceStorage")
        # Windows
        roots.append(home / "AppData" / "Roaming" / editor / "User" / "workspaceStorage")
    return roots


@register("copilot-chat")
class CopilotChatAdapter(BaseAdapter):
    """GitHub Copilot Chat — reads VS Code workspaceStorage chatSessions"""

    SUPPORTED_SCHEMA_VERSIONS = ["v1"]

    DEFAULT_ROOTS: list[Path] = _build_default_roots()

    # File patterns inside chatSessions/ subdirectories.
    SESSION_FILE_PATTERNS = ["*.jsonl", "*.json"]

    def __init__(self, config: dict[str, Any] | None = None):
        super().__init__(config)
        ad_cfg = (config or {}).get("adapters", {}).get("copilot-chat", {})
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
        """Find chatSessions/*.jsonl and *.json under each workspace hash dir."""
        out: list[Path] = []
        for root in self.roots:
            root = Path(root).expanduser()
            if not root.exists():
                continue
            # Walk <root>/<hash>/chatSessions/<file>
            for pattern in self.SESSION_FILE_PATTERNS:
                glob_pattern = os.path.join("*", "chatSessions", pattern)
                out.extend(sorted(root.glob(glob_pattern)))
        # De-dupe while preserving order
        seen: set[Path] = set()
        unique: list[Path] = []
        for p in out:
            if p not in seen:
                seen.add(p)
                unique.append(p)
        return unique

    def derive_project_slug(self, path: Path) -> str:
        """Derive a slug from the workspace hash directory.

        The chatSessions/ files live at:
            <root>/<workspace-hash>/chatSessions/<file>
        We use the workspace hash (parent of chatSessions/) as the slug,
        truncated to 12 chars and prefixed with 'copilot-'.
        """
        # Try to find the workspace hash dir — should be the parent of chatSessions/
        for root in self.roots:
            root = Path(root).expanduser()
            try:
                rel = path.relative_to(root)
                if rel.parts:
                    return f"copilot-{rel.parts[0][:12]}"
            except ValueError:
                continue
        # Fallback: walk up from the file to find the chatSessions parent
        if path.parent.name == "chatSessions":
            return f"copilot-{path.parent.parent.name[:12]}"
        return f"copilot-{path.parent.name[:12]}"
