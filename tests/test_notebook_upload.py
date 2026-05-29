from __future__ import annotations

import asyncio
from io import BytesIO

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from starlette.datastructures import UploadFile


def test_save_raw_file_uses_notebook_uploads_dir(tmp_path):
    from llmwiki.web.services.ingester import save_raw_file

    uploads_dir = tmp_path / "notebooks" / "ai" / "raw" / "uploads"

    saved = save_raw_file("AI Notes.md", b"# Notes", uploads_dir=uploads_dir)

    assert saved == uploads_dir / "AI-Notes.md"
    assert saved.read_bytes() == b"# Notes"


def test_save_raw_file_default_preserves_company_docs_dir(monkeypatch, tmp_path):
    from llmwiki.web.services import ingester

    raw_dir = tmp_path / "raw" / "company-docs"
    monkeypatch.setattr(ingester, "RAW_DIR", raw_dir)

    saved = ingester.save_raw_file("Policy File.md", b"# Policy")

    assert saved == raw_dir / "Policy-File.md"
    assert saved.read_bytes() == b"# Policy"


def test_process_upload_writes_wiki_to_selected_notebook(tmp_path):
    from llmwiki.web.services.ingester import process_upload

    uploads_dir = tmp_path / "notebooks" / "ai" / "raw" / "uploads"
    wiki_dir = tmp_path / "notebooks" / "ai" / "wiki"
    global_wiki = tmp_path / "wiki"
    (wiki_dir / "log.md").parent.mkdir(parents=True)
    (wiki_dir / "log.md").write_text("", encoding="utf-8")

    result = process_upload(
        "AI Notes.md",
        b"# Notes\n\n[[AI]]",
        uploads_dir=uploads_dir,
        wiki_dir=wiki_dir,
    )

    assert result["status"] == "ok"
    assert result["wiki_path"] == "sources/company-docs/AI-Notes.md"
    assert (wiki_dir / "sources" / "company-docs" / "AI-Notes.md").is_file()
    assert not (global_wiki / "sources" / "company-docs" / "AI-Notes.md").exists()


def test_process_upload_default_preserves_company_docs_raw_dir(monkeypatch, tmp_path):
    from llmwiki.web.services import ingester

    raw_dir = tmp_path / "raw" / "company-docs"
    wiki_root = tmp_path / "wiki"
    monkeypatch.setattr(ingester, "RAW_DIR", raw_dir)
    monkeypatch.setattr(ingester, "REPO_ROOT", tmp_path)

    result = ingester.process_upload("Policy File.txt", b"# Policy", wiki_dir=wiki_root)

    assert result["status"] == "ok"
    assert (raw_dir / "Policy-File.txt").read_bytes() == b"# Policy"
    assert (raw_dir / "Policy-File.md").is_file()
    assert not (tmp_path / "raw" / "uploads").exists()


def test_create_entity_concept_pages_sanitizes_extracted_names(tmp_path):
    from llmwiki.web.services.ingester import create_entity_concept_pages

    wiki_dir = tmp_path / "notebooks" / "ai" / "wiki"
    outside = tmp_path / "notebooks" / "ai" / "escape.md"
    knowledge = {
        "entities": [{"name": "../escape", "description": "bad"}],
        "concepts": [{"name": "bad\\concept/name", "description": "bad"}],
    }

    created = create_entity_concept_pages(knowledge, "source-slug", wiki_dir=wiki_dir)

    assert "entities/escape.md" in created
    assert "concepts/bad-concept-name.md" in created
    assert (wiki_dir / "entities" / "escape.md").is_file()
    assert (wiki_dir / "concepts" / "bad-concept-name.md").is_file()
    assert not outside.exists()


def test_importing_auth_route_does_not_create_jwt_secret(monkeypatch, tmp_path):
    import importlib
    import sys

    import llmwiki

    secret_path = tmp_path / ".jwt_secret"
    monkeypatch.delenv("JWT_SECRET_KEY", raising=False)
    monkeypatch.setattr(llmwiki, "REPO_ROOT", tmp_path)
    sys.modules.pop("llmwiki.web.routes.auth", None)

    importlib.import_module("llmwiki.web.routes.auth")

    assert not secret_path.exists()


