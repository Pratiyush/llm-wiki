"""GLM Q&A API with SSE streaming + conversation threads."""

from __future__ import annotations

import re
from datetime import date, datetime
from pathlib import Path

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from llmwiki import REPO_ROOT
from llmwiki.web.models import Notebook, User
from llmwiki.web.services.notebooks import (
    DEFAULT_NOTEBOOK_SLUG,
    can_access_notebook,
    ensure_default_notebook,
    notebook_wiki_dir,
    validate_notebook_slug,
)

router = APIRouter()

HISTORY_MAX_ROUNDS = 6  # max Q&A pairs to inject as context
CROSS_NOTEBOOK_DENIED = "跨知识库搜索仅管理员可用"


def _user_from_token(token: str) -> User | None:
    if not token:
        return None
    db = None
    try:
        from llmwiki.web.database import SessionLocal
        from llmwiki.web.routes.auth import get_current_user

        db = SessionLocal()
        return get_current_user(token=token, db=db)
    except Exception:
        return None
    finally:
        if db:
            db.close()


def _resolve_query_notebook(notebook_slug: str | None, token: str = "") -> tuple[Notebook, Path, User | None]:
    from fastapi import HTTPException
    from llmwiki.web.database import SessionLocal

    slug = notebook_slug or DEFAULT_NOTEBOOK_SLUG
    try:
        slug = validate_notebook_slug(slug)
    except ValueError:
        raise HTTPException(status_code=404, detail="notebook not found")

    db = None
    try:
        db = SessionLocal()
        default = ensure_default_notebook(db)
        notebook = default if slug == default.slug else db.query(Notebook).filter(Notebook.slug == slug).first()
        if notebook is None:
            raise HTTPException(status_code=404, detail="notebook not found")

        user = None
        if token:
            try:
                from llmwiki.web.routes.auth import get_current_user

                user = get_current_user(token=token, db=db)
            except Exception:
                user = None

        if not can_access_notebook(user, notebook):
            raise HTTPException(status_code=403, detail="notebook access denied")

        return notebook, notebook_wiki_dir(notebook.slug), user
    finally:
        if db:
            db.close()


@router.post("/ask")
async def ask(body: dict):
    """Ask a question with GLM API + wiki context."""
    question = body.get("question", "")
    model = body.get("model")
    token = body.get("token", "")
    notebook_slug = body.get("notebook_slug") or DEFAULT_NOTEBOOK_SLUG
    cross_notebook = bool(body.get("cross_notebook", False))

    if not question.strip():
        return {"answer": "请输入问题", "question": question}

    try:
        user = _user_from_token(token)
        if cross_notebook and (not user or user.role != "admin"):
            return {"answer": CROSS_NOTEBOOK_DENIED, "question": question}
        notebook, wiki_dir, _ = _resolve_query_notebook(notebook_slug, token)
        from llmwiki.web.services.glm_client import ask as glm_ask
        answer = glm_ask(question, model=model, wiki_dir=wiki_dir)
        return {"answer": answer, "question": question, "notebook": notebook.slug}
    except ValueError as e:
        return {"answer": f"配置错误: {e}", "question": question}
    except Exception as e:
        return {"answer": f"查询失败: {e}", "question": question}


