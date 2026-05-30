# Conversation Follow-ups Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make same-thread follow-up questions and re-asks carry useful prior Q&A context into every Q&A mode.

**Architecture:** Add a focused `conversation_context` service that turns server-side `ChatHistory` rows into a compact prompt block. Route handlers resolve the current notebook/user/thread, build this block best-effort, and pass it to `glm_client.ask()`, `ask_stream()`, and `ask_agent()`. The frontend keeps re-asks in the current thread instead of clearing `threadId`.

**Tech Stack:** FastAPI routes, SQLAlchemy models, pytest, existing browser JavaScript without a JS test runner.

---

## File Map

- Create `llmwiki/web/services/conversation_context.py`: pure context-building helpers plus DB-backed `build_conversation_context()`.
- Create `tests/test_conversation_context.py`: focused unit tests for context formatting, source extraction, reference detection, and access scoping.
- Modify `llmwiki/web/services/glm_client.py`: add optional `conversation_context` arguments and prompt insertion.
- Modify `llmwiki/web/routes/query.py`: replace `_build_thread_history()` usage with the new builder and pass context to all Q&A paths.
- Modify `tests/test_notebook_query_scope.py`: extend route integration tests so `ask`, `stream`, and `agent` pass conversation context.
- Modify `llmwiki/web/static/components/qa.js`: stop resetting `threadId` in `reAsk()`.
- Create `tests/test_qa_js_behavior.py`: static regression test that `reAsk()` does not clear `threadId`.

## Task 1: Conversation Context Service

**Files:**
- Create: `llmwiki/web/services/conversation_context.py`
- Create: `tests/test_conversation_context.py`

- [ ] **Step 1: Write failing service tests**

Create `tests/test_conversation_context.py`:

```python
from __future__ import annotations

from datetime import datetime, timedelta


def test_extract_cited_sources_dedupes_in_order():
    from llmwiki.web.services.conversation_context import extract_cited_sources

    answer = "See [[PPP Contract]] and [[Articles]]. Also [[PPP Contract]]."

    assert extract_cited_sources(answer) == ["PPP Contract", "Articles"]


def test_referential_question_detection_uses_chinese_triggers():
    from llmwiki.web.services.conversation_context import is_referential_question

    assert is_referential_question("\u5bf9\u4e8e\u4e0a\u4e00\u4e2a\u95ee\u9898\uff0c\u8bf7\u6269\u5927\u68c0\u7d22\u8303\u56f4")
    assert is_referential_question("\u521a\u624d\u7684\u7b54\u6848\u4e0d\u5168\u9762\uff0c\u7ee7\u7eed\u5206\u6790")
    assert not is_referential_question("\u8bf7\u8bf4\u660ePPP\u5408\u540c\u5ba1\u6279\u6d41\u7a0b")


def test_format_history_keeps_recent_rounds_fuller_and_older_sources():
    from llmwiki.web.services.conversation_context import format_history_records

    base = datetime(2026, 5, 30, 9, 0, 0)
    records = []
    for i in range(1, 7):
        records.append(
            {
                "question": f"question {i}",
                "answer": f"answer {i} " + ("x" * 600) + f" [[Source{i}]]",
                "created_at": base + timedelta(minutes=i),
            }
        )

    context = format_history_records(records, "\u5bf9\u4e8e\u4e0a\u4e00\u4e2a\u95ee\u9898\uff0c\u7ee7\u7eed")

    assert "## Current conversation context" in context
    assert "### Current thread topic" in context
    assert "### Recent Q&A" in context
    assert "User: question 5" in context
    assert "User: question 6" in context
    assert "### Older Q&A summary" in context
    assert "User: question 1" in context
    assert "Cited sources: [[Source1]]" in context
    assert context.index("User: question 1") < context.index("User: question 6")


def test_format_history_omits_topic_for_standalone_question():
    from llmwiki.web.services.conversation_context import format_history_records

    context = format_history_records(
        [{"question": "old q", "answer": "old a [[Doc]]"}],
        "\u8bf7\u8bf4\u660e\u5408\u540c\u5ba1\u6279",
    )

    assert "## Current conversation context" in context
    assert "### Current thread topic" not in context
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
pytest tests/test_conversation_context.py -q
```

Expected: FAIL with `ModuleNotFoundError` or missing functions.

- [ ] **Step 3: Implement the service helpers**

Create `llmwiki/web/services/conversation_context.py`:

