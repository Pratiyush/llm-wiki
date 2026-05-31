"""Notebook listing and admin creation API."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from llmwiki.notebooks import (
    NOTEBOOK_DESCRIPTION,
    is_valid_slug,
    user_is_admin,
)
from llmwiki.web.database import get_db
from llmwiki.web.models import Notebook, User
from llmwiki.web.routes.auth import get_current_user
from llmwiki.web.services.notebooks import (
    ensure_default_notebook,
    ensure_notebook_dirs,
    slugify_notebook_title,
)

router = APIRouter()


def _normalize_submitted_slug(raw_slug: str, title: str) -> str:
    slug = raw_slug.strip()
    if not slug:
        return slugify_notebook_title(title)
    if any(char.isspace() for char in slug) or "_" in slug or not slug.isascii():
        return slugify_notebook_title(slug)
    return slug


def _serialize_notebook(notebook: Notebook) -> dict[str, object]:
    return {
        "slug": notebook.slug,
        "title": notebook.title,
        "name": notebook.title,
        "description": notebook.description or (
            NOTEBOOK_DESCRIPTION if notebook.is_default else None
        ),
        "is_default": notebook.is_default,
        "visibility": "public" if notebook.is_default else notebook.visibility,
    }


@router.get("")
async def api_notebooks(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    ensure_default_notebook(db)

    query = db.query(Notebook)
    if not user_is_admin(user):
        query = query.filter(Notebook.is_default.is_(True))

    notebooks = query.order_by(Notebook.is_default.desc(), Notebook.id.asc()).all()
    return {"notebooks": [_serialize_notebook(notebook) for notebook in notebooks]}


@router.post("")
async def create_notebook(
    body: dict,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if not user_is_admin(user):
        raise HTTPException(status_code=403, detail="admin role required")

    title = str(body.get("title") or body.get("name") or "").strip()
    slug = _normalize_submitted_slug(str(body.get("slug") or ""), title)
    description = body.get("description")
    if isinstance(description, str):
        description = description.strip() or None

    if not slug or not is_valid_slug(slug) or not title:
        raise HTTPException(
            status_code=400,
            detail="invalid notebook: slug must use lowercase letters, numbers, and hyphens",
        )
    if db.query(Notebook).filter(Notebook.slug == slug).first():
        raise HTTPException(status_code=409, detail="notebook slug already exists")

    notebook = Notebook(
        slug=slug,
        title=title,
        description=description,
        visibility="private",
        is_default=False,
        created_by=user.id,
    )
    ensure_notebook_dirs(slug)
    db.add(notebook)
    db.commit()
    db.refresh(notebook)

    return {"status": "ok", "notebook": _serialize_notebook(notebook)}


@router.patch("/{slug}")
async def update_notebook(
    slug: str,
    body: dict,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if not user_is_admin(user):
        raise HTTPException(status_code=403, detail="admin role required")
    if not is_valid_slug(slug):
        raise HTTPException(status_code=404, detail="notebook not found")

    notebook = db.query(Notebook).filter(Notebook.slug == slug).first()
    if not notebook or notebook.is_default:
        raise HTTPException(status_code=404, detail="notebook not found")

    title = str(body.get("title") or body.get("name") or notebook.title).strip()
    description = body.get("description", notebook.description)
    if isinstance(description, str):
        description = description.strip() or None
    if not title:
        raise HTTPException(status_code=400, detail="invalid notebook")

    notebook.title = title
    notebook.description = description
    db.commit()
    db.refresh(notebook)
    return {"status": "ok", "notebook": _serialize_notebook(notebook)}
