"""GLM Q&A API with SSE streaming + conversation threads."""

from __future__ import annotations

import re
from datetime import date, datetime

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from llmwiki import REPO_ROOT

router = APIRouter()

HISTORY_MAX_ROUNDS = 6  # max Q&A pairs to inject as context


@router.post("/ask")
async def ask(body: dict):
    """Ask a question with GLM API + wiki context."""
    question = body.get("question", "")
    model = body.get("model")

    if not question.strip():
        return {"answer": "请输入问题", "question": question}

    try:
        from llmwiki.web.services.glm_client import ask as glm_ask
        answer = glm_ask(question, model=model)
        return {"answer": answer, "question": question}
    except ValueError as e:
        return {"answer": f"配置错误: {e}", "question": question}
    except Exception as e:
        return {"answer": f"查询失败: {e}", "question": question}


@router.post("/stream")
async def stream(body: dict):
    """Stream Q&A response via SSE."""
    question = body.get("question", "")
    model = body.get("model")

    if not question.strip():
        def empty():
            yield 'data: 请输入问题\n\n'
            yield 'data: [DONE]\n\n'
        return StreamingResponse(empty(), media_type="text/event-stream")

    def generate():
        try:
            from llmwiki.web.services.glm_client import ask_stream
            for chunk in ask_stream(question, model=model):
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
            conversation_history = _build_thread_history(token, resolved_thread_id)
        except (ValueError, TypeError):
            pass

    def generate():
        import json as _json
        final_answer = ""
        try:
            from llmwiki.web.services.glm_client import ask_agent
            for event_json in ask_agent(
                question, model=model,
                conversation_history=conversation_history or None,
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
                               thread_id=resolved_thread_id)
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

    if not answer.strip():
        return {"status": "error", "message": "回答内容为空"}

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
        path = _write_synthesis(question, answer)
        _mark_history_saved(token, question, answer)
        return {"status": "ok", "path": path, "mode": "direct"}

    if user:
        from llmwiki.web.models import PendingWiki
        from llmwiki.web.database import SessionLocal
        db_pending = None
        try:
            db_pending = SessionLocal()
            slug = _slugify(question[:30])
            pending = PendingWiki(
                question=question[:500],
                answer=answer,
                slug=slug,
                proposer_id=user.id,
                department=user.department,
            )
            db_pending.add(pending)
            db_pending.commit()
            _mark_history_saved(token, question, answer)
            return {"status": "pending", "mode": "approval", "id": pending.id}
        finally:
            if db_pending:
                db_pending.close()

    path = _write_synthesis(question, answer)
    return {"status": "ok", "path": path, "mode": "direct"}


