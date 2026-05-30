"""Document upload API with version tracking and notebook-scoped lineage."""

from __future__ import annotations

from fastapi import APIRouter, File, Form, Header, HTTPException, Query, UploadFile

from llmwiki.web.services.notebooks import DEFAULT_NOTEBOOK_SLUG

router = APIRouter()


def _form_value(value: object, default: str = "") -> str:
    return value if isinstance(value, str) else default


def _bearer_token(authorization: str | None) -> str:
    value = _form_value(authorization).strip()
    scheme, _, token = value.partition(" ")
    if scheme.lower() == "bearer" and token:
        return token.strip()
    return ""


def _record_lineage(
    db,
    *,
    notebook_id: int | None,
    source_file_id: int,
    source_path: str,
    new_pages: list[str],
) -> None:
    from llmwiki.web.models import KnowledgeLineage

    if source_path:
        db.add(
            KnowledgeLineage(
                notebook_id=notebook_id,
                source_file_id=source_file_id,
                wiki_path=source_path,
                wiki_type="source",
            )
        )

    for page in new_pages:
        if page == source_path:
            continue
        page_type = "concept" if page.startswith("concepts/") else "entity"
        db.add(
            KnowledgeLineage(
                notebook_id=notebook_id,
                source_file_id=source_file_id,
                wiki_path=page,
                wiki_type=page_type,
            )
        )


@router.post("/file")
async def upload_file(
    file: UploadFile = File(...),
    version_note: str = Form(""),
    token: str = Form(""),
    notebook: str = Form(""),
    notebook_query: str | None = Query(None, alias="notebook"),
    authorization: str | None = Header(None),
):
    """Upload a file, convert to markdown, create wiki source page with lineage."""
    from llmwiki.web.database import SessionLocal
    from llmwiki.web.models import Notebook, UploadedFile
    from llmwiki.web.services.ingester import process_upload
    from llmwiki.web.services.notebooks import (
        can_access_notebook,
        ensure_default_notebook,
        ensure_notebook_dirs,
        notebook_raw_dir,
        notebook_wiki_dir,
        validate_notebook_slug,
    )

    filename = file.filename or "unnamed"
    content = await file.read()
    version_note = _form_value(version_note)
    token = _form_value(token) or _bearer_token(authorization)
    requested_notebook = (
        _form_value(notebook).strip()
        or _form_value(notebook_query).strip()
        or DEFAULT_NOTEBOOK_SLUG
    )

    if not content:
        return {"status": "error", "message": "empty file"}

    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    if ext not in ("docx", "doc", "pdf", "md", "txt"):
        return {
            "status": "error",
            "message": f"unsupported format: .{ext}; upload .doc/.docx/.pdf/.md/.txt",
        }

    try:
        slug = validate_notebook_slug(requested_notebook)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    db = SessionLocal()
    try:
        if slug == DEFAULT_NOTEBOOK_SLUG:
            notebook_row = ensure_default_notebook(db)
        else:
            notebook_row = db.query(Notebook).filter(Notebook.slug == slug).first()
            if notebook_row is None:
                raise HTTPException(status_code=404, detail="notebook not found")
            ensure_notebook_dirs(slug)

        uploader_id = None
        user = None
        if token:
            try:
                from llmwiki.web.routes.auth import get_current_user

                user = get_current_user(token=token, db=db)
                uploader_id = user.id
            except HTTPException:
                raise
            except Exception:
                user = None

        if not can_access_notebook(user, notebook_row):
            raise HTTPException(status_code=403, detail="notebook access denied")

        uploads_dir = notebook_raw_dir(slug) / "uploads"
        wiki_dir = notebook_wiki_dir(slug)
        ensure_notebook_dirs(slug)
        uploads_dir.mkdir(parents=True, exist_ok=True)

        result = process_upload(filename, content, uploads_dir=uploads_dir, wiki_dir=wiki_dir)

        if result.get("status") == "ok":
            uf = UploadedFile(
                notebook_id=notebook_row.id,
                filename=filename,
                wiki_path=result.get("wiki_path", ""),
                version_note=version_note or "unspecified",
                status="current",
                uploader_id=uploader_id,
            )
            db.add(uf)
            db.flush()

            source_path = result.get("wiki_path", "")
            _record_lineage(
                db,
                notebook_id=notebook_row.id,
                source_file_id=uf.id,
                source_path=source_path,
                new_pages=result.get("new_pages", []),
            )

            db.commit()
            result["version_note"] = version_note or "unspecified"
            result["notebook"] = slug

        return result
    except HTTPException:
        db.rollback()
        raise
    except Exception as exc:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    finally:
        db.close()


