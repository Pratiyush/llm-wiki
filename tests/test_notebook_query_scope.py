from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest


def _page(wiki: Path, name: str, body: str) -> None:
    path = wiki / "sources" / f"{name}.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(f'---\ntitle: "{name}"\n---\n\n{body}', encoding="utf-8")


def test_build_context_uses_selected_wiki_dir(tmp_path):
    from llmwiki.web.services.glm_client import build_context

    wiki_a = tmp_path / "a" / "wiki"
    wiki_b = tmp_path / "b" / "wiki"
    _page(wiki_a, "ai", "transformer attention material")
    _page(wiki_b, "policy", "contract approval material")

    context = build_context("transformer", wiki_dir=wiki_a)

    assert "transformer attention material" in context
    assert "contract approval material" not in context


def test_write_synthesis_uses_selected_notebook_wiki(tmp_path, monkeypatch):
    import llmwiki.web.routes.query as query

    repo = tmp_path / "repo"
    wiki = tmp_path / "notebooks" / "ai" / "wiki"
    monkeypatch.setattr(query, "REPO_ROOT", repo)

    rel_path = query._write_synthesis("What is attention?", "Only notebook answer", wiki_dir=wiki)

    assert rel_path.startswith("syntheses/")
    assert (wiki / rel_path).read_text(encoding="utf-8").find("Only notebook answer") >= 0
    assert (wiki / "log.md").is_file()
    assert not (repo / "wiki" / rel_path).exists()


def test_save_chat_history_records_notebook_id(monkeypatch, tmp_path):
    import llmwiki.web.database as database
    import llmwiki.web.routes.query as query
    from llmwiki.web.database import Base
    from llmwiki.web.models import ChatHistory, Conversation, Notebook, User

    db_path = tmp_path / "query.db"
    engine = database.create_engine(f"sqlite:///{db_path}", connect_args={"check_same_thread": False})
    TestingSessionLocal = database.sessionmaker(bind=engine, autocommit=False, autoflush=False)
    Base.metadata.create_all(bind=engine)
    monkeypatch.setattr(database, "engine", engine)
    monkeypatch.setattr(database, "SessionLocal", TestingSessionLocal)

    with TestingSessionLocal() as db:
        user = User(username="admin", hashed_password="x", role="admin")
        notebook = Notebook(slug="ai", title="AI", is_default=False)
        db.add_all([user, notebook])
        db.commit()
        db.refresh(user)
        db.refresh(notebook)
        user_id = user.id
        notebook_id = notebook.id

    def fake_current_user(token, db):
        return db.get(User, user_id)

    monkeypatch.setattr("llmwiki.web.routes.auth.get_current_user", fake_current_user)

    thread_id = query._save_chat_history(
        "token",
        "Question",
        "Answer",
        notebook_id=notebook_id,
    )

    with TestingSessionLocal() as db:
        conversation = db.get(Conversation, thread_id)
        history = db.query(ChatHistory).one()
        assert conversation.notebook_id == notebook_id
        assert history.notebook_id == notebook_id


def _query_db(tmp_path, monkeypatch):
    import llmwiki.web.database as database
    from llmwiki.web.database import Base

    db_path = tmp_path / "query.db"
    engine = database.create_engine(f"sqlite:///{db_path}", connect_args={"check_same_thread": False})
    TestingSessionLocal = database.sessionmaker(bind=engine, autocommit=False, autoflush=False)
    Base.metadata.create_all(bind=engine)
    monkeypatch.setattr(database, "engine", engine)
    monkeypatch.setattr(database, "SessionLocal", TestingSessionLocal)
    return TestingSessionLocal