@router.post("/stream")
async def stream(body: dict):
    """Stream Q&A response via SSE."""
    question = body.get("question", "")
    model = body.get("model")
    token = body.get("token", "")
    notebook_slug = body.get("notebook_slug") or DEFAULT_NOTEBOOK_SLUG
    cross_notebook = bool(body.get("cross_notebook", False))

    if not question.strip():
        def empty():
            yield 'data: 请输入问题\n\n'
            yield 'data: [DONE]\n\n'
        return StreamingResponse(empty(), media_type="text/event-stream")

    def generate():
        try:
            user = _user_from_token(token)
            if cross_notebook and (not user or user.role != "admin"):
                yield f"data: {CROSS_NOTEBOOK_DENIED}\n\n"
                yield "data: [DONE]\n\n"
                return
            _, wiki_dir, _ = _resolve_query_notebook(notebook_slug, token)
            from llmwiki.web.services.glm_client import ask_stream
            for chunk in ask_stream(question, model=model, wiki_dir=wiki_dir):
                yield f"data: {chunk}\n\n"
        except ValueError as e:
            yield f"data: 配置错误: {e}\n\n"
        except Exception as e:
            yield f"data: 查询失败: {e}\n\n"
        yield "data: [DONE]\n\n"

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.post("/agent")
async def agent_stream(body: dict):
    """Agent loop with tool calling via SSE. Supports thread-based follow-up."""
    question = body.get("question", "")
    model = body.get("model")
    token = body.get("token", "")
    thread_id = body.get("thread_id")  # optional: continue an existing thread
    notebook_slug = body.get("notebook_slug") or DEFAULT_NOTEBOOK_SLUG
    cross_notebook = bool(body.get("cross_notebook", False))

    if not question.strip():
        def empty():
            yield 'data: {"type": "error", "message": "请输入问题"}\n\n'
            yield 'data: [DONE]\n\n'
        return StreamingResponse(empty(), media_type="text/event-stream")

    # Resolve thread_id and build conversation history
    resolved_thread_id = None
    conversation_history = ""

    if token and thread_id:
        try:
            resolved_thread_id = int(thread_id)
            notebook, _, _ = _resolve_query_notebook(notebook_slug, token)
            conversation_history = _build_thread_history(
                token,
                resolved_thread_id,
                notebook_id=notebook.id,
            )
        except (ValueError, TypeError):
            pass

    def generate():
        import json as _json
        final_answer = ""
        notebook_id = None
        try:
            user = _user_from_token(token)
            if cross_notebook and (not user or user.role != "admin"):
                event = _json.dumps({"type": "error", "message": CROSS_NOTEBOOK_DENIED}, ensure_ascii=False)
                yield f"data: {event}\n\n"
                yield "data: [DONE]\n\n"
                return
            notebook, wiki_dir, _ = _resolve_query_notebook(notebook_slug, token)
            notebook_id = notebook.id
            from llmwiki.web.services.glm_client import ask_agent
            for event_json in ask_agent(
                question, model=model,
                conversation_history=conversation_history or None,
                wiki_dir=wiki_dir,
            ):
                yield f"data: {event_json}\n\n"
                try:
                    evt = _json.loads(event_json)
                    if evt.get("type") == "done" and evt.get("answer"):
                        final_answer = evt["answer"]
                except Exception:
                    pass
        except ValueError as e:
            yield f'data: {{"type": "error", "message": "配置错误: {e}"}}\n\n'
        except Exception as e:
            yield f'data: {{"type": "error", "message": "查询失败: {e}"}}\n\n'
        if final_answer:
            new_tid = _save_chat_history(token, question, final_answer, model or "",
                               thread_id=resolved_thread_id, notebook_id=notebook_id)
            if new_tid is not None:
                yield f'data: {{"type": "thread", "thread_id": {new_tid}}}\n\n'
        yield "data: [DONE]\n\n"

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.post("/save")
async def save_synthesis(body: dict):
    """Save a Q&A pair — leader/admin writes directly, staff submits for approval."""
    question = body.get("question", "未命名")
    answer = body.get("answer", "")
    token = body.get("token", "")
    notebook_slug = body.get("notebook_slug") or DEFAULT_NOTEBOOK_SLUG

    if not answer.strip():
        return {"status": "error", "message": "回答内容为空"}

    try:
        notebook, wiki_dir, _ = _resolve_query_notebook(notebook_slug, token)
    except Exception as e:
        return {"status": "error", "message": str(e)}

    user = None
    db_auth = None
    if token:
        try:
            from llmwiki.web.routes.auth import get_current_user
            from llmwiki.web.database import SessionLocal
            from fastapi.security import OAuth2PasswordBearer
            db_auth = SessionLocal()
            user = get_current_user(token=token, db=db_auth)
        except Exception:
            pass
        finally:
            if db_auth:
                db_auth.close()

    if user and user.role in ("leader", "admin"):
        path = _write_synthesis(question, answer, wiki_dir=wiki_dir)
        _mark_history_saved(token, question, answer, notebook_id=notebook.id)
        return {"status": "ok", "path": path, "mode": "direct", "notebook": notebook.slug}

    if user:
        from llmwiki.web.models import PendingWiki
        from llmwiki.web.database import SessionLocal
        db_pending = None
        try:
            db_pending = SessionLocal()
            slug = _slugify(question[:30])
            pending = PendingWiki(
                notebook_id=notebook.id,
                question=question[:500],
                answer=answer,
                slug=slug,
                proposer_id=user.id,
                department=user.department,
            )
            db_pending.add(pending)
            db_pending.commit()
            _mark_history_saved(token, question, answer, notebook_id=notebook.id)
            return {"status": "pending", "mode": "approval", "id": pending.id, "notebook": notebook.slug}
        finally:
            if db_pending:
                db_pending.close()

    path = _write_synthesis(question, answer, wiki_dir=wiki_dir)
    return {"status": "ok", "path": path, "mode": "direct", "notebook": notebook.slug}


