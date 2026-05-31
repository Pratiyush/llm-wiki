from __future__ import annotations

import asyncio

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from llmwiki.web.database import Base
from llmwiki.web.models import Notebook, User


@pytest.fixture()
def db_session(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'app.db'}")
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    db = Session()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture()
def users(db_session):
    admin = User(username="admin", hashed_password="x", role="admin")
    staff = User(username="staff", hashed_password="x", role="staff")
    leader = User(username="leader", hashed_password="x", role="leader")
    db_session.add_all([admin, staff, leader])
    db_session.commit()
    for user in (admin, staff, leader):
        db_session.refresh(user)
    return {"admin": admin, "staff": staff, "leader": leader}


def test_can_access_notebook_allows_default_for_staff_and_all_for_admin(users):
    from llmwiki.notebooks import can_access_notebook

    default = Notebook(slug="enterprise-management", title="Enterprise", is_default=True)
    private = Notebook(slug="admin-notes", title="Admin Notes", is_default=False)

    assert can_access_notebook(users["staff"], default) is True
    assert can_access_notebook(users["staff"], private) is False
    assert can_access_notebook(users["admin"], default) is True
    assert can_access_notebook(users["admin"], private) is True


def test_user_is_admin_only_accepts_admin_role(users):
    from llmwiki.notebooks import user_is_admin

    assert user_is_admin(users["admin"]) is True
    assert user_is_admin(users["staff"]) is False
    assert user_is_admin(users["leader"]) is False
    assert user_is_admin(None) is False


def test_notebooks_list_filters_staff_to_default_and_admin_to_all(
    db_session, users, monkeypatch, tmp_path
):
    from llmwiki.web.routes import notebooks as route
    from llmwiki.web.services import notebooks as notebook_services

    monkeypatch.setattr(notebook_services, "REPO_ROOT", tmp_path)
    db_session.add(
        Notebook(
            slug="admin-notes",
            title="Admin Notes",
            description="Private",
            visibility="private",
            is_default=False,
            created_by=users["admin"].id,
        )
    )
    db_session.commit()

    staff_response = asyncio.run(route.api_notebooks(user=users["staff"], db=db_session))
    admin_response = asyncio.run(route.api_notebooks(user=users["admin"], db=db_session))

    assert [notebook["slug"] for notebook in staff_response["notebooks"]] == [
        "enterprise-management"
    ]
    assert [notebook["slug"] for notebook in admin_response["notebooks"]] == [
        "enterprise-management",
        "admin-notes",
    ]


def test_notebooks_list_ensures_default_when_database_empty(
    db_session, users, monkeypatch, tmp_path
):
    from llmwiki.web.routes import notebooks as route
    from llmwiki.web.services import notebooks as notebook_services

    monkeypatch.setattr(notebook_services, "REPO_ROOT", tmp_path)

    response = asyncio.run(route.api_notebooks(user=users["staff"], db=db_session))

    assert [notebook["slug"] for notebook in response["notebooks"]] == [
        "enterprise-management"
    ]
    assert db_session.query(Notebook).filter_by(is_default=True).count() == 1
    assert (tmp_path / "notebooks" / "enterprise-management" / "wiki").is_dir()


def test_create_notebook_rejects_staff(db_session, users):
    from llmwiki.web.routes import notebooks as route

    with pytest.raises(HTTPException) as exc:
        asyncio.run(
            route.create_notebook(
                {"slug": "staff-notes", "title": "Staff Notes"},
                user=users["staff"],
                db=db_session,
            )
        )

    assert exc.value.status_code == 403


def test_create_notebook_allows_admin_and_creates_private_dirs(
    db_session, users, monkeypatch, tmp_path
):
    from llmwiki.web.routes import notebooks as route
    from llmwiki.web.services import notebooks as notebook_services

    monkeypatch.setattr(notebook_services, "REPO_ROOT", tmp_path)

    response = asyncio.run(
        route.create_notebook(
            {"slug": "admin-notes", "title": "Admin Notes", "description": "Private"},
            user=users["admin"],
            db=db_session,
        )
    )

    assert response == {
        "status": "ok",
        "notebook": {
            "slug": "admin-notes",
            "title": "Admin Notes",
            "name": "Admin Notes",
            "description": "Private",
            "visibility": "private",
            "is_default": False,
        },
    }
    notebook = db_session.query(Notebook).filter_by(slug="admin-notes").one()
    assert notebook.created_by == users["admin"].id
    assert (tmp_path / "notebooks" / "admin-notes" / "wiki").is_dir()