```python
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run:

```bash
pytest tests/test_conversation_context.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add llmwiki/web/services/conversation_context.py tests/test_conversation_context.py
git commit -m "feat: build conversation context"
```

## Task 2: LLM Client Prompt Integration

**Files:**
- Modify: `llmwiki/web/services/glm_client.py`
- Test: `tests/test_conversation_context.py`

- [ ] **Step 1: Add failing prompt tests**

Append to `tests/test_conversation_context.py`:

```python
def test_build_messages_puts_conversation_before_wiki_context(monkeypatch):
    import llmwiki.web.services.glm_client as glm

    monkeypatch.setattr(glm, "build_context", lambda question, wiki_dir=None: "WIKI CONTEXT")

    messages = glm._build_ask_messages(
        "current question",
        conversation_context="THREAD CONTEXT",
        wiki_dir=None,
    )

    system = messages[0]["content"]
    assert system.index("THREAD CONTEXT") < system.index("WIKI CONTEXT")
    assert messages[1] == {"role": "user", "content": "current question"}


def test_build_agent_system_content_includes_conversation_before_preload(monkeypatch):
    import llmwiki.web.services.glm_client as glm

    monkeypatch.setattr(glm, "_preload_context", lambda question, wiki_dir=None: "PRELOADED WIKI")

    content = glm._build_agent_system_content(
        "current question",
        conversation_context="THREAD CONTEXT",
        wiki_dir=None,
    )

    assert content.index("THREAD CONTEXT") < content.index("PRELOADED WIKI")
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
pytest tests/test_conversation_context.py::test_build_messages_puts_conversation_before_wiki_context tests/test_conversation_context.py::test_build_agent_system_content_includes_conversation_before_preload -q
```

Expected: FAIL because helper functions do not exist.

- [ ] **Step 3: Add prompt helper functions and arguments**

Modify `llmwiki/web/services/glm_client.py`:

```python
def _conversation_context_section(conversation_context: str | None) -> str:
    if not conversation_context:
        return ""
    return "\n---\nConversation context:\n" + conversation_context.strip() + "\n---"


def _build_ask_messages(
    question: str,
    *,
    model: str | None = None,
    conversation_context: str | None = None,
    wiki_dir: Path | None = None,
) -> list[dict[str, str]]:
    context = build_context(question, wiki_dir=wiki_dir)
    system = SYSTEM_PROMPT + _conversation_context_section(conversation_context)
    system += f"\n---\nWiki context:\n{context}\n---"
    return [
        {"role": "system", "content": system},
        {"role": "user", "content": question},
    ]
```

Change `ask()` signature and message construction:

```python
def ask(
    question: str,
    model: str | None = None,
    *,
    conversation_context: str | None = None,
    wiki_dir: Path | None = None,
) -> str:
    client, actual_model = _get_client_for_model(model or MODEL_FLASH)
    messages = _build_ask_messages(
        question,
        model=model,
        conversation_context=conversation_context,
        wiki_dir=wiki_dir,
    )
```

Change `ask_stream()` signature and message construction the same way:

```python
def ask_stream(
    question: str,
    model: str | None = None,
    *,
    conversation_context: str | None = None,
    wiki_dir: Path | None = None,
):
    client, actual_model = _get_client_for_model(model or MODEL_FLASH)
    messages = _build_ask_messages(
        question,
        model=model,
        conversation_context=conversation_context,
        wiki_dir=wiki_dir,
    )
```

Add agent system helper:

```python
def _build_agent_system_content(
    question: str,
    *,
    conversation_context: str | None = None,
    wiki_dir: Path | None = None,
) -> str:
    system_content = AGENT_SYSTEM_PROMPT
    if conversation_context:
        system_content += _conversation_context_section(conversation_context)
    preloaded_context = _preload_context(question, wiki_dir=wiki_dir)
    if preloaded_context:
        system_content += "\n\nInitial wiki search results; read full pages if needed:\n" + preloaded_context
    return system_content
```

Change `ask_agent()` signature:

```python
def ask_agent(
    question: str,
    model: str | None = None,
    conversation_history: str | None = None,
    *,
    conversation_context: str | None = None,
    wiki_dir: Path | None = None,
):
```

Replace the current manual `system_content` construction with:

```python
    effective_context = conversation_context or conversation_history
    system_content = _build_agent_system_content(
        question,
        conversation_context=effective_context,
        wiki_dir=wiki_dir,
    )
