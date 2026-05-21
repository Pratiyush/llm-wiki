"""Database setup — SQLite for user auth and approval workflow."""

from __future__ import annotations

from pathlib import Path
from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker, Session

DB_PATH = Path(__file__).resolve().parents[2] / "llmwiki.db"
engine = create_engine(
    f"sqlite:///{DB_PATH}",
    connect_args={"check_same_thread": False},
    pool_pre_ping=True,
)
SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)


def _enable_wal() -> None:
    """Enable WAL mode + sensible PRAGMAs for concurrent read/write safety."""
    import sqlite3
    conn = sqlite3.connect(str(DB_PATH))
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    conn.execute("PRAGMA busy_timeout=5000")
    conn.execute("PRAGMA foreign_keys=ON")
    conn.close()


_enable_wal()


class Base(DeclarativeBase):
    pass


def get_db() -> Session:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    """Create all tables if they don't exist, plus migration for existing installs."""
    import sqlalchemy as sa
    import llmwiki.web.models  # noqa: F401 — ensure models are registered
    Base.metadata.create_all(bind=engine)

    # Migration: add thread_id column to chat_history for existing databases
    # create_all() only creates new tables, not columns on existing tables
    with engine.connect() as conn:
        cols = [row[1] for row in conn.execute(
            sa.text("PRAGMA table_info(chat_history)")
        ).fetchall()]
        if "thread_id" not in cols:
            conn.execute(sa.text(
                "ALTER TABLE chat_history ADD COLUMN thread_id INTEGER REFERENCES conversations(id)"
            ))
            conn.execute(sa.text(
                "ALTER TABLE chat_history ADD COLUMN saved_to_wiki BOOLEAN DEFAULT FALSE"
            ))
            conn.commit()