def test_create_notebook_accepts_name_alias_for_frontend(
    db_session, users, monkeypatch, tmp_path
):
    from llmwiki.web.routes import notebooks as route
    from llmwiki.web.services import notebooks as notebook_services

    monkeypatch.setattr(notebook_services, "REPO_ROOT", tmp_path)

    response = asyncio.run(
        route.create_notebook(
            {"slug": "ai", "name": "Artificial Intelligence", "description": "AI notes"},
            user=users["admin"],
            db=db_session,
        )
    )

    assert response["notebook"]["slug"] == "ai"
    assert response["notebook"]["title"] == "Artificial Intelligence"
    assert response["notebook"]["name"] == "Artificial Intelligence"


def test_create_notebook_normalizes_slug_with_spaces_from_form_input(
    db_session, users, monkeypatch, tmp_path
):
    from llmwiki.web.routes import notebooks as route
    from llmwiki.web.services import notebooks as notebook_services

    monkeypatch.setattr(notebook_services, "REPO_ROOT", tmp_path)

    response = asyncio.run(
        route.create_notebook(
            {
                "slug": "Chinese tradition",
                "name": "传统文化",
                "description": "中国传统文化知识",
            },
            user=users["admin"],
            db=db_session,
        )
    )

    assert response["notebook"]["slug"] == "chinese-tradition"
    assert response["notebook"]["title"] == "传统文化"
    assert (tmp_path / "notebooks" / "chinese-tradition" / "wiki").is_dir()


def test_create_notebook_accepts_chinese_slug_from_form_input(
    db_session, users, monkeypatch, tmp_path
):
    from llmwiki.notebooks import is_valid_slug
    from llmwiki.web.routes import notebooks as route
    from llmwiki.web.services import notebooks as notebook_services

    monkeypatch.setattr(notebook_services, "REPO_ROOT", tmp_path)

    response = asyncio.run(
        route.create_notebook(
            {
                "slug": "城轨技术规范",
                "name": "城市轨道交通技术规范",
                "description": "城市轨道交通业务范围内的技术规范",
            },
            user=users["admin"],
            db=db_session,
        )
    )

    slug = response["notebook"]["slug"]
    assert is_valid_slug(slug)
    assert slug != "notebook"
    assert response["notebook"]["title"] == "城市轨道交通技术规范"
    assert (tmp_path / "notebooks" / slug / "wiki").is_dir()


def test_update_notebook_allows_admin_to_edit_non_default(db_session, users):
    from llmwiki.web.routes import notebooks as route

    db_session.add(
        Notebook(
            slug="ai",
            title="AI",
            description="Old",
            is_default=False,
            created_by=users["admin"].id,
        )
    )
    db_session.commit()

    response = asyncio.run(
        route.update_notebook(
            "ai",
            {"name": "Artificial Intelligence", "description": "New"},
            user=users["admin"],
            db=db_session,
        )
    )

    notebook = db_session.query(Notebook).filter_by(slug="ai").one()
    assert response["status"] == "ok"
    assert notebook.title == "Artificial Intelligence"
    assert notebook.description == "New"


def test_update_notebook_rejects_staff_and_default(db_session, users):
    from llmwiki.web.routes import notebooks as route

    db_session.add(Notebook(slug="enterprise-management", title="Default", is_default=True))
    db_session.add(Notebook(slug="ai", title="AI", is_default=False))
    db_session.commit()

    with pytest.raises(HTTPException) as staff_exc:
        asyncio.run(route.update_notebook("ai", {"name": "X"}, user=users["staff"], db=db_session))
    assert staff_exc.value.status_code == 403

    with pytest.raises(HTTPException) as default_exc:
        asyncio.run(
            route.update_notebook(
                "enterprise-management",
                {"name": "X"},
                user=users["admin"],
                db=db_session,
            )
        )
    assert default_exc.value.status_code == 404


@pytest.mark.parametrize(
    ("body", "status_code"),
    [
        ({"slug": "admin-notes", "title": "Duplicate"}, 409),
        ({"slug": "../bad", "title": "Bad Slug"}, 400),
        ({"slug": "BadSlug", "title": "Bad Slug"}, 400),
        ({"slug": "empty-title", "title": "   "}, 400),
    ],
)
def test_create_notebook_rejects_duplicate_slug_invalid_slug_and_empty_title(
    db_session, users, body, status_code
):
    from llmwiki.web.routes import notebooks as route

    db_session.add(Notebook(slug="admin-notes", title="Existing"))
    db_session.commit()

    with pytest.raises(HTTPException) as exc:
        asyncio.run(route.create_notebook(body, user=users["admin"], db=db_session))

    assert exc.value.status_code == status_code