def _save_chat_history(token: str, question: str, answer: str, model: str = "",
                       thread_id: int | None = None) -> int | None:
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

        # Auto-create thread if none provided
        if thread_id is None:
            title = question[:80].replace("\n", " ").strip() or "新对话"
            conv = Conversation(user_id=user.id, title=title)
            db.add(conv)
            db.flush()
            thread_id = conv.id

        entry = ChatHistory(
            user_id=user.id,
            thread_id=thread_id,
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


def _build_thread_history(token: str, thread_id: int) -> str:
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


def _mark_history_saved(token: str, question: str, answer: str):
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
async def get_history(token: str = ""):
    """Get chat history with thread grouping for the current user."""
    if not token:
        return {"history": [], "threads": []}
    db = None
    try:
        from llmwiki.web.routes.auth import get_current_user
        from llmwiki.web.database import SessionLocal
        from llmwiki.web.models import ChatHistory, Conversation
        db = SessionLocal()
        user = get_current_user(token=token, db=db)

        # Get threads
        threads = (
            db.query(Conversation)
            .filter(Conversation.user_id == user.id)
            .order_by(Conversation.created_at.desc())
            .all()
        )

        # Get all history records
        records = (
            db.query(ChatHistory)
            .filter(ChatHistory.user_id == user.id)
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
async def clear_history(token: str = ""):
    """Clear chat history for the current user."""
    if not token:
        return {"status": "error", "message": "未登录"}
    db = None
    try:
        from llmwiki.web.routes.auth import get_current_user
        from llmwiki.web.database import SessionLocal
        from llmwiki.web.models import ChatHistory, Conversation
        db = SessionLocal()
        user = get_current_user(token=token, db=db)
        db.query(ChatHistory).filter(ChatHistory.user_id == user.id).delete()
        db.query(Conversation).filter(Conversation.user_id == user.id).delete()
        db.commit()
        return {"status": "ok"}
    except Exception as e:
        return {"status": "error", "message": str(e)}
    finally:
        if db:
            db.close()


@router.delete("/thread/{thread_id}")
async def delete_thread(thread_id: int, token: str = ""):
    """Delete a specific conversation thread and its messages."""
    if not token:
        return {"status": "error", "message": "未登录"}
    db = None
    try:
        from llmwiki.web.routes.auth import get_current_user
        from llmwiki.web.database import SessionLocal
        from llmwiki.web.models import ChatHistory, Conversation
        db = SessionLocal()
        user = get_current_user(token=token, db=db)

        # Verify ownership
        conv = db.query(Conversation).filter(
            Conversation.id == thread_id,
            Conversation.user_id == user.id,
        ).first()
        if not conv:
            return {"status": "error", "message": "对话线程不存在"}

        db.query(ChatHistory).filter(ChatHistory.thread_id == thread_id).delete()
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
async def get_thread_messages(thread_id: int, token: str = ""):
    """Get all messages for a specific thread (owner only)."""
    if not token:
        return {"messages": [], "title": ""}
    db = None
    try:
        from llmwiki.web.routes.auth import get_current_user
        from llmwiki.web.database import SessionLocal
        from llmwiki.web.models import ChatHistory, Conversation
        db = SessionLocal()
        user = get_current_user(token=token, db=db)
        conv = db.query(Conversation).filter(
            Conversation.id == thread_id,
            Conversation.user_id == user.id,
        ).first()
        if not conv:
            return {"messages": [], "title": ""}
        records = (
            db.query(ChatHistory)
            .filter(ChatHistory.thread_id == thread_id)
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
    if not token:
        return {"status": "error", "message": "未登录"}
    if not title or len(title) > 200:
        return {"status": "error", "message": "标题无效"}
    db = None
    try:
        from llmwiki.web.routes.auth import get_current_user
        from llmwiki.web.database import SessionLocal
        from llmwiki.web.models import Conversation
        db = SessionLocal()
        user = get_current_user(token=token, db=db)
        conv = db.query(Conversation).filter(
            Conversation.id == thread_id,
            Conversation.user_id == user.id,
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


@router.post("/fork")
async def fork_thread(body: dict):
    """Fork a thread at a specific message — create new thread with history up to that point."""
    thread_id = body.get("thread_id")
    fork_from_msg_id = body.get("fork_from_msg_id")
    token = body.get("token", "")
    if not token or not thread_id or not fork_from_msg_id:
        return {"status": "error", "message": "缺少参数"}
    db = None
    try:
        from llmwiki.web.routes.auth import get_current_user
        from llmwiki.web.database import SessionLocal
        from llmwiki.web.models import ChatHistory, Conversation
        db = SessionLocal()
        user = get_current_user(token=token, db=db)
        conv = db.query(Conversation).filter(
            Conversation.id == thread_id,
            Conversation.user_id == user.id,
        ).first()
        if not conv:
            return {"status": "error", "message": "对话线程不存在"}
        # Create new thread
        new_conv = Conversation(user_id=user.id, title=conv.title + " (分叉)")
        db.add(new_conv)
        db.flush()
        # Copy messages up to and including fork point
        messages = (
            db.query(ChatHistory)
            .filter(ChatHistory.thread_id == thread_id)
            .order_by(ChatHistory.created_at.asc())
            .all()
        )
        copied = 0
        for msg in messages:
            db.add(ChatHistory(
                user_id=user.id,
                thread_id=new_conv.id,
                question=msg.question,
                answer=msg.answer,
                model=msg.model,
            ))
            copied += 1
            if msg.id == fork_from_msg_id:
                break
        db.commit()
        return {"status": "ok", "thread_id": new_conv.id, "title": new_conv.title}
    except Exception as e:
        return {"status": "error", "message": str(e)}
    finally:
        if db:
            db.close()


def _write_synthesis(question: str, answer: str) -> str:
    """Write Q&A pair to wiki/syntheses/ and return the path."""
    slug = _slugify(question[:30])
    filename = f"{slug}.md"
    filepath = REPO_ROOT / "wiki" / "syntheses" / filename
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

    log_path = REPO_ROOT / "wiki" / "log.md"
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