def _save_chat_history(token: str, question: str, answer: str, model: str = "",
                       thread_id: int | None = None,
                       notebook_id: int | None = None) -> int | None:
    """Save a Q&A pair to chat_history, auto-creating a thread if none provided.
    Returns the thread_id."""
    if not token or not answer.strip():
        return None
    db = None
    try:
        from llmwiki.web.routes.auth import get_current_user
        from llmwiki.web.database import SessionLocal
        from llmwiki.web.models import ChatHistory, Conversation
        db = SessionLocal()
        user = get_current_user(token=token, db=db)

        if thread_id is not None:
            conv = db.query(Conversation).filter(
                Conversation.id == thread_id,
                Conversation.user_id == user.id,
                Conversation.notebook_id == notebook_id,
            ).first()
            if conv is None:
                thread_id = None

        # Auto-create thread if none provided or the supplied one is inaccessible.
        if thread_id is None:
            title = question[:80].replace("\n", " ").strip() or "新对话"
            conv = Conversation(user_id=user.id, title=title, notebook_id=notebook_id)
            db.add(conv)
            db.flush()
            thread_id = conv.id

        entry = ChatHistory(
            user_id=user.id,
            thread_id=thread_id,
            notebook_id=notebook_id,
            question=question[:2000],
            answer=answer,
            model=model,
        )
        db.add(entry)
        db.commit()
        return thread_id
    except Exception:
        return None
    finally:
        if db:
            db.close()


def _build_thread_history(token: str, thread_id: int, notebook_id: int | None = None) -> str:
    """Build conversation history text from the last N rounds of a thread."""
    db = None
    try:
        from llmwiki.web.routes.auth import get_current_user
        from llmwiki.web.database import SessionLocal
        from llmwiki.web.models import ChatHistory
        db = SessionLocal()
        user = get_current_user(token=token, db=db)
        records = (
            db.query(ChatHistory)
            .filter(
                ChatHistory.user_id == user.id,
                ChatHistory.thread_id == thread_id,
                ChatHistory.notebook_id == notebook_id,
            )
            .order_by(ChatHistory.created_at.desc())
            .limit(HISTORY_MAX_ROUNDS)
            .all()
        )
        records = list(reversed(records))
        if not records:
            return ""
        lines = []
        for r in records:
            lines.append(f"用户: {r.question}")
            # Truncate answers to keep context manageable (Chinese text has no spaces)
            answer_short = r.answer[:800] if len(r.answer) > 800 else r.answer
            lines.append(f"助手: {answer_short}")
        return "\n".join(lines)
    except Exception:
        return ""
    finally:
        if db:
            db.close()


def _mark_history_saved(token: str, question: str, answer: str, notebook_id: int | None = None):
    """Mark matching chat_history record as saved_to_wiki=True."""
    if not token:
        return
    db = None
    try:
        from llmwiki.web.routes.auth import get_current_user
        from llmwiki.web.database import SessionLocal
        from llmwiki.web.models import ChatHistory
        db = SessionLocal()
        user = get_current_user(token=token, db=db)
        record = db.query(ChatHistory).filter(
            ChatHistory.user_id == user.id,
            ChatHistory.question == question[:2000],
            ChatHistory.notebook_id == notebook_id,
        ).order_by(ChatHistory.created_at.desc()).first()
        if record:
            record.saved_to_wiki = True
            db.commit()
    except Exception:
        pass
    finally:
        if db:
            db.close()


