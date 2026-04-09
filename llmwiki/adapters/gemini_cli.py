"""Gemini CLI adapter.

Reads conversation history from Google's Gemini CLI.

Status: v0.3 initial implementation. Gemini CLI stores sessions under
~/.gemini/ (exact layout TBC against a real install). The adapter detects
the directory and discovers .jsonl / .json files inside.

Registers as "available" if any of the known Gemini CLI paths exist.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from llmwiki.adapters import register
from llmwiki.adapters.base import BaseAdapter


@register("gemini_cli")
class GeminiCliAdapter(BaseAdapter):
    """Gemini CLI — reads ~/.gemini/ session history"""

    SUPPORTED_SCHEMA_VERSIONS = ["v1"]

    DEFAULT_ROOTS = [
        # macOS / Linux / Windows (dot-dir works everywhere)
        Path.home() / ".gemini",
        # Linux (XDG)
        Path.home() / ".config" / "gemini",
        Path.home() / ".local" / "share" / "gemini",
        # Windows (%APPDATA%)
        Path.home() / "AppData" / "Roaming" / "gemini",
    ]

    def __init__(self, config: dict[str, Any] | None = None):
        super().__init__(config)
        ad_cfg = (config or {}).get("adapters", {}).get("gemini_cli", {})
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
        out: list[Path] = []
        for root in self.roots:
            root = Path(root).expanduser()
            if not root.exists():
                continue
            # Look for both .jsonl and .json (Gemini CLI format TBC)
            out.extend(sorted(root.rglob("*.jsonl")))
            out.extend(sorted(root.rglob("chat-*.json")))
            out.extend(sorted(root.rglob("session-*.json")))
        return out

    def derive_project_slug(self, path: Path) -> str:
        # Gemini CLI doesn't have an obvious project encoding yet; use the
        # parent directory name
        for root in self.roots:
            root = Path(root).expanduser()
            try:
                rel = path.relative_to(root)
                return f"gemini-{rel.parts[0].lower()}" if rel.parts else "gemini-root"
            except ValueError:
                continue
        return f"gemini-{path.parent.name.lower()}"
