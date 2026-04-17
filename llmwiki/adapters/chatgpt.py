"""ChatGPT conversation-export adapter (v1.1 · #44).

ChatGPT doesn't write session files to disk like Claude Code or Codex.
Users must **export** their chat history from
https://chat.openai.com/settings → Data Controls → Export, then extract
the zip into a directory. This adapter reads `conversations.json` from
that export.

The export format is a JSON array of conversation objects::

    [
      {
        "title": "Debugging my FastAPI route",
        "create_time": 1730246400.0,
        "update_time": 1730250000.0,
        "mapping": {
          "<uuid>": {
            "id": "<uuid>",
            "message": {
              "author": {"role": "user"|"assistant"|"system"|"tool"},
              "content": {"parts": ["..."]} | {"content_type": "code", ...},
              "create_time": 1730246402.0
            },
            "parent": "<uuid>",
            "children": ["<uuid>"]
          }
        },
        "current_node": "<uuid>"
      },
      ...
    ]

Configuration (in ``sessions_config.json``)::

    "chatgpt": {
      "enabled": false,
      "export_dirs": ["~/Downloads/chatgpt-export"],
      "min_messages": 2
    }

Opt-in: disabled by default. Add ``"enabled": true`` and point
``export_dirs`` at the folder where you extracted the export zip.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator

from llmwiki.adapters import register
from llmwiki.adapters.base import BaseAdapter


@register("chatgpt")
class ChatGPTAdapter(BaseAdapter):
    """ChatGPT — parses conversations.json from a user's export."""

    SUPPORTED_SCHEMA_VERSIONS = ["v1"]

    DEFAULT_EXPORT_DIRS = [
        Path.home() / "Downloads" / "chatgpt-export",
    ]

    def __init__(self, config: dict[str, Any] | None = None):
        super().__init__(config)
        ad_cfg = (config or {}).get("chatgpt", {})
        self._enabled = ad_cfg.get("enabled", False)
        self._min_messages = int(ad_cfg.get("min_messages", 2))
        dirs = ad_cfg.get("export_dirs", [])
        if dirs:
            self._export_dirs = [Path(d).expanduser() for d in dirs]
        else:
            self._export_dirs = self.DEFAULT_EXPORT_DIRS

    @property
    def session_store_path(self):  # type: ignore[override]
        return self._export_dirs

    @classmethod
    def is_available(cls) -> bool:
        # Disabled by default — user must opt in via config
        return False

    def is_available_with_config(self) -> bool:
        if not self._enabled:
            return False
        return any(
            (d / "conversations.json").is_file() for d in self._export_dirs
        )

    def discover_sessions(self) -> list[Path]:
        """Each conversations.json file is one 'session-store'."""
        out: list[Path] = []
        for d in self._export_dirs:
            path = d / "conversations.json"
            if path.is_file():
                out.append(path)
        return out


# ─── Parsing ───────────────────────────────────────────────────────────


def _role(msg: dict[str, Any]) -> str:
    """Extract role from the message dict."""
    try:
        return msg["author"]["role"]
    except (KeyError, TypeError):
        return "unknown"


def _content_parts(msg: dict[str, Any]) -> list[str]:
    """Extract text parts from a message. ChatGPT exports can be nested."""
    content = msg.get("content", {})
    if not isinstance(content, dict):
        return []
    parts = content.get("parts", [])
    if not isinstance(parts, list):
        return []
    # Each part can be a string OR a dict with "text" or "image_url"
    out: list[str] = []
    for part in parts:
        if isinstance(part, str):
            out.append(part)
        elif isinstance(part, dict) and "text" in part:
            out.append(str(part["text"]))
    return out


def _linearize(conversation: dict[str, Any]) -> Iterator[dict[str, Any]]:
    """Follow the parent→children chain from `current_node` back to root,
    then yield messages in forward order."""
    mapping = conversation.get("mapping", {})
    current = conversation.get("current_node")
    if not current or not mapping:
        return

    # Walk up from current_node to collect the linear path
    chain: list[str] = []
    while current:
        chain.append(current)
        node = mapping.get(current, {})
        current = node.get("parent")
    chain.reverse()  # root → leaf

    for node_id in chain:
        node = mapping.get(node_id, {})
        msg = node.get("message")
        if not msg:
            continue
        yield msg


def parse_conversations_json(path: Path) -> list[dict[str, Any]]:
    """Read a conversations.json export and return a list of session dicts.

    Each session dict has: ``title``, ``created``, ``updated``, ``messages``
    (list of ``{role, text, created}``).
    """
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []

    if not isinstance(raw, list):
        return []

    sessions: list[dict[str, Any]] = []
    for conv in raw:
        if not isinstance(conv, dict):
            continue

        title = str(conv.get("title", "Untitled ChatGPT conversation"))
        created = conv.get("create_time")
        updated = conv.get("update_time")

        messages: list[dict[str, Any]] = []
        for msg in _linearize(conv):
            role = _role(msg)
            parts = _content_parts(msg)
            if not parts:
                continue
            msg_created = msg.get("create_time")
            messages.append({
                "role": role,
                "text": "\n".join(parts),
                "created": msg_created,
            })

        sessions.append({
            "title": title,
            "created": created,
            "updated": updated,
            "messages": messages,
        })

    return sessions


# ─── Markdown rendering ───────────────────────────────────────────────


def _fmt_ts(ts: Any) -> str:
    """Format a Unix timestamp as ISO date string; "" if unavailable."""
    if ts is None:
        return ""
    try:
        return datetime.fromtimestamp(float(ts), tz=timezone.utc).strftime("%Y-%m-%d")
    except (ValueError, TypeError, OSError):
        return ""


def render_conversation_markdown(session: dict[str, Any]) -> str:
    """Render a single ChatGPT conversation as frontmatter-tagged markdown."""
    title = session["title"]
    date_str = _fmt_ts(session.get("created")) or _fmt_ts(session.get("updated"))
    msg_count = len(session["messages"])

    # Collect unique roles
    roles = sorted({m["role"] for m in session["messages"] if m["role"] != "unknown"})

    fm = [
        "---",
        f'title: "{title}"',
        "type: source",
        "tags: [chatgpt, session-transcript]",
        f"date: {date_str}",
        "project: chatgpt",
        f"source: chatgpt-export",
        f"message_count: {msg_count}",
        f"roles: [{', '.join(roles)}]",
        "---",
        "",
        f"# {title}",
        "",
        f"**Messages:** {msg_count} · **Date:** {date_str or 'unknown'}",
        "",
        "## Conversation",
        "",
    ]

    for m in session["messages"]:
        role = m["role"].capitalize()
        fm.append(f"### {role}")
        fm.append("")
        # Indent text blocks for readability
        fm.append(m["text"])
        fm.append("")

    return "\n".join(fm)