def test_save_chat_history_rejects_thread_owned_by_another_user(monkeypatch, tmp_path):
    import llmwiki.web.routes.query as query
    from llmwiki.web.models import ChatHistory, Conversation, Notebook, User

    TestingSessionLocal = _query_db(tmp_path, monkeypatch)
    with TestingSessionLocal() as db:
        owner = User(username="owner", hashed_password="x", role="admin")
        attacker = User(username="attacker", hashed_password="x", role="admin")
        notebook = Notebook(slug="ai", title="AI", is_default=False)
        db.add_all([owner, attacker, notebook])
        db.commit()
        db.refresh(owner)
        db.refresh(attacker)
        db.refresh(notebook)
        conv = Conversation(user_id=owner.id, notebook_id=notebook.id, title="Owner thread")
        db.add(conv)
        db.commit()
        owner_thread_id = conv.id
        attacker_id = attacker.id
        notebook_id = notebook.id

    def fake_current_user(token, db):
        return db.get(User, attacker_id)

    monkeypatch.setattr("llmwiki.web.routes.auth.get_current_user", fake_current_user)

    new_thread_id = query._save_chat_history(
        "token",
        "Injected",
        "Blocked",
        thread_id=owner_thread_id,
        notebook_id=notebook_id,
    )

    assert new_thread_id != owner_thread_id
    with TestingSessionLocal() as db:
        owner_rows = db.query(ChatHistory).filter(ChatHistory.thread_id == owner_thread_id).all()
        attacker_rows = db.query(ChatHistory).filter(ChatHistory.user_id == attacker_id).all()
        assert owner_rows == []
        assert len(attacker_rows) == 1
        assert attacker_rows[0].thread_id == new_thread_id


def test_init_db_backfills_legacy_chat_rows_to_default_notebook(monkeypatch, tmp_path):
    import sqlalchemy as sa
    import llmwiki.web.database as database
    from llmwiki.web.models import Notebook

    db_path = tmp_path / "legacy.db"
    engine = database.create_engine(f"sqlite:///{db_path}", connect_args={"check_same_thread": False})
    monkeypatch.setattr(database, "engine", engine)

    with engine.begin() as conn:
        conn.execute(sa.text("CREATE TABLE notebooks (id INTEGER PRIMARY KEY, slug VARCHAR(100) UNIQUE NOT NULL, title VARCHAR(200) NOT NULL, description TEXT, visibility VARCHAR(20) NOT NULL DEFAULT 'private', is_default BOOLEAN NOT NULL DEFAULT FALSE, created_by INTEGER, created_at DATETIME, updated_at DATETIME)"))
        conn.execute(sa.text("CREATE TABLE users (id INTEGER PRIMARY KEY, username VARCHAR(50) UNIQUE NOT NULL, hashed_password VARCHAR(255) NOT NULL, full_name VARCHAR(100), department VARCHAR(100), role VARCHAR(20), is_active BOOLEAN, created_at DATETIME)"))
        conn.execute(sa.text("CREATE TABLE conversations (id INTEGER PRIMARY KEY, user_id INTEGER NOT NULL, title VARCHAR(200), created_at DATETIME)"))
        conn.execute(sa.text("CREATE TABLE chat_history (id INTEGER PRIMARY KEY, user_id INTEGER NOT NULL, thread_id INTEGER, question TEXT NOT NULL, answer TEXT NOT NULL, model VARCHAR(50), saved_to_wiki BOOLEAN DEFAULT FALSE, created_at DATETIME)"))
        conn.execute(sa.text("CREATE TABLE pending_wikis (id INTEGER PRIMARY KEY, question TEXT, answer TEXT NOT NULL, slug VARCHAR(100), proposer_id INTEGER NOT NULL, department VARCHAR(100), status VARCHAR(20), reviewer_id INTEGER, review_comment TEXT, created_at DATETIME, reviewed_at DATETIME)"))
        conn.execute(sa.text("CREATE TABLE uploaded_files (id INTEGER PRIMARY KEY, filename VARCHAR(200) NOT NULL, wiki_path VARCHAR(200), version_note VARCHAR(200) NOT NULL, status VARCHAR(20), uploader_id INTEGER, uploaded_at DATETIME)"))
        conn.execute(sa.text("CREATE TABLE knowledge_lineage (id INTEGER PRIMARY KEY, source_file_id INTEGER NOT NULL, wiki_path VARCHAR(200) NOT NULL, wiki_type VARCHAR(20), created_at DATETIME)"))
        conn.execute(sa.text("CREATE TABLE outdated_flags (id INTEGER PRIMARY KEY, file_id INTEGER NOT NULL, reporter_id INTEGER NOT NULL, reason TEXT, status VARCHAR(20), reviewer_id INTEGER, created_at DATETIME, reviewed_at DATETIME)"))
        conn.execute(sa.text("INSERT INTO notebooks (id, slug, title, is_default, visibility) VALUES (10, 'enterprise-management', '企业管理制度', 1, 'public')"))
        conn.execute(sa.text("INSERT INTO users (id, username, hashed_password) VALUES (1, 'u', 'x')"))
        conn.execute(sa.text("INSERT INTO conversations (id, user_id, title) VALUES (1, 1, 'legacy')"))
        conn.execute(sa.text("INSERT INTO chat_history (id, user_id, thread_id, question, answer) VALUES (1, 1, 1, 'q', 'a')"))

    database.init_db()

    with engine.connect() as conn:
        default_id = conn.execute(sa.select(Notebook.id).where(Notebook.slug == "enterprise-management")).scalar_one()
        conv_notebook = conn.execute(sa.text("SELECT notebook_id FROM conversations WHERE id = 1")).scalar_one()
        chat_notebook = conn.execute(sa.text("SELECT notebook_id FROM chat_history WHERE id = 1")).scalar_one()

    assert conv_notebook == default_id
    assert chat_notebook == default_id