@router.post("/url")
async def upload_url(body: dict, authorization: str | None = Header(None)):
    """Import a public URL or pasted web text into a notebook."""
    from llmwiki.web.database import SessionLocal
    from llmwiki.web.models import Notebook, UploadedFile
    from llmwiki.web.services.notebooks import (
        can_access_notebook,
        ensure_default_notebook,
        ensure_notebook_dirs,
        notebook_raw_dir,
        notebook_wiki_dir,
        validate_notebook_slug,
    )
    from llmwiki.web.services.web_ingester import WebImportError, process_web_import

    token = _form_value(body.get("token")) or _bearer_token(authorization)
    requested_notebook = _form_value(body.get("notebook")).strip() or DEFAULT_NOTEBOOK_SLUG
    mode = _form_value(body.get("mode"), "auto") or "auto"
    url = _form_value(body.get("url")).strip()
    title = _form_value(body.get("title")).strip()
    content = _form_value(body.get("content"))
    version_note = _form_value(body.get("version_note")).strip()

    if not url:
        return {"status": "error", "code": "missing_url", "message": "URL is required"}
    if mode not in {"auto", "manual"}:
        return {"status": "error", "code": "invalid_mode", "message": "mode must be auto or manual"}

    try:
        slug = validate_notebook_slug(requested_notebook)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    db = SessionLocal()
    try:
        if slug == DEFAULT_NOTEBOOK_SLUG:
            notebook_row = ensure_default_notebook(db)
        else:
            notebook_row = db.query(Notebook).filter(Notebook.slug == slug).first()
            if notebook_row is None:
                raise HTTPException(status_code=404, detail="notebook not found")
            ensure_notebook_dirs(slug)

        uploader_id = None
        user = None
        if token:
            try:
                from llmwiki.web.routes.auth import get_current_user

                user = get_current_user(token=token, db=db)
                uploader_id = user.id
            except HTTPException:
                raise
            except Exception:
                user = None

        if not can_access_notebook(user, notebook_row):
            raise HTTPException(status_code=403, detail="notebook access denied")

        raw_dir = notebook_raw_dir(slug) / "web"
        wiki_dir = notebook_wiki_dir(slug)
        ensure_notebook_dirs(slug)
        result = process_web_import(
            url,
            title=title,
            content=content,
            mode=mode,
            raw_dir=raw_dir,
            wiki_dir=wiki_dir,
        )

        if result.get("status") == "ok":
            uf = UploadedFile(
                notebook_id=notebook_row.id,
                filename=result.get("title") or url,
                wiki_path=result.get("wiki_path", ""),
                version_note=version_note or "web import",
                status="current",
                uploader_id=uploader_id,
            )
            db.add(uf)
            db.flush()
            _record_lineage(
                db,
                notebook_id=notebook_row.id,
                source_file_id=uf.id,
                source_path=result.get("wiki_path", ""),
                new_pages=result.get("new_pages", []),
            )
            db.commit()
            result["version_note"] = version_note or "web import"
            result["notebook"] = slug

        return result
    except WebImportError as exc:
        db.rollback()
        return {"status": "error", "code": exc.code, "message": exc.message}
    except HTTPException:
        db.rollback()
        raise
    except Exception as exc:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    finally:
        db.close()