# ── Thread / History endpoints ────────────────────────────────────────────

@router.get("/history")
async def get_history(token: str = "", notebook: str = DEFAULT_NOTEBOOK_SLUG):
    """Get chat history with thread grouping for the current user."""
    if not token:
        return {"history": [], "threads": []}
    db = None
    try:
        selected, _, _ = _resolve_query_notebook(notebook, token)
        from llmwiki.web.routes.auth import get_current_user
        from llmwiki.web.database import SessionLocal
        from llmwiki.web.models import ChatHistory, Conversation
        db = SessionLocal()
        user = get_current_user(token=token, db=db)

        # Get threads
        threads = (
            db.query(Conversation)
            .filter(
                Conversation.user_id == user.id,
                Conversation.notebook_id == selected.id,
            )
            .order_by(Conversation.created_at.desc())
            .all()
        )

        # Get all history records
        records = (
            db.query(ChatHistory)
            .filter(
                ChatHistory.user_id == user.id,
                ChatHistory.notebook_id == selected.id,
            )
            .order_by(ChatHistory.created_at.asc())
            .all()
        )

        return {
            "history": [
                {
                    "id": r.id,
                    "thread_id": r.thread_id,
                    "question": r.question,
                    "answer": r.answer,
                    "model": r.model,
                    "saved_to_wiki": bool(r.saved_to_wiki),
                    "created_at": r.created_at.strftime("%Y-%m-%d %H:%M") if r.created_at else "",
                }
                for r in records
            ],
            "threads": [
                {
                    "id": t.id,
                    "title": t.title,
                    "created_at": t.created_at.strftime("%Y-%m-%d %H:%M") if t.created_at else "",
                }
                for t in threads
            ],
        }
    except Exception:
        return {"history": [], "threads": []}
    finally:
        if db:
            db.close()


@router.delete("/history")
async def clear_history(token: str = "", notebook: str = DEFAULT_NOTEBOOK_SLUG):
    """Clear chat history for the current user."""
    if not token:
        return {"status": "error", "message": "未登录"}
    db = None
    try:
        selected, _, _ = _resolve_query_notebook(notebook, token)
        from llmwiki.web.routes.auth import get_current_user
        from llmwiki.web.database import SessionLocal
        from llmwiki.web.models import ChatHistory, Conversation
        db = SessionLocal()
        user = get_current_user(token=token, db=db)
        db.query(ChatHistory).filter(
            ChatHistory.user_id == user.id,
            ChatHistory.notebook_id == selected.id,
        ).delete()
        db.query(Conversation).filter(
            Conversation.user_id == user.id,
            Conversation.notebook_id == selected.id,
        ).delete()
        db.commit()
        return {"status": "ok"}
    except Exception as e:
        return {"status": "error", "message": str(e)}
    finally:
        if db:
            db.close()


@router.delete("/thread/{thread_id}")
async def delete_thread(thread_id: int, token: str = "", notebook: str = DEFAULT_NOTEBOOK_SLUG):
    """Delete a specific conversation thread and its messages."""
    if not token:
        return {"status": "error", "message": "未登录"}
    db = None
    try:
        selected, _, _ = _resolve_query_notebook(notebook, token)
        from llmwiki.web.routes.auth import get_current_user
        from llmwiki.web.database import SessionLocal
        from llmwiki.web.models import ChatHistory, Conversation
        db = SessionLocal()
        user = get_current_user(token=token, db=db)

        # Verify ownership
        conv = db.query(Conversation).filter(
            Conversation.id == thread_id,
            Conversation.user_id == user.id,
            Conversation.notebook_id == selected.id,
        ).first()
        if not conv:
            return {"status": "error", "message": "对话线程不存在"}

        db.query(ChatHistory).filter(
            ChatHistory.thread_id == thread_id,
            ChatHistory.user_id == user.id,
            ChatHistory.notebook_id == selected.id,
        ).delete()
        db.delete(conv)
        db.commit()
        return {"status": "ok"}
    except Exception as e:
        return {"status": "error", "message": str(e)}
    finally:
        if db:
            db.close()