```

Keep `conversation_history` as a compatibility alias for now.

- [ ] **Step 4: Run prompt tests**

Run:

```bash
pytest tests/test_conversation_context.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add llmwiki/web/services/glm_client.py tests/test_conversation_context.py
git commit -m "feat: include thread context in prompts"
```

## Task 3: Route Integration for Ask, Stream, and Agent

**Files:**
- Modify: `llmwiki/web/routes/query.py`
- Modify: `tests/test_notebook_query_scope.py`

- [ ] **Step 1: Add failing ask integration test**

Update `test_ask_route_passes_selected_notebook_wiki_dir` in `tests/test_notebook_query_scope.py` so the body includes `thread_id`, and the fake LLM captures `conversation_context`:

```python
@pytest.mark.asyncio
async def test_ask_route_passes_selected_notebook_wiki_dir(monkeypatch, tmp_path):
    import llmwiki.web.routes.query as query

    wiki_dir = tmp_path / "notebooks" / "ai" / "wiki"
    captured = {}

    monkeypatch.setattr(
        query,
        "_resolve_query_notebook",
        lambda slug, token="": (SimpleNamespace(slug=slug, id=42), wiki_dir, SimpleNamespace(id=7)),
    )
    monkeypatch.setattr(
        query,
        "_build_context_for_thread",
        lambda *, token, thread_id, notebook_id, question: "THREAD CONTEXT",
    )

    def fake_ask(question, model=None, *, conversation_context=None, wiki_dir=None):
        captured["question"] = question
        captured["wiki_dir"] = wiki_dir
        captured["conversation_context"] = conversation_context
        return "scoped answer"

    monkeypatch.setattr("llmwiki.web.services.glm_client.ask", fake_ask)

    response = await query.ask({"question": "attention", "notebook_slug": "ai", "thread_id": 9, "token": "t"})

    assert response["answer"] == "scoped answer"
    assert response["notebook"] == "ai"
    assert captured == {
        "question": "attention",
        "wiki_dir": wiki_dir,
        "conversation_context": "THREAD CONTEXT",
    }
```

- [ ] **Step 2: Add stream and agent integration tests**

Append:

```python
def test_stream_route_passes_conversation_context(monkeypatch, tmp_path):
    import asyncio
    import llmwiki.web.routes.query as query

    wiki_dir = tmp_path / "wiki"
    captured = {}
    monkeypatch.setattr(
        query,
        "_resolve_query_notebook",
        lambda slug, token="": (SimpleNamespace(slug=slug, id=42), wiki_dir, SimpleNamespace(id=7)),
    )
    monkeypatch.setattr(
        query,
        "_build_context_for_thread",
        lambda *, token, thread_id, notebook_id, question: "THREAD CONTEXT",
    )

    def fake_stream(question, model=None, *, conversation_context=None, wiki_dir=None):
        captured["conversation_context"] = conversation_context
        captured["wiki_dir"] = wiki_dir
        yield "answer"

    monkeypatch.setattr("llmwiki.web.services.glm_client.ask_stream", fake_stream)

    response = asyncio.run(query.stream({"question": "q", "thread_id": 3, "token": "t", "notebook_slug": "ai"}))

    async def collect():
        return [chunk async for chunk in response.body_iterator]

    chunks = asyncio.run(collect())

    assert "data: answer\n\n" in chunks
    assert captured == {"conversation_context": "THREAD CONTEXT", "wiki_dir": wiki_dir}


def test_agent_route_passes_conversation_context(monkeypatch, tmp_path):
    import asyncio
    import json
    import llmwiki.web.routes.query as query

    wiki_dir = tmp_path / "wiki"
    captured = {}
    monkeypatch.setattr(query, "_user_from_token", lambda token: SimpleNamespace(id=7, role="admin"))
    monkeypatch.setattr(
        query,
        "_resolve_query_notebook",
        lambda slug, token="": (SimpleNamespace(slug=slug, id=42), wiki_dir, SimpleNamespace(id=7)),
    )
    monkeypatch.setattr(
        query,
        "_build_context_for_thread",
        lambda *, token, thread_id, notebook_id, question: "THREAD CONTEXT",
    )
    monkeypatch.setattr(query, "_save_chat_history", lambda *args, **kwargs: 3)

    def fake_agent(question, model=None, conversation_history=None, *, conversation_context=None, wiki_dir=None):
        captured["conversation_history"] = conversation_history
        captured["conversation_context"] = conversation_context
        captured["wiki_dir"] = wiki_dir
        yield json.dumps({"type": "done", "answer": "final"}, ensure_ascii=False)

    monkeypatch.setattr("llmwiki.web.services.glm_client.ask_agent", fake_agent)

    response = asyncio.run(query.agent_stream({"question": "q", "thread_id": 3, "token": "t", "notebook_slug": "ai"}))

    async def collect():
        return [chunk async for chunk in response.body_iterator]

    chunks = asyncio.run(collect())

    assert any('"answer": "final"' in chunk for chunk in chunks)
    assert captured == {
        "conversation_history": None,
        "conversation_context": "THREAD CONTEXT",
        "wiki_dir": wiki_dir,
    }