def test_init_db_creates_default_notebook_before_legacy_chat_backfill(monkeypatch, tmp_path):
    import sqlalchemy as sa
    import llmwiki.web.database as database
    from llmwiki.web.models import Notebook

    db_path = tmp_path / "legacy-without-default.db"
    engine = database.create_engine(f"sqlite:///{db_path}", connect_args={"check_same_thread": False})
    monkeypatch.setattr(database, "engine", engine)

    with engine.begin() as conn:
        conn.execute(sa.text("CREATE TABLE notebooks (id INTEGER PRIMARY KEY, slug VARCHAR(100) UNIQUE NOT NULL, title VARCHAR(200) NOT NULL, description TEXT, visibility VARCHAR(20) NOT NULL DEFAULT 'private', is_default BOOLEAN NOT NULL DEFAULT FALSE, created_by INTEGER, created_at DATETIME, updated_at DATETIME)"))
        conn.execute(sa.text("CREATE TABLE users (id INTEGER PRIMARY KEY, username VARCHAR(50) UNIQUE NOT NULL, hashed_password VARCHAR(255) NOT NULL, full_name VARCHAR(100), department VARCHAR(100), role VARCHAR(20), is_active BOOLEAN, created_at DATETIME)"))
        conn.execute(sa.text("CREATE TABLE conversations (id INTEGER PRIMARY KEY, user_id INTEGER NOT NULL, title VARCHAR(200), created_at DATETIME)"))
        conn.execute(sa.text("CREATE TABLE chat_history (id INTEGER PRIMARY KEY, user_id INTEGER NOT NULL, thread_id INTEGER, question TEXT NOT NULL, answer TEXT NOT NULL, model VARCHAR(50), saved_to_wiki BOOLEAN DEFAULT FALSE, created_at DATETIME)"))
        conn.execute(sa.text("CREATE TABLE pending_wikis (id INTEGER PRIMARY KEY, question TEXT, answer TEXT NOT NULL, slug VARCHAR(100), proposer_id INTEGER NOT NULL, department VARCHAR(100), status VARCHAR(20), reviewer_id INTEGER, review_comment TEXT, created_at DATETIME, reviewed_at DATETIME)"))
        conn.execute(sa.text("CREATE TABLE uploaded_files (id INTEGER PRIMARY KEY, filename VARCHAR(200) NOT NULL, wiki_path VARCHAR(200), version_note VARCHAR(200) NOT NULL, status VARCHAR(20), uploader_id INTEGER, uploaded_at DATETIME)"))
        conn.execute(sa.text("CREATE TABLE knowledge_lineage (id INTEGER PRIMARY KEY, source_file_id INTEGER NOT NULL, wiki_path VARCHAR(200) NOT NULL, wiki_type VARCHAR(20), created_at DATETIME)"))
        conn.execute(sa.text("CREATE TABLE outdated_flags (id INTEGER PRIMARY KEY, file_id INTEGER NOT NULL, reporter_id INTEGER NOT NULL, reason TEXT, status VARCHAR(20), reviewer_id INTEGER, created_at DATETIME, reviewed_at DATETIME)"))
        conn.execute(sa.text("INSERT INTO users (id, username, hashed_password) VALUES (1, 'u', 'x')"))
        conn.execute(sa.text("INSERT INTO conversations (id, user_id, title) VALUES (1, 1, 'legacy')"))
        conn.execute(sa.text("INSERT INTO chat_history (id, user_id, thread_id, question, answer) VALUES (1, 1, 1, 'q', 'a')"))

    database.init_db()

    with engine.connect() as conn:
        default_id = conn.execute(sa.select(Notebook.id).where(Notebook.slug == "enterprise-management")).scalar_one()
        conv_notebook = conn.execute(sa.text("SELECT notebook_id FROM conversations WHERE id = 1")).scalar_one()
        chat_notebook = conn.execute(sa.text("SELECT notebook_id FROM chat_history WHERE id = 1")).scalar_one()

    assert conv_notebook == default_id
    assert chat_notebook == default_id


