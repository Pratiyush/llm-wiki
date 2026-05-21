"""SQLAlchemy models for users and approval workflow."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from llmwiki.web.database import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    username: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    full_name: Mapped[str] = mapped_column(String(100), default="")
    department: Mapped[str] = mapped_column(String(100), default="")
    role: Mapped[str] = mapped_column(String(20), default="staff")  # admin / leader / staff
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)


class PendingWiki(Base):
    __tablename__ = "pending_wikis"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    question: Mapped[str] = mapped_column(Text, default="")
    answer: Mapped[str] = mapped_column(Text, nullable=False)
    slug: Mapped[str] = mapped_column(String(100), default="")
    proposer_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"))
    department: Mapped[str] = mapped_column(String(100), default="")
    status: Mapped[str] = mapped_column(String(20), default="pending")  # pending / approved / rejected
    reviewer_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("users.id"), nullable=True)
    review_comment: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class ChatHistory(Base):
    __tablename__ = "chat_history"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"))
    thread_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("conversations.id"), nullable=True)
    question: Mapped[str] = mapped_column(Text, nullable=False)
    answer: Mapped[str] = mapped_column(Text, nullable=False)
    model: Mapped[str] = mapped_column(String(50), default="")
    saved_to_wiki: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)


class Conversation(Base):
    __tablename__ = "conversations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"))
    title: Mapped[str] = mapped_column(String(200), default="新对话")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)


class UploadedFile(Base):
    __tablename__ = "uploaded_files"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    filename: Mapped[str] = mapped_column(String(200), nullable=False)
    wiki_path: Mapped[str] = mapped_column(String(200), default="")
    version_note: Mapped[str] = mapped_column(String(200), nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="current")  # current / outdated
    uploader_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=True)
    uploaded_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)


class KnowledgeLineage(Base):
    __tablename__ = "knowledge_lineage"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    source_file_id: Mapped[int] = mapped_column(Integer, ForeignKey("uploaded_files.id"))
    wiki_path: Mapped[str] = mapped_column(String(200), nullable=False)
    wiki_type: Mapped[str] = mapped_column(String(20), default="source")  # source / entity / concept / synthesis / pending_review
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)


class OutdatedFlag(Base):
    __tablename__ = "outdated_flags"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    file_id: Mapped[int] = mapped_column(Integer, ForeignKey("uploaded_files.id"))
    reporter_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"))
    reason: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(String(20), default="pending")  # pending / confirmed / rejected
    reviewer_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