```

- [ ] **Step 3: Run tests to verify they fail**

Run:

```bash
pytest tests/test_notebook_query_scope.py::test_ask_route_passes_selected_notebook_wiki_dir tests/test_notebook_query_scope.py::test_stream_route_passes_conversation_context tests/test_notebook_query_scope.py::test_agent_route_passes_conversation_context -q
```

Expected: FAIL because `_build_context_for_thread` does not exist or routes do not pass `conversation_context`.

- [ ] **Step 4: Implement route helper and pass context**

In `llmwiki/web/routes/query.py`, add:

```python
def _build_context_for_thread(
    *,
    token: str,
    thread_id: int | str | None,
    notebook_id: int | None,
    question: str,
) -> str:
    if not token or not thread_id or notebook_id is None:
        return ""
    db = None
    try:
        resolved_thread_id = int(thread_id)
    except (TypeError, ValueError):
        return ""
    try:
        from llmwiki.web.database import SessionLocal
        from llmwiki.web.routes.auth import get_current_user
        from llmwiki.web.services.conversation_context import build_conversation_context

        db = SessionLocal()
        user = get_current_user(token=token, db=db)
        return build_conversation_context(
            db,
            user_id=user.id,
            notebook_id=notebook_id,
            thread_id=resolved_thread_id,
            current_question=question,
        )
    except Exception:
        return ""
    finally:
        if db:
            db.close()
```

In `ask()`, read `thread_id` and pass context:

```python
    thread_id = body.get("thread_id")
```

After resolving notebook:

```python
        conversation_context = _build_context_for_thread(
            token=token,
            thread_id=thread_id,
            notebook_id=notebook.id,
            question=question,
        )
        answer = glm_ask(
            question,
            model=model,
            conversation_context=conversation_context or None,
            wiki_dir=wiki_dir,
        )
```

In `stream()`, read `thread_id`, resolve notebook once in the generator, build context, and pass:

```python
            notebook, wiki_dir, _ = _resolve_query_notebook(notebook_slug, token)
            conversation_context = _build_context_for_thread(
                token=token,
                thread_id=thread_id,
                notebook_id=notebook.id,
                question=question,
            )
            from llmwiki.web.services.glm_client import ask_stream
            for chunk in ask_stream(
                question,
                model=model,
                conversation_context=conversation_context or None,
                wiki_dir=wiki_dir,
            ):
                yield f"data: {chunk}\n\n"
```

In `agent_stream()`, replace `_build_thread_history()` usage with:

```python
    conversation_context = ""
    if token and thread_id:
        try:
            resolved_thread_id = int(thread_id)
            notebook, _, _ = _resolve_query_notebook(notebook_slug, token)
            conversation_context = _build_context_for_thread(
                token=token,
                thread_id=resolved_thread_id,
                notebook_id=notebook.id,
                question=question,
            )
        except (ValueError, TypeError):
            pass
```

Call `ask_agent()` with:

```python
                question,
                model=model,
                conversation_context=conversation_context or None,
                wiki_dir=wiki_dir,
```

Leave `_build_thread_history()` in place only if other code still imports it; otherwise remove it after tests pass.

- [ ] **Step 5: Run route tests**

Run:

```bash
pytest tests/test_notebook_query_scope.py -q
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add llmwiki/web/routes/query.py tests/test_notebook_query_scope.py
git commit -m "feat: pass thread context through query routes"
```

## Task 4: Frontend Re-Ask Keeps Current Thread

**Files:**
- Modify: `llmwiki/web/static/components/qa.js`
- Create: `tests/test_qa_js_behavior.py`

- [ ] **Step 1: Add failing static JS regression test**

Create `tests/test_qa_js_behavior.py`:

```python
from __future__ import annotations

