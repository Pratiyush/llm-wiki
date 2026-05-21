"""Document upload API — with version tracking and lineage."""

from __future__ import annotations

from fastapi import APIRouter, UploadFile, File, Form

router = APIRouter()


@router.post("/file")
async def upload_file(
    file: UploadFile = File(...),
    version_note: str = Form(""),
    token: str = Form(""),
):
    """Upload a file, convert to markdown, create wiki source page with lineage."""
    from llmwiki.web.services.ingester import process_upload
    from llmwiki.web.database import SessionLocal

    filename = file.filename or "unnamed"
    content = await file.read()

    if not content:
        return {"status": "error", "message": "文件为空"}

    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    if ext not in ("docx", "doc", "pdf", "md", "txt"):
        return {"status": "error", "message": f"不支持的格式: .{ext}，请上传 .doc/.docx/.pdf/.md/.txt 文件"}

    result = process_upload(filename, content)

    # Record uploaded file + lineage
    if result.get("status") == "ok":
        try:
            db = SessionLocal()

            # Resolve uploader
            uploader_id = None
            if token:
                try:
                    from llmwiki.web.routes.auth import get_current_user
                    user = get_current_user(token=token, db=db)
                    uploader_id = user.id
                except Exception:
                    pass

            # Create uploaded file record
            from llmwiki.web.models import UploadedFile, KnowledgeLineage
            uf = UploadedFile(
                filename=filename,
                wiki_path=result.get("wiki_path", ""),
                version_note=version_note or "未填写",
                status="current",
                uploader_id=uploader_id,
            )
            db.add(uf)
            db.flush()

            # Record lineage for the source page
            source_path = result.get("wiki_path", "")
            if source_path:
                lineage = KnowledgeLineage(
                    source_file_id=uf.id,
                    wiki_path=source_path,
                    wiki_type="source",
                )
                db.add(lineage)

            # Record lineage for new entity/concept pages
            for page in result.get("new_pages", []):
                if page != source_path:
                    page_type = "entity"
                    if "/concepts/" in page:
                        page_type = "concept"
                    lineage = KnowledgeLineage(
                        source_file_id=uf.id,
                        wiki_path=page,
                        wiki_type=page_type,
                    )
                    db.add(lineage)

            db.commit()
            result["version_note"] = version_note or "未填写"
        except Exception as e:
            # Don't fail upload if lineage recording fails
            import logging
            logging.warning(f"Lineage recording failed: {e}")

    return result
