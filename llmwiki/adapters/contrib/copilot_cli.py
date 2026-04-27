"""GitHub Copilot CLI adapter.

Reads session event logs from the Copilot CLI's local state directory.

Copilot CLI stores per-session event logs under:
    ~/.copilot/session-state/<session-id>/events.jsonl

The COPILOT_HOME environment variable, when set, overrides the default
~/.copilot base directory.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from llmwiki.adapters import register
from llmwiki.adapters.base import BaseAdapter


def _build_default_roots() -> list[Path]:
    """Build DEFAULT_ROOTS, incorporating COPILOT_HOME if set."""
    home = Path.home()
    roots: list[Path] = [
        home / ".copilot" / "session-state",
    ]
    copilot_home = os.environ.get("COPILOT_HOME")
    if copilot_home:
        roots.append(Path(copilot_home).expanduser() / "session-state")
    return roots


@register("copilot_cli", aliases=["copilot-cli"])
class CopilotCliAdapter(BaseAdapter):
    """GitHub Copilot CLI — reads ~/.copilot/session-state/*/events.jsonl.

    #arch-l5 (#626): canonical name is ``copilot_cli`` (snake_case,
    matching every other adapter). The kebab-case ``copilot-cli`` is
    kept as a REGISTRY alias and still recognised in
    ``sessions_config.json`` so existing user configs don't break.
    """

    # #arch-m9 (#621): SUPPORTED_SCHEMA_VERSIONS = ["v1"] is the
    # BaseAdapter default — declaration removed here.

    DEFAULT_ROOTS: list[Path] = _build_default_roots()

    def __init__(self, config: dict[str, Any] | None = None):
        super().__init__(config)
        adapters_cfg = (config or {}).get("adapters", {}) or {}
        # #626: read snake_case config first; fall back to legacy
        # kebab-case so existing sessions_config.json keeps working.
        ad_cfg = adapters_cfg.get("copilot_cli") or adapters_cfg.get("copilot-cli") or {}
        paths = ad_cfg.get("roots") or []
        self.roots: list[Path] = (
            [Path(p).expanduser() for p in paths] if paths else self.DEFAULT_ROOTS
        )

    @property
    def session_store_path(self):  # type: ignore[override]
        return self.roots

    # #496: kept as an explicit override because it has special
    # COPILOT_HOME env-var handling that BaseAdapter.is_available()
    # (which only checks self.session_store_path) doesn't cover. The
    # base impl is still reachable via super().is_available() if the
    # env-var check fails.
    @classmethod
    def is_available(cls) -> bool:
        for p in cls.DEFAULT_ROOTS:
            if Path(p).expanduser().exists():
                return True
        # Also check COPILOT_HOME at call time (may be set after import)
        copilot_home = os.environ.get("COPILOT_HOME")
        if copilot_home:
            p = Path(copilot_home).expanduser() / "session-state"
            if p.exists():
                return True
        return False

    def discover_sessions(self) -> list[Path]:
        """Find events.jsonl files under each session-id directory."""
        out: list[Path] = []
        for root in self.roots:
            root = Path(root).expanduser()
            if not root.exists():
                continue
            # Walk <root>/<session-id>/events.jsonl
            out.extend(sorted(root.glob("*/events.jsonl")))
        # De-dupe while preserving order
        seen: set[Path] = set()
        unique: list[Path] = []
        for p in out:
            if p not in seen:
                seen.add(p)
                unique.append(p)
        return unique

    def derive_project_slug(self, path: Path) -> str:
        """Use the session-id directory name as the project slug.

        Layout: <root>/<session-id>/events.jsonl
        The session-id directory is the immediate parent of events.jsonl.
        """
        for root in self.roots:
            root = Path(root).expanduser()
            try:
                rel = path.relative_to(root)
                if rel.parts:
                    return rel.parts[0]
            except ValueError:
                continue
        # Fallback: use the parent directory name
        return path.parent.name
