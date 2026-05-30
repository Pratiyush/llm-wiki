"""Build prompt-safe context from same-thread chat history."""

from __future__ import annotations

import re
from typing import Any, Iterable

from sqlalchemy.orm import Session

from llmwiki.web.models import ChatHistory

MAX_ROUNDS = 6
RECENT_FULL_ROUNDS = 2
RECENT_ANSWER_CHARS = 1200
OLDER_ANSWER_CHARS = 360

REFERENTIAL_TRIGGERS = (
    "\u4e0a\u4e00\u4e2a\u95ee\u9898",
    "\u521a\u624d",
    "\u7ee7\u7eed",
    "\u8fd9\u4e2a\u95ee\u9898",
    "\u8be5\u95ee\u9898",
    "\u524d\u9762",
    "\u4e0a\u4e00\u95ee",
    "\u8865\u5145",
)

_WIKILINK_RE = re.compile(r"\[\[([^\]|]+)(?:\|[^\]]*)?\]\]")


def _truncate(text: str, limit: int) -> str:
    text = (text or "").strip()
    if len(text) <= limit:
        return text
    return text[:limit].rstrip() + "..."


def extract_cited_sources(answer: str, *, limit: int = 8) -> list[str]:
    seen: set[str] = set()
    sources: list[str] = []
    for raw in _WIKILINK_RE.findall(answer or ""):
        source = raw.strip()
        if not source or source in seen:
            continue
        seen.add(source)
        sources.append(source)
        if len(sources) >= limit:
            break
    return sources


def is_referential_question(question: str) -> bool:
    normalized = (question or "").strip()
    return any(trigger in normalized for trigger in REFERENTIAL_TRIGGERS)


def _record_value(record: Any, key: str) -> Any:
    if isinstance(record, dict):
        return record.get(key)
    return getattr(record, key, None)


def format_history_records(records: Iterable[Any], current_question: str) -> str:
    rows = list(records)[-MAX_ROUNDS:]
    if not rows:
        return ""

    older = rows[:-RECENT_FULL_ROUNDS] if len(rows) > RECENT_FULL_ROUNDS else []
    recent = rows[-RECENT_FULL_ROUNDS:]

    lines = [
        "## Current conversation context",
        "The following content comes from prior Q&A in the same thread. Use it only to resolve references in the current question.",
        "",
    ]

    if is_referential_question(current_question):
        lines.extend(
            [
                "### Current thread topic",
                "The current question may refer to recent turns. Interpret it with the full meaning of the latest user question.",
                "",
            ]
        )

    if recent:
        lines.append("### Recent Q&A")
        for record in recent:
            lines.append(f"User: {_truncate(str(_record_value(record, 'question') or ''), 1000)}")
            lines.append(f"Assistant: {_truncate(str(_record_value(record, 'answer') or ''), RECENT_ANSWER_CHARS)}")
            lines.append("")

    if older:
        lines.append("### Older Q&A summary")
        for record in older:
            answer = str(_record_value(record, "answer") or "")
            sources = extract_cited_sources(answer)
            lines.append(f"User: {_truncate(str(_record_value(record, 'question') or ''), 1000)}")
            lines.append(f"Assistant summary: {_truncate(answer, OLDER_ANSWER_CHARS)}")
            if sources:
                lines.append("Cited sources: " + ", ".join(f"[[{source}]]" for source in sources))
            lines.append("")

    return "\n".join(lines).strip()


def build_conversation_context(
    db: Session,
    *,
    user_id: int | None,
    notebook_id: int | None,
    thread_id: int | None,
    current_question: str,
) -> str:
    if not user_id or not notebook_id or not thread_id:
        return ""

    records = (
        db.query(ChatHistory)
        .filter(
            ChatHistory.user_id == user_id,
            ChatHistory.notebook_id == notebook_id,
            ChatHistory.thread_id == thread_id,
        )
        .order_by(ChatHistory.created_at.desc())
        .limit(MAX_ROUNDS)
        .all()
    )
    return format_history_records(list(reversed(records)), current_question)
