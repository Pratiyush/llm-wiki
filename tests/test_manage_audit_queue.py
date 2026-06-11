from __future__ import annotations

import asyncio

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from llmwiki.web.database import Base
from llmwiki.web.models import KnowledgeLineage, Notebook, UploadedFile, User


def test_audit_queue_checks_files_in_selected_notebook_wiki(monkeypatch, tmp_path):
    from llmwiki.web.routes import manage
    from llmwiki.web.services import notebooks as notebook_services

    monkeypatch.setattr(notebook_services, "REPO_ROOT", tmp_path)
    engine = create_engine(f"sqlite:///{tmp_path / 'app.db'}")
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    db = Session()
    try:
        admin = User(username="admin", hashed_password="x", role="admin")
        notebook = Notebook(
            slug="enterprise-management",
            title="企业管理制度",
            is_default=True,
        )
        db.add_all([admin, notebook])
        db.commit()
        db.refresh(admin)
        db.refresh(notebook)

        wiki_file = tmp_path / "notebooks" / notebook.slug / "wiki" / "sources" / "budget.md"
        wiki_file.parent.mkdir(parents=True, exist_ok=True)
        wiki_file.write_text("---\ntitle: 预算基价\n---\n正文预览", encoding="utf-8")

        uploaded = UploadedFile(
            notebook_id=notebook.id,
            filename="2020天津市建筑、装饰装修工程预算基价.pdf",
            wiki_path="sources/budget.md",
            version_note="test",
            status="outdated",
            uploader_id=admin.id,
        )
        db.add(uploaded)
        db.commit()
        db.refresh(uploaded)

        db.add(
            KnowledgeLineage(
                notebook_id=notebook.id,
                source_file_id=uploaded.id,
                wiki_path="sources/budget.md",
                wiki_type="pending_review",
            )
        )
        db.commit()

        response = asyncio.run(
            manage.get_audit_queue(user=admin, db=db, notebook="enterprise-management")
        )

        assert response["queue"][0]["file_exists"] is True
        assert "正文预览" in response["queue"][0]["preview"]
    finally:
        db.close()
