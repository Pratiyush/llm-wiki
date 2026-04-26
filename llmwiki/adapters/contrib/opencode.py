"""OpenCode / OpenClaw adapter (v1.1 · #43).

OpenCode (sst/opencode) and OpenClaw (the community fork) are open-source
terminal AI coding agents. They write session transcripts to the
platform-specific app config directory:

- macOS:   ~/Library/Application Support/opencode/sessions/
           ~/Library/Application Support/openclaw/sessions/
- Linux:   ~/.config/opencode/sessions/
           ~/.config/openclaw/sessions/
- Windows: %APPDATA%/opencode/sessions/
           %APPDATA%/openclaw/sessions/

Session files are `*.jsonl` (one JSON object per line) with a schema
similar enough to Claude Code that the shared renderer in
``llmwiki.convert`` works after a light normalization pass.

The adapter registers as available when either `opencode/` or
`openclaw/` session-store directory exists. Per-record normalization
happens in ``normalize_records()`` which maps OpenCode's top-level
``role`` / ``content`` fields onto the Claude-style
``{type: user|assistant, message: {role: ..., content: ...}}`` shape
that the renderer expects.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from llmwiki.adapters import register
from llmwiki.adapters.base import BaseAdapter


@register("opencode")
class OpenCodeAdapter(BaseAdapter):
    """OpenCode / OpenClaw — shared adapter (both use identical schema)."""

    SUPPORTED_SCHEMA_VERSIONS = ["v1"]

    DEFAULT_ROOTS = [
        # macOS
        Path.home() / "Library" / "Application Support" / "opencode" / "sessions",
        Path.home() / "Library" / "Application Support" / "openclaw" / "sessions",
        # Linux (XDG default)
        Path.home() / ".config" / "opencode" / "sessions",
        Path.home() / ".config" / "openclaw" / "sessions",
        # Windows
        Path.home() / "AppData" / "Roaming" / "opencode" / "sessions",
        Path.home() / "AppData" / "Roaming" / "openclaw" / "sessions",
    ]

    def __init__(self, config: dict[str, Any] | None = None):
        super().__init__(config)
        ad_cfg = (config or {}).get("adapters", {}).get("opencode", {})
        paths = ad_cfg.get("roots") or []
        self.roots: list[Path] = (
            [Path(p).expanduser() for p in paths] if paths else self.DEFAULT_ROOTS
        )

    @property
    def session_store_path(self):  # type: ignore[override]
        return self.roots

    # #496: is_available() inherited from BaseAdapter — temp instance
    # reads self.session_store_path (returns self.roots = DEFAULT_ROOTS
    # when no config override).

    def discover_sessions(self) -> list[Path]:
        """Return every .jsonl session file under every configured root."""
        out: list[Path] = []
        for root in self.roots:
            root = Path(root).expanduser()
            if not root.exists():
                continue
            out.extend(sorted(root.rglob("*.jsonl")))
        return out

    def derive_project_slug(self, jsonl_path: Path) -> str:
        """OpenCode files are typically ``<project>-<session-id>.jsonl`` or
        nested under ``<project>/<session-id>.jsonl``. Use parent dir if
        nested, else split on first dash of filename."""
        for root in self.roots:
            root = Path(root).expanduser()
            try:
                rel = jsonl_path.relative_to(root)
                # If nested: <project>/<session>.jsonl → project
                if len(rel.parts) > 1:
                    return rel.parts[0]
                # Flat: <project>-<session>.jsonl → left-of-first-dash
                stem = rel.stem
                if "-" in stem:
                    return stem.split("-", 1)[0]
                return stem[:16]
            except ValueError:
                continue
        return jsonl_path.parent.name

    def is_subagent(self, jsonl_path: Path) -> bool:
        """OpenCode marks subagent sessions with 'subagent' in the filename.

        #arch-m1 (#614): match the segment, not the substring. The
        previous `"subagent" in name` form would mis-classify a session
        whose user-supplied slug happens to contain the literal text
        "subagent" anywhere — same regression #406 fixed for the main
        adapter contract.
        """
        # Hyphen-bounded match — accepts the subagent identifier whether
        # it appears as a leading, trailing, or interior segment of a
        # `-`-delimited filename.
        import re
        return bool(re.search(r"(?:^|[-/])subagent(?:[-.]|$)", jsonl_path.name))

    def normalize_records(
        self, records: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        """Translate OpenCode/OpenClaw records into the shared Claude-style
        shape that ``llmwiki.convert.render_session_markdown`` expects.

        OpenCode shape (approximate, based on public docs)::

            {"role": "user",      "content": "string", "timestamp": "..."}
            {"role": "assistant", "content": "string or [{type, text|tool_use}]"}
            {"role": "tool",      "content": "tool result", "tool_call_id": "..."}

        Claude Code shape::

            {"type": "user",      "message": {"role": "user",      "content": "..."}}
            {"type": "assistant", "message": {"role": "assistant", "content": [...]}}

        Records already in Claude shape (have top-level ``type``) are
        passed through unchanged.
        """
        out: list[dict[str, Any]] = []
        for rec in records:
            if not isinstance(rec, dict):
                continue

            # Pass-through if already Claude-shaped
            if "type" in rec and "message" in rec:
                out.append(rec)
                continue

            role = rec.get("role")
            content = rec.get("content")
            if role is None or content is None:
                # Skip non-message records (metadata, session-init, etc.)
                out.append(rec)
                continue

            # Map tool role → user (tool results are user-side in Claude shape)
            claude_type = "user" if role in ("user", "tool", "system") else "assistant"

            normalized = {
                "type": claude_type,
                "message": {"role": role, "content": content},
            }
            # Preserve timestamp if present — converter uses it for sorting
            if "timestamp" in rec:
                normalized["timestamp"] = rec["timestamp"]
            if "sessionId" in rec:
                normalized["sessionId"] = rec["sessionId"]

            out.append(normalized)
        return out