import re
from pathlib import Path


def _qa_js() -> str:
    return Path("llmwiki/web/static/components/qa.js").read_text(encoding="utf-8")


def test_reask_does_not_clear_current_thread():
    js = _qa_js()
    match = re.search(r"\n  reAsk\(question, model\) \{(?P<body>.*?)\n  \},", js, re.S)
    assert match, "QA.reAsk function not found"

    body = match.group("body")

    assert "this.threadId = null" not in body
    assert "this._updateThreadIndicator()" not in body
    assert "_sendAgent(question, model" in body
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
pytest tests/test_qa_js_behavior.py -q
```

Expected: FAIL because `reAsk()` currently clears `threadId`.

- [ ] **Step 3: Modify `QA.reAsk()`**

In `llmwiki/web/static/components/qa.js`, replace:

```javascript
  reAsk(question, model) {
    if (this.streaming) return;
    // Re-ask with a fresh thread - model comparison should be independent
    this.threadId = null;
    this._updateThreadIndicator();
    var msgEl = this.addMessage('assistant', '');
    var bubble = msgEl.querySelector('.msg-bubble');
    bubble.innerHTML = '<div class="agent-step agent-thinking">Re-answering with ' + model + '...</div>';
    this.messagesEl.scrollTop = this.messagesEl.scrollHeight;
    this._sendAgent(question, model, msgEl, bubble);
  },
```

with:

```javascript
  reAsk(question, model) {
    if (this.streaming) return;
    var msgEl = this.addMessage('assistant', '');
    var bubble = msgEl.querySelector('.msg-bubble');
    bubble.innerHTML = '<div class="agent-step agent-thinking">Re-answering in the current thread with ' + model + '...</div>';
    this.messagesEl.scrollTop = this.messagesEl.scrollHeight;
    this._sendAgent(question, model, msgEl, bubble);
  },
```

If the file currently contains mojibake text for Chinese UI strings, preserve the local style and only remove the two `threadId` reset lines plus the stale comment.

- [ ] **Step 4: Run frontend regression test**

Run:

```bash
pytest tests/test_qa_js_behavior.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add llmwiki/web/static/components/qa.js tests/test_qa_js_behavior.py
git commit -m "fix: keep re-asks in current thread"
```

## Task 5: End-to-End Verification and Cleanup

**Files:**
- Review: `llmwiki/web/services/conversation_context.py`
- Review: `llmwiki/web/services/glm_client.py`
- Review: `llmwiki/web/routes/query.py`
- Review: `llmwiki/web/static/components/qa.js`

- [ ] **Step 1: Run focused test suite**

Run:

```bash
pytest tests/test_conversation_context.py tests/test_notebook_query_scope.py tests/test_qa_js_behavior.py -q
```

Expected: all tests pass.

- [ ] **Step 2: Compile touched Python modules**

Run:

```bash
python -m compileall llmwiki/web/services/conversation_context.py llmwiki/web/services/glm_client.py llmwiki/web/routes/query.py
```

Expected: command exits 0.

- [ ] **Step 3: Inspect final diff**

Run:

```bash
git diff --stat HEAD
git status --short
```

Expected: no unstaged changes except any intentionally unrelated pre-existing untracked files.

- [ ] **Step 4: Manual prompt sanity check without network**

Run this by importing helper functions only:

```bash
python -c "from llmwiki.web.services.conversation_context import format_history_records; print(format_history_records([{'question':'PPP?','answer':'A [[Doc]]'}], '\u5bf9\u4e8e\u4e0a\u4e00\u4e2a\u95ee\u9898\uff0c\u7ee7\u7eed')[:200])"
```

Expected output starts with:

```text
## Current conversation context
```

- [ ] **Step 5: Final commit if cleanup changed files**

If Step 3 shows additional legitimate cleanup edits:

```bash
git add <changed-files>
git commit -m "test: verify conversation follow-up context"
```

If no files changed, do not create an empty commit.

## Self-Review Notes

- Spec coverage: Tasks cover the context service, prompt integration, all three Q&A routes, `reAsk()` behavior, security scoping, and tests.
- Phase boundary: Web page ingestion and URL citation support remain out of scope.
- Persistence: No schema migration or persistent summary table is introduced.
- Risk control: Context construction is deterministic and best-effort; model calls remain in existing LLM client paths.
