from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker


def test_slugify_notebook_title_handles_common_inputs():
    from llmwiki.web.services.notebooks import slugify_notebook_title

    assert slugify_notebook_title("\u4f01\u4e1a\u7ba1\u7406\u5236\u5ea6") == "qi-ye-guan-li-zhi-du"
    assert slugify_notebook_title("Engineering KB") == "engineering-kb"
    assert slugify_notebook_title("   ") == "notebook"
    assert slugify_notebook_title("Team___Docs!!! 2026") == "team-docs-2026"


def test_ensure_notebook_dirs_creates_expected_tree(monkeypatch, tmp_path):
    from llmwiki.web.services import notebooks

    monkeypatch.setattr(notebooks, "REPO_ROOT", tmp_path)

    notebooks.ensure_notebook_dirs("ops")

    expected_dirs = [
        tmp_path / "notebooks" / "ops",
        tmp_path / "notebooks" / "ops" / "raw",
        tmp_path / "notebooks" / "ops" / "wiki",
        tmp_path / "notebooks" / "ops" / "graph",
        tmp_path / "notebooks" / "ops" / "wiki" / "sources",
        tmp_path / "notebooks" / "ops" / "wiki" / "entities",
        tmp_path / "notebooks" / "ops" / "wiki" / "concepts",
        tmp_path / "notebooks" / "ops" / "wiki" / "syntheses",
        tmp_path / "notebooks" / "ops" / "wiki" / "categories",
        tmp_path / "notebooks" / "ops" / "wiki" / "hot",
        tmp_path / "notebooks" / "ops" / "wiki" / "projects",
    ]
    for path in expected_dirs:
        assert path.is_dir()
        assert (path / ".gitkeep").is_file()


def test_notebook_paths_reject_unsafe_slugs(tmp_path, monkeypatch):
    import pytest

    from llmwiki.web.services import notebooks

    monkeypatch.setattr(notebooks, "REPO_ROOT", tmp_path)

    for slug in ["../escape", "/absolute", "bad\\slug", "BadSlug", "", "a--b"]:
        with pytest.raises(ValueError):
            notebooks.notebook_root(slug)


def test_init_db_creates_notebooks_and_adds_nullable_notebook_id(monkeypatch, tmp_path):
    from llmwiki.web import database

    db_path = tmp_path / "legacy.db"
    temp_engine = create_engine(f"sqlite:///{db_path}")
    legacy_tables = {
        "pending_wikis": "CREATE TABLE pending_wikis (id INTEGER PRIMARY KEY, answer TEXT NOT NULL)",
        "chat_history": "CREATE TABLE chat_history (id INTEGER PRIMARY KEY, question TEXT NOT NULL, answer TEXT NOT NULL)",
        "conversations": "CREATE TABLE conversations (id INTEGER PRIMARY KEY, title VARCHAR(200))",
        "uploaded_files": "CREATE TABLE uploaded_files (id INTEGER PRIMARY KEY, filename VARCHAR(200) NOT NULL)",
        "knowledge_lineage": "CREATE TABLE knowledge_lineage (id INTEGER PRIMARY KEY, wiki_path VARCHAR(200) NOT NULL)",
        "outdated_flags": "CREATE TABLE outdated_flags (id INTEGER PRIMARY KEY, reason TEXT)",
    }
    with temp_engine.begin() as conn:
        for ddl in legacy_tables.values():
            conn.execute(sa.text(ddl))

    monkeypatch.setattr(database, "engine", temp_engine)

    database.init_db()
    database.init_db()

    with temp_engine.connect() as conn:
        table_names = {
            row[0]
            for row in conn.execute(
                sa.text("SELECT name FROM sqlite_master WHERE type='table'")
            ).fetchall()
        }
        assert "notebooks" in table_names
        for table_name in legacy_tables:
            columns = {
                row[1]: row
                for row in conn.execute(sa.text(f"PRAGMA table_info({table_name})")).fetchall()
            }
            assert "notebook_id" in columns
            assert columns["notebook_id"][3] == 0
        chat_columns = {
            row[1]
            for row in conn.execute(sa.text("PRAGMA table_info(chat_history)")).fetchall()
        }
        assert {"thread_id", "saved_to_wiki"}.issubset(chat_columns)


def test_ensure_default_notebook_is_idempotent_and_permissions(monkeypatch, tmp_path):
    from llmwiki.web.services import notebooks
    from llmwiki.web.database import Base
    from llmwiki.web.models import Notebook, User
    from llmwiki.web.services.notebooks import (
        can_access_notebook,
        can_manage_notebooks,
        ensure_default_notebook,
        get_default_notebook,
    )

    monkeypatch.setattr(notebooks, "REPO_ROOT", tmp_path)

    engine = create_engine(f"sqlite:///{tmp_path / 'app.db'}")
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    db = Session()
    try:
        first = ensure_default_notebook(db)
        second = ensure_default_notebook(db)

        assert first.id == second.id
        assert first.slug == "enterprise-management"
        assert first.title == "\u4f01\u4e1a\u7ba1\u7406\u5236\u5ea6"
        assert first.is_default is True
        assert get_default_notebook(db).id == first.id
        assert db.query(Notebook).count() == 1

        admin = User(username="admin", hashed_password="x", role="admin")
        staff = User(username="staff", hashed_password="x", role="staff")
        private = Notebook(slug="private-notes", title="Private")
        db.add_all([admin, staff, private])
        db.commit()

        assert can_manage_notebooks(admin) is True
        assert can_manage_notebooks(staff) is False
        assert can_access_notebook(admin, private) is True
        assert can_access_notebook(staff, first) is True
        assert can_access_notebook(staff, private) is False
    finally:
        db.close()
