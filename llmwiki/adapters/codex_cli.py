"""Codex CLI adapter (production — v0.5 fix #109).

Reads session transcripts from OpenAI's Codex CLI and normalizes the
Codex-native JSONL schema into the shared Claude-style format. v0.3 brings this adapter
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
        """Derive the project slug from the Codex session's recorded cwd.

        Codex CLI 0.118.0 stores sessions under date-bucketed directories
        (~/.codex/sessions/YYYY/MM/DD/rollout-*.jsonl), so the directory
        path itself is NOT the project identifier. Instead we read the
        session_meta record's `cwd` field and use its basename.

        Fallback: if the session has no cwd, use the directory name
        (which will be the DD date bucket — not great, but better than
        crashing).
        """
        import json

        # Try to read cwd from the session_meta record
        try:
            with open(path, encoding="utf-8", errors="replace") as f:
                for line in f:
                    try:
                        r = json.loads(line.strip())
                    except (ValueError, json.JSONDecodeError):
                        continue
                    if r.get("type") == "session_meta":
                        cwd = r.get("payload", {}).get("cwd", "")
                        if cwd:
                            # Use the basename of the working directory
                            return Path(cwd).name.lower().replace(" ", "-")
                    break  # session_meta is always the first record
        except OSError:
            pass

        # Fallback: use the parent directory name
        return path.parent.name


    def normalize_records(self, records: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Normalize Codex CLI records into the shared Claude-style format.

        Maps:
        - session_meta → sessionId, cwd, model metadata extraction
        - response_item(role=user, type=message) → user record
        - response_item(role=assistant, type=message) → assistant record
        - response_item(type=web_search_call) → tool_use record
        - event_msg(type=task_started) → turn boundary (triggers slug)
        - Everything else → skipped gracefully
        """
        out: list[dict[str, Any]] = []

        # Extract session metadata first
        session_id = ""
        cwd = ""
        model = ""
        for r in records:
            if r.get("type") == "session_meta":
                p = r.get("payload", {})
                session_id = p.get("id", "")
                cwd = p.get("cwd", "")

        for r in records:
            rtype = r.get("type", "")
            payload = r.get("payload", {})
            ts = r.get("timestamp", "")

            if rtype == "session_meta":
                # Emit a synthetic init record with metadata
                out.append({
                    "type": "init",
                    "sessionId": session_id,
                    "cwd": cwd,
                    "timestamp": ts,
                })
                continue

            if rtype == "turn_context":
                model = payload.get("model", model)
                continue

            if rtype == "response_item":
                role = payload.get("role", "")
                item_type = payload.get("type", "")
                content_blocks = payload.get("content", [])

                if role == "user" and item_type == "message":
                    # Extract text from content blocks
                    text_parts = []
                    for block in (content_blocks if isinstance(content_blocks, list) else []):
                        if isinstance(block, dict) and block.get("type") == "input_text":
                            text_parts.append(block.get("text", ""))
                        elif isinstance(block, str):
                            text_parts.append(block)
                    text = "\n".join(text_parts).strip()
                    if text:
                        out.append({
                            "type": "user",
                            "message": {"role": "user", "content": text},
                            "timestamp": ts,
                        })
                    continue

                if role == "assistant" and item_type == "message":
                    text_parts = []
                    for block in (content_blocks if isinstance(content_blocks, list) else []):
                        if isinstance(block, dict) and block.get("type") == "output_text":
                            text_parts.append({"type": "text", "text": block.get("text", "")})
                        elif isinstance(block, str):
                            text_parts.append({"type": "text", "text": block})
                    if text_parts:
                        out.append({
                            "type": "assistant",
                            "message": {
                                "role": "assistant",
                                "content": text_parts,
                                "model": model,
                            },
                            "timestamp": ts,
                        })
                    continue

                if role == "developer":
                    # System/developer prompt — skip (context, not conversation)
                    continue

                if item_type == "web_search_call":
                    out.append({
                        "type": "assistant",
                        "message": {
                            "role": "assistant",
                            "content": [{
                                "type": "tool_use",
                                "name": "WebSearch",
                                "input": {"query": payload.get("query", "")},
                            }],
                        },
                        "timestamp": ts,
                    })
                    continue

                if item_type == "reasoning":
                    # Thinking block — skip by default (matches Claude config)
                    continue

            if rtype == "event_msg":
                # Turn lifecycle events — mostly metadata, not conversation
                continue

            # Unknown record type — skip gracefully (never crash)

        return out

    def is_subagent(self, path: Path) -> bool:
        return "subagent" in path.name or "agent-" in path.name
