"""Codex CLI adapter.

Reads session transcripts from OpenAI's Codex CLI. v0.3 brings this adapter
from stub → production: it discovers session files, derives project slugs,
and declares its schema version. Record parsing goes through the shared
converter in llmwiki.convert with graceful degradation for unknown record
types.

Codex CLI stores sessions under:
- ~/.codex/sessions/
- ~/.codex/projects/ (alternate layout)

Both are checked. Users can override via config.json.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from llmwiki.adapters import register
from llmwiki.adapters.base import BaseAdapter


@register("codex_cli")
class CodexCliAdapter(BaseAdapter):
    """Codex CLI — reads ~/.codex/sessions/**/*.jsonl (v0.3 production)"""

    SUPPORTED_SCHEMA_VERSIONS = ["v0.x", "v1.0"]

    DEFAULT_ROOTS = [
        # Cross-platform: dot-dir works on macOS, Linux, and Windows
        Path.home() / ".codex" / "sessions",
        Path.home() / ".codex" / "projects",
    ]

    def __init__(self, config: dict[str, Any] | None = None):
        super().__init__(config)
        ad_cfg = (config or {}).get("adapters", {}).get("codex_cli", {})
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
            if root.exists():
                out.extend(sorted(root.rglob("*.jsonl")))
        # Dedupe
        seen: set[Path] = set()
        unique: list[Path] = []
        for p in out:
            if p not in seen:
                seen.add(p)
                unique.append(p)
        return unique

    def derive_project_slug(self, path: Path) -> str:
        """Walk up from the .jsonl to the nearest project directory.

        Codex CLI layouts vary — some use ~/.codex/sessions/<project>/<file>.jsonl,
        others use ~/.codex/projects/<hashed-path>/<file>.jsonl. We prefer the
        directory immediately under sessions/ or projects/, and strip the
        '-Users-...-draft-' prefix the same way the Claude Code adapter does.
        """
        for root in self.roots:
            root = Path(root).expanduser()
            try:
                rel = path.relative_to(root)
                if rel.parts:
                    parent = rel.parts[0]
                    if parent.startswith("-Users-") or parent.startswith("-home-"):
                        parts = parent.lstrip("-").split("-")
                        for marker in ("draft", "production", "Desktop", "workspace"):
                            if marker in parts:
                                idx = len(parts) - 1 - parts[::-1].index(marker)
                                tail = parts[idx + 1 :]
                                if tail:
                                    return "-".join(tail)
                        return "-".join(parts[-2:]) if len(parts) >= 2 else parent
                    return parent
            except ValueError:
                continue
        return path.parent.name

    def is_subagent(self, path: Path) -> bool:
        return "subagent" in path.name or "agent-" in path.name