@pytest.mark.asyncio
async def test_ask_route_passes_selected_notebook_wiki_dir(monkeypatch, tmp_path):
    import llmwiki.web.routes.query as query

    wiki_dir = tmp_path / "notebooks" / "ai" / "wiki"
    captured = {}

    monkeypatch.setattr(
        query,
        "_resolve_query_notebook",
        lambda slug, token="": (SimpleNamespace(slug=slug, id=42), wiki_dir, None),
    )

    def fake_ask(question, model=None, *, wiki_dir=None):
        captured["question"] = question
        captured["wiki_dir"] = wiki_dir
        return "scoped answer"

    monkeypatch.setattr("llmwiki.web.services.glm_client.ask", fake_ask)

    response = await query.ask({"question": "attention", "notebook_slug": "ai"})

    assert response["answer"] == "scoped answer"
    assert response["notebook"] == "ai"
    assert captured == {"question": "attention", "wiki_dir": wiki_dir}


@pytest.mark.asyncio
async def test_cross_notebook_search_requires_admin(monkeypatch):
    import llmwiki.web.routes.query as query

    monkeypatch.setattr(query, "_user_from_token", lambda token: None)

    response = await query.ask({"question": "x", "cross_notebook": True})

    assert response["answer"] == query.CROSS_NOTEBOOK_DENIED


def test_stream_cross_notebook_denial_is_framed_and_done(monkeypatch):
    import asyncio
    import llmwiki.web.routes.query as query

    monkeypatch.setattr(query, "_user_from_token", lambda token: None)

    response = asyncio.run(query.stream({"question": "x", "cross_notebook": True}))

    async def collect():
        return [chunk async for chunk in response.body_iterator]

    chunks = asyncio.run(collect())

    assert chunks == [
        f"data: {query.CROSS_NOTEBOOK_DENIED}\n\n",
        "data: [DONE]\n\n",
    ]


def test_agent_cross_notebook_denial_is_framed_and_done(monkeypatch):
    import asyncio
    import json
    import llmwiki.web.routes.query as query

    monkeypatch.setattr(query, "_user_from_token", lambda token: None)

    response = asyncio.run(query.agent_stream({"question": "x", "cross_notebook": True}))

    async def collect():
        return [chunk async for chunk in response.body_iterator]

    chunks = asyncio.run(collect())

    assert chunks[0].startswith("data: ")
    payload = json.loads(chunks[0][6:].strip())
    assert payload == {"type": "error", "message": query.CROSS_NOTEBOOK_DENIED}
    assert chunks[1] == "data: [DONE]\n\n"