# ── Thread messages / rename / fork ─────────────────────────────────────


@router.get("/messages")
async def get_thread_messages(thread_id: int, token: str = "", notebook: str = DEFAULT_NOTEBOOK_SLUG):
    """Get all messages for a specific thread (owner only)."""
    if not token:
        return {"messages": [], "title": ""}
    db = None
    try:
        selected, _, _ = _resolve_query_notebook(notebook, token)
        from llmwiki.web.routes.auth import get_current_user
        from llmwiki.web.database import SessionLocal
        from llmwiki.web.models import ChatHistory, Conversation
        db = SessionLocal()
        user = get_current_user(token=token, db=db)
        conv = db.query(Conversation).filter(
            Conversation.id == thread_id,
            Conversation.user_id == user.id,
            Conversation.notebook_id == selected.id,
        ).first()
        if not conv:
            return {"messages": [], "title": ""}
        records = (
            db.query(ChatHistory)
            .filter(
                ChatHistory.thread_id == thread_id,
                ChatHistory.user_id == user.id,
                ChatHistory.notebook_id == selected.id,
            )
            .order_by(ChatHistory.created_at.asc())
            .all()
        )
        return {
            "messages": [
                {
                    "id": r.id,
                    "question": r.question,
                    "answer": r.answer,
                    "model": r.model,
                    "created_at": r.created_at.strftime("%Y-%m-%d %H:%M") if r.created_at else "",
                }
                for r in records
            ],
            "title": conv.title,
        }
    except Exception:
        return {"messages": [], "title": ""}
    finally:
        if db:
            db.close()


@router.put("/thread/{thread_id}/rename")
async def rename_thread(thread_id: int, body: dict):
    """Rename a conversation thread (owner only)."""
    token = body.get("token", "")
    title = body.get("title", "").strip()
    notebook = body.get("notebook") or body.get("notebook_slug") or DEFAULT_NOTEBOOK_SLUG
    if not token:
        return {"status": "error", "message": "未登录"}
    if not title or len(title) > 200:
        return {"status": "error", "message": "标题无效"}
    db = None
    try:
        selected, _, _ = _resolve_query_notebook(notebook, token)
        from llmwiki.web.routes.auth import get_current_user
        from llmwiki.web.database import SessionLocal
        from llmwiki.web.models import Conversation
        db = SessionLocal()
        user = get_current_user(token=token, db=db)
        conv = db.query(Conversation).filter(
            Conversation.id == thread_id,
            Conversation.user_id == user.id,
            Conversation.notebook_id == selected.id,
        ).first()
        if not conv:
            return {"status": "error", "message": "对话线程不存在"}
        conv.title = title[:200]
        db.commit()
        return {"status": "ok"}
    except Exception as e:
        return {"status": "error", "message": str(e)}
    finally:
        if db:
            db.close()


def _write_synthesis(question: str, answer: str, *, wiki_dir: Path | None = None) -> str:
    """Write Q&A pair to wiki/syntheses/ and return the path."""
    slug = _slugify(question[:30])
    filename = f"{slug}.md"
    target_wiki = wiki_dir or (REPO_ROOT / "wiki")
    filepath = target_wiki / "syntheses" / filename
    filepath.parent.mkdir(parents=True, exist_ok=True)

    today = date.today().isoformat()
    content = f"""---
title: "{question[:60]}"
type: synthesis
tags: [问答]
last_updated: {today}
question: "{question[:100]}"
---

# {question}

{answer}
"""
    filepath.write_text(content, encoding="utf-8")

    log_path = target_wiki / "log.md"
    log_entry = f"\n## [{today}] query (web) | {question[:60]}\n"
    existing = log_path.read_text(encoding="utf-8") if log_path.exists() else ""
    log_path.write_text(existing + log_entry, encoding="utf-8")

    return f"syntheses/{filename}"


def _slugify(text: str) -> str:
    """Convert text to a filesystem-safe slug."""
    text = text.strip()
    text = re.sub(r'[\s]+', '-', text)
    text = re.sub(r'[^\w一-鿿-]', '', text)
    text = text.strip('-')
    return text[:50] if text else "unnamed"
