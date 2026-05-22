"""Database setup for SQLite user auth and approval workflow."""

from __future__ import annotations

from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

DB_PATH = Path(__file__).resolve().parents[2] / "llmwiki.db"
DEFAULT_NOTEBOOK_SLUG = "enterprise-management"
DEFAULT_NOTEBOOK_TITLE = "\u4f01\u4e1a\u7ba1\u7406\u5236\u5ea6"
engine = create_engine(
    f"sqlite:///{DB_PATH}",
    connect_args={"check_same_thread": False},
    pool_pre_ping=True,
)
SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)


def _enable_wal() -> None:
    """Enable WAL mode and sensible PRAGMAs for concurrent read/write safety."""
    import sqlite3

    database = engine.url.database
    if not database or database == ":memory:":
        return
    conn = sqlite3.connect(database)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    conn.execute("PRAGMA busy_timeout=5000")
    conn.execute("PRAGMA foreign_keys=ON")
    conn.close()


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
    import llmwiki.web.models  # noqa: F401

    if engine.url.get_backend_name() == "sqlite":
        _enable_wal()

    Base.metadata.create_all(bind=engine)

    with engine.connect() as conn:
        def column_names(table_name: str) -> set[str]:
            return {
                row[1]
                for row in conn.execute(sa.text(f"PRAGMA table_info({table_name})")).fetchall()
            }

        # create_all() only creates new tables, not columns on existing tables.
        chat_cols = column_names("chat_history")
        if chat_cols and "thread_id" not in chat_cols:
            conn.execute(sa.text(
                "ALTER TABLE chat_history ADD COLUMN thread_id INTEGER REFERENCES conversations(id)"
            ))
            chat_cols.add("thread_id")
        if chat_cols and "saved_to_wiki" not in chat_cols:
            conn.execute(sa.text(
                "ALTER TABLE chat_history ADD COLUMN saved_to_wiki BOOLEAN DEFAULT FALSE"
            ))
            chat_cols.add("saved_to_wiki")

        notebook_scoped_tables = [
            "pending_wikis",
            "chat_history",
            "conversations",
            "uploaded_files",
            "knowledge_lineage",
            "outdated_flags",
        ]
        for table_name in notebook_scoped_tables:
            cols = column_names(table_name)
            if cols and "notebook_id" not in cols:
                conn.execute(sa.text(
                    f"ALTER TABLE {table_name} ADD COLUMN notebook_id INTEGER REFERENCES notebooks(id)"
                ))

        if column_names("notebooks"):
            default_notebook_id = conn.execute(sa.text(
                "SELECT id FROM notebooks WHERE is_default = 1 ORDER BY id LIMIT 1"
            )).scalar()
            if default_notebook_id is None:
                existing_default_slug_id = conn.execute(
                    sa.text("SELECT id FROM notebooks WHERE slug = :slug LIMIT 1"),
                    {"slug": DEFAULT_NOTEBOOK_SLUG},
                ).scalar()
                if existing_default_slug_id is not None:
                    conn.execute(
                        sa.text(
                            "UPDATE notebooks SET title = COALESCE(NULLIF(title, ''), :title), "
                            "is_default = 1 WHERE id = :id"
                        ),
                        {"title": DEFAULT_NOTEBOOK_TITLE, "id": existing_default_slug_id},
                    )
                    default_notebook_id = existing_default_slug_id
                else:
                    conn.execute(
                        sa.text(
                            "INSERT INTO notebooks (slug, title, visibility, is_default, created_at, updated_at) "
                            "VALUES (:slug, :title, 'public', 1, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)"
                        ),
                        {"slug": DEFAULT_NOTEBOOK_SLUG, "title": DEFAULT_NOTEBOOK_TITLE},
                    )
                    default_notebook_id = conn.execute(sa.text(
                        "SELECT id FROM notebooks WHERE slug = :slug LIMIT 1"
                    ), {"slug": DEFAULT_NOTEBOOK_SLUG}).scalar()
        else:
            default_notebook_id = None

        if default_notebook_id is not None:
            for table_name in notebook_scoped_tables:
                cols = column_names(table_name)
                if cols and "notebook_id" in cols:
                    conn.execute(
                        sa.text(f"UPDATE {table_name} SET notebook_id = :notebook_id WHERE notebook_id IS NULL"),
                        {"notebook_id": default_notebook_id},
                    )
        conn.commit()