def test_upload_route_records_notebook_id_and_uses_selected_notebook(
    monkeypatch,
    tmp_path,
):
    monkeypatch.setenv("JWT_SECRET_KEY", "test-secret")

    from llmwiki.web import database
    from llmwiki.web.database import Base
    from llmwiki.web.models import KnowledgeLineage, Notebook, UploadedFile, User
    from llmwiki.web.routes.auth import _create_token
    from llmwiki.web.routes.upload import upload_file
    from llmwiki.web.services import notebooks

    monkeypatch.setattr(notebooks, "REPO_ROOT", tmp_path)
    engine = create_engine(f"sqlite:///{tmp_path / 'app.db'}")
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    monkeypatch.setattr(database, "SessionLocal", Session)

    db = Session()
    try:
        admin = User(username="admin", hashed_password="x", role="admin")
        selected = Notebook(slug="ai", title="AI", is_default=False)
        db.add_all([admin, selected])
        db.commit()
        db.refresh(admin)
        db.refresh(selected)
        token = _create_token(admin)
        notebook_id = selected.id
    finally:
        db.close()

    notebooks.ensure_notebook_dirs("ai")
    (tmp_path / "notebooks" / "ai" / "wiki" / "log.md").write_text("", encoding="utf-8")
    upload = UploadFile(filename="AI Notes.md", file=BytesIO(b"# Notes"))

    result = asyncio.run(upload_file(file=upload, token=token, notebook="ai"))

    assert result["status"] == "ok"
    db = Session()
    try:
        uploaded = db.query(UploadedFile).one()
        assert uploaded.notebook_id == notebook_id
        lineages = db.query(KnowledgeLineage).all()
        assert lineages
        assert {lineage.notebook_id for lineage in lineages} == {notebook_id}
        assert (tmp_path / "notebooks" / "ai" / "wiki" / "sources" / "company-docs").is_dir()
    finally:
        db.close()


def test_upload_route_accepts_bearer_token_header(monkeypatch, tmp_path):
    monkeypatch.setenv("JWT_SECRET_KEY", "test-secret")

    from llmwiki.web import database
    from llmwiki.web.database import Base
    from llmwiki.web.models import Notebook, UploadedFile, User
    from llmwiki.web.routes.auth import _create_token
    from llmwiki.web.routes.upload import upload_file
    from llmwiki.web.services import notebooks

    monkeypatch.setattr(notebooks, "REPO_ROOT", tmp_path)
    engine = create_engine(f"sqlite:///{tmp_path / 'app.db'}")
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    monkeypatch.setattr(database, "SessionLocal", Session)

    db = Session()
    try:
        admin = User(username="admin", hashed_password="x", role="admin")
        selected = Notebook(slug="ai", title="AI", is_default=False)
        db.add_all([admin, selected])
        db.commit()
        db.refresh(admin)
        admin_id = admin.id
        token = _create_token(admin)
    finally:
        db.close()

    notebooks.ensure_notebook_dirs("ai")
    (tmp_path / "notebooks" / "ai" / "wiki" / "log.md").write_text("", encoding="utf-8")

    result = asyncio.run(
        upload_file(
            file=UploadFile(filename="AI Notes.md", file=BytesIO(b"# Notes")),
            notebook="ai",
            authorization=f"Bearer {token}",
        )
    )

    assert result["status"] == "ok"
    db = Session()
    try:
        uploaded = db.query(UploadedFile).one()
        assert uploaded.uploader_id == admin_id
    finally:
        db.close()


def test_upload_route_rejects_invalid_or_missing_notebook(monkeypatch, tmp_path):
    from fastapi import HTTPException

    from llmwiki.web import database
    from llmwiki.web.database import Base
    from llmwiki.web.routes.upload import upload_file
    from llmwiki.web.services import notebooks

    monkeypatch.setattr(notebooks, "REPO_ROOT", tmp_path)
    engine = create_engine(f"sqlite:///{tmp_path / 'app.db'}")
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    monkeypatch.setattr(database, "SessionLocal", Session)

    with pytest.raises(HTTPException) as invalid:
        asyncio.run(
            upload_file(
                file=UploadFile(filename="Notes.md", file=BytesIO(b"# Notes")),
                notebook="../escape",
            )
        )
    assert invalid.value.status_code == 400

    with pytest.raises(HTTPException) as missing:
        asyncio.run(
            upload_file(
                file=UploadFile(filename="Notes.md", file=BytesIO(b"# Notes")),
                notebook="missing",
            )
        )
    assert missing.value.status_code == 404


def test_staff_cannot_upload_to_non_default_notebook(monkeypatch, tmp_path):
    from fastapi import HTTPException

    monkeypatch.setenv("JWT_SECRET_KEY", "test-secret")

    from llmwiki.web import database
    from llmwiki.web.database import Base
    from llmwiki.web.models import Notebook, User
    from llmwiki.web.routes.auth import _create_token
    from llmwiki.web.routes.upload import upload_file
    from llmwiki.web.services import notebooks

    monkeypatch.setattr(notebooks, "REPO_ROOT", tmp_path)
    engine = create_engine(f"sqlite:///{tmp_path / 'app.db'}")
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    monkeypatch.setattr(database, "SessionLocal", Session)

    db = Session()
    try:
        staff = User(username="staff", hashed_password="x", role="staff")
        private = Notebook(slug="private-notes", title="Private", is_default=False)
        db.add_all([staff, private])
        db.commit()
        db.refresh(staff)
        token = _create_token(staff)
    finally:
        db.close()

    notebooks.ensure_notebook_dirs("private-notes")

    with pytest.raises(HTTPException) as exc:
        asyncio.run(
            upload_file(
                file=UploadFile(filename="Notes.md", file=BytesIO(b"# Notes")),
                token=token,
                notebook="private-notes",
            )
        )
    assert exc.value.status_code == 403
