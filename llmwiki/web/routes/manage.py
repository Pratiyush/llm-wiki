"""Management API — lint, sync, build, status, approvals."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from llmwiki import REPO_ROOT
from llmwiki.web.database import SessionLocal, get_db
from llmwiki.notebooks import DEFAULT_NOTEBOOK_SLUG
from llmwiki.web.models import Notebook, PendingWiki, UploadedFile, KnowledgeLineage, OutdatedFlag, User
from llmwiki.web.routes.auth import get_current_user
from llmwiki.web.services.notebooks import notebook_wiki_dir, validate_notebook_slug
from llmwiki.web.services.wiki_reader import get_stats, invalidate_cache

router = APIRouter()


def _selected_notebook_wiki_dir(db: Session, notebook: str | None) -> tuple[Notebook, Path]:
    slug = (notebook or DEFAULT_NOTEBOOK_SLUG).strip() or DEFAULT_NOTEBOOK_SLUG
    try:
        validate_notebook_slug(slug)
    except ValueError:
        raise HTTPException(status_code=404, detail="notebook not found") from None

    row = db.query(Notebook).filter(Notebook.slug == slug).first()
    if not row:
        raise HTTPException(status_code=404, detail="notebook not found")
    return row, notebook_wiki_dir(row.slug)


def _lineage_wiki_file(db: Session, lineage: KnowledgeLineage) -> Path:
    notebook_id = lineage.notebook_id
    if notebook_id is None:
        source = db.query(UploadedFile).filter(UploadedFile.id == lineage.source_file_id).first()
        notebook_id = source.notebook_id if source else None

    slug = DEFAULT_NOTEBOOK_SLUG
    if notebook_id is not None:
        notebook = db.query(Notebook).filter(Notebook.id == notebook_id).first()
        if notebook:
            slug = notebook.slug
    return notebook_wiki_dir(slug) / lineage.wiki_path


@router.get("/status")
async def get_status():
    return get_stats()


def _make_llm_callback():
    """Create an LLM callback for lint rules."""
    from llmwiki.web.services.glm_client import get_client, MODEL_FLASH
    client = get_client()

    def llm_callback(prompt: str) -> str:
        resp = client.chat.completions.create(
            model=MODEL_FLASH,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.1,
            max_tokens=2000,
        )
        return resp.choices[0].message.content.strip()
    return llm_callback


# --- Lint background task state ---
_lint_result = None
_lint_running = False


def _run_lint_sync(include_llm: bool):
    """Run lint in a background thread."""
    global _lint_result, _lint_running
    try:
        from llmwiki.lint import load_pages, run_all, summarize
        pages = load_pages()
        llm_cb = _make_llm_callback() if include_llm else None
        issues = run_all(pages, include_llm=include_llm, llm_callback=llm_cb)
        summary = summarize(issues)
        issue_list = []
        for issue in issues[:200]:
            issue_list.append({
                "rule": issue.get("rule", ""),
                "severity": issue.get("severity", "info"),
                "page": str(issue.get("page", "")) if issue.get("page") else "",
                "message": issue.get("message", ""),
            })
        _lint_result = {"summary": summary, "issues": issue_list, "total": len(issues), "done": True}
    except Exception as e:
        _lint_result = {"summary": {"error": 1}, "issues": [{"rule": "internal", "severity": "error", "page": "", "message": str(e)}], "total": 1, "done": True}
    finally:
        _lint_running = False


@router.post("/lint")
async def run_lint(body: dict = None):
    """Start lint check. Returns immediately; poll GET /lint for results."""
    global _lint_running, _lint_result
    if _lint_running:
        return {"status": "running"}
    include_llm = (body or {}).get("include_llm", False)
    _lint_running = True
    _lint_result = {"status": "running", "done": False}
    import threading
    t = threading.Thread(target=_run_lint_sync, args=(include_llm,), daemon=True)
    t.start()
    return {"status": "started"}


@router.get("/lint")
async def get_lint_result():
    """Poll for lint results."""
    if _lint_running:
        return {"status": "running", "done": False}
    if _lint_result:
        return _lint_result
    return {"status": "idle", "done": False}


@router.post("/fix-wiki")
async def fix_wiki():
    """One-time fix: create stub pages for all missing wikilinks + rebuild index."""
    import re
    from llmwiki import REPO_ROOT
    from datetime import date
    from pathlib import Path

    WIKILINK_RE = re.compile(r"\[\[([^\]|]+)(?:\|[^\]]*)?\]\]")
    wiki_dir = REPO_ROOT / "wiki"
    today = date.today().isoformat()

    # 1. Scan all existing pages to build slug set
    existing_slugs: set[str] = set()
    for p in wiki_dir.rglob("*.md"):
        rel = str(p.relative_to(wiki_dir))
        slug = rel.rsplit("/", 1)[-1].removesuffix(".md")
        existing_slugs.add(slug)

    # 2. Scan all pages for wikilinks, collect missing targets
    missing_targets: set[str] = set()
    source_map: dict[str, str] = {}  # target → first source that mentions it
    for p in wiki_dir.rglob("*.md"):
        if p.name == "_context.md":
            continue
        try:
            text = p.read_text(encoding="utf-8")
        except OSError:
            continue
        rel = str(p.relative_to(wiki_dir))
        for target in WIKILINK_RE.findall(text):
            t = target.split("#")[0].strip()
            if not t:
                continue
            # Skip if contains path separators or is too long
            if "/" in t or "\\" in t or len(t) > 100:
                continue
            if t not in existing_slugs:
                missing_targets.add(t)
                if t not in source_map:
                    source_map[t] = rel

    # 3. Create stub entity pages for missing targets
    created = []
    entities_dir = wiki_dir / "entities"
    entities_dir.mkdir(parents=True, exist_ok=True)
    for name in sorted(missing_targets):
        # Skip names that would be invalid filenames
        safe_name = name.replace("/", "-").replace("\\", "-").replace(":", "-")
        safe_name = safe_name.strip(". ")
        if not safe_name:
            continue
        entity_path = entities_dir / f"{safe_name}.md"
        if entity_path.exists():
            continue
        src = source_map.get(name, "")
        content = f"""---
title: "{name}"
type: entity
tags: []
sources: [{src}]
last_updated: {today}
---

# {name}

（自动生成的占位页面，待完善）

## Key Facts

- （从 {src} 提取，待完善）

## Connections

- [[{src}]]
"""
        entity_path.write_text(content, encoding="utf-8")
        created.append(name)

    # 4. Rebuild index.md
    _rebuild_index(wiki_dir)

    return {
        "status": "ok",
        "created_pages": len(created),
        "created": created[:50],
        "index_rebuilt": True,
    }


def _rebuild_index(wiki_dir: Path):
    """Rebuild wiki/index.md from all existing pages."""
    from llmwiki.lint import parse_frontmatter
    import re

    sections = {
        "Sources": [],
        "Entities": [],
        "Concepts": [],
        "Syntheses": [],
    }

    for p in sorted(wiki_dir.rglob("*.md")):
        if p.name.startswith("_") or p.name in ("index.md", "overview.md", "log.md",
                "hints.md", "hot.md", "MEMORY.md", "SOUL.md", "CRITICAL_FACTS.md",
                "dashboard.md", "README.md"):
            continue
        rel = str(p.relative_to(wiki_dir))
        try:
            text = p.read_text(encoding="utf-8")
        except OSError:
            continue
        meta = parse_frontmatter(text)
        page_type = meta.get("type", "").lower()
        title = meta.get("title", p.stem)
        if page_type == "source":
            sections["Sources"].append(f"- [{title}]({rel})")
        elif page_type == "entity":
            sections["Entities"].append(f"- [{title}]({rel})")
        elif page_type == "concept":
            sections["Concepts"].append(f"- [{title}]({rel})")
        elif page_type == "synthesis":
            sections["Syntheses"].append(f"- [{title}]({rel})")

    lines = ["# Wiki Index\n"]
    lines.append("## Overview\n- [Overview](overview.md)\n")
    for section_name, entries in sections.items():
        lines.append(f"## {section_name}\n")
        if entries:
            lines.extend(entries)
        else:
            lines.append("- (暂无)\n")
        lines.append("")

    (wiki_dir / "index.md").write_text("\n".join(lines), encoding="utf-8")


@router.post("/sync")
async def run_sync():
    """Trigger session sync."""
    try:
        from llmwiki.convert import convert_all
        rc = convert_all()
        return {"status": "ok", "return_code": rc}
    except Exception as e:
        return {"status": "error", "message": str(e)}


@router.post("/build")
async def run_build():
    """Trigger static site rebuild."""
    try:
        from llmwiki.build import build_site
        from llmwiki import REPO_ROOT
        build_site(out_dir=REPO_ROOT / "site")
        return {"status": "ok"}
    except Exception as e:
        return {"status": "error", "message": str(e)}


@router.get("/deploy-log")
async def get_deploy_log():
    """Return current version and deploy log."""
    version_file = REPO_ROOT / "VERSION"
    version = version_file.read_text(encoding="utf-8").strip() if version_file.exists() else "unknown"

    log_file = REPO_ROOT / "DEPLOY_LOG.md"
    log_content = log_file.read_text(encoding="utf-8") if log_file.exists() else "暂无维护日志"

    return {"version": version, "log": log_content}


# ========== Approval workflow ==========

@router.get("/approvals")
async def list_approvals(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """List pending approvals — leader/admin only."""
    if user.role not in ("leader", "admin"):
        raise HTTPException(status_code=403, detail="需要部门长或管理员权限")

    query = db.query(PendingWiki).filter(PendingWiki.status == "pending")
    # leader sees own department; admin sees all
    if user.role == "leader":
        query = query.filter(PendingWiki.department == user.department)

    items = query.order_by(PendingWiki.created_at.desc()).all()
    result = []
    for item in items:
        proposer = db.query(User).filter(User.id == item.proposer_id).first()
        result.append({
            "id": item.id,
            "question": item.question[:100],
            "answer_preview": item.answer[:200].replace("\n", " "),
            "slug": item.slug,
            "proposer": proposer.full_name or proposer.username if proposer else "未知",
            "department": item.department,
            "created_at": item.created_at.strftime("%Y-%m-%d %H:%M") if item.created_at else "",
        })
    return {"pending": result}


@router.post("/approvals/{item_id}/approve")
async def approve_item(
    item_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Approve a pending wiki — writes to wiki/syntheses/."""
    if user.role not in ("leader", "admin"):
        raise HTTPException(status_code=403, detail="需要部门长或管理员权限")

    item = db.query(PendingWiki).filter(PendingWiki.id == item_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="记录不存在")
    if item.status != "pending":
        raise HTTPException(status_code=400, detail="该记录已被处理")

    # Write to wiki
    from llmwiki.web.routes.query import _write_synthesis
    path = _write_synthesis(item.question, item.answer)

    # Update record
    item.status = "approved"
    item.reviewer_id = user.id
    item.reviewed_at = datetime.now()
    db.commit()

    return {"status": "ok", "path": path}


@router.post("/approvals/{item_id}/reject")
async def reject_item(
    item_id: int,
    body: dict = None,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Reject a pending wiki."""
    if user.role not in ("leader", "admin"):
        raise HTTPException(status_code=403, detail="需要部门长或管理员权限")

    item = db.query(PendingWiki).filter(PendingWiki.id == item_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="记录不存在")
    if item.status != "pending":
        raise HTTPException(status_code=400, detail="该记录已被处理")

    comment = (body or {}).get("comment", "")
    item.status = "rejected"
    item.reviewer_id = user.id
    item.reviewed_at = datetime.now()
    item.review_comment = comment
    db.commit()

    return {"status": "ok"}


# ========== Wiki Content Management ==========

@router.get("/wiki-pages")
async def list_wiki_pages(
    category: str = "sources",
    user: User = Depends(get_current_user),
):
    """List all wiki pages in a category — admin only."""
    if user.role not in ("leader", "admin"):
        raise HTTPException(status_code=403, detail="需要管理员权限")

    wiki_dir = REPO_ROOT / "wiki" / category
    if not wiki_dir.exists():
        return {"pages": []}

    pages = []
    for f in sorted(wiki_dir.rglob("*.md")):
        rel_path = str(f.relative_to(REPO_ROOT / "wiki"))
        # Read frontmatter for title
        title = f.stem
        try:
            content = f.read_text(encoding="utf-8")
            for line in content.split("\n")[:10]:
                if line.startswith("title:"):
                    title = line.split(":", 1)[1].strip().strip('"')
                    break
        except Exception:
            pass

        pages.append({
            "path": rel_path,
            "title": title,
            "size": f.stat().st_size,
        })

    return {"pages": pages, "category": category}


@router.get("/wiki-search")
async def search_all_wiki(
    q: str = "",
    user: User = Depends(get_current_user),
):
    """Search across ALL wiki categories — admin only."""
    if user.role not in ("leader", "admin"):
        raise HTTPException(status_code=403, detail="需要管理员权限")

    if not q.strip():
        return {"results": [], "total": 0}

    query = q.strip().lower()
    categories = ["sources", "syntheses", "entities", "concepts"]
    results = []

    for cat in categories:
        cat_dir = REPO_ROOT / "wiki" / cat
        if not cat_dir.exists():
            continue
        for f in cat_dir.rglob("*.md"):
            try:
                content = f.read_text(encoding="utf-8")
                title = f.stem
                for line in content.split("\n")[:10]:
                    if line.startswith("title:"):
                        title = line.split(":", 1)[1].strip().strip('"')
                        break

                rel_path = str(f.relative_to(REPO_ROOT / "wiki"))
                content_lower = content.lower()
                title_lower = title.lower()
                path_lower = rel_path.lower()

                # Score: title match > path match > content match
                score = 0
                if query in title_lower:
                    score += 20
                if query in path_lower:
                    score += 10
                if query in content_lower:
                    # Count occurrences for relevance
                    score += min(content_lower.count(query), 10)

                if score > 0:
                    results.append({
                        "path": rel_path,
                        "title": title,
                        "category": cat,
                        "score": score,
                        "size": f.stat().st_size,
                    })
            except Exception:
                pass

    # Sort by score descending
    results.sort(key=lambda x: x["score"], reverse=True)
    return {"results": results[:100], "total": len(results)}

@router.get("/wiki-page/{path:path}")
async def get_wiki_page_content(
    path: str,
    user: User = Depends(get_current_user),
):
    """Get content of any wiki page for editing — admin only."""
    if user.role not in ("leader", "admin"):
        raise HTTPException(status_code=403, detail="需要管理员权限")

    wiki_file = REPO_ROOT / "wiki" / path
    if not wiki_file.exists() or not wiki_file.is_file():
        raise HTTPException(status_code=404, detail="页面不存在")

    content = wiki_file.read_text(encoding="utf-8")
    return {"path": path, "content": content}


# --- Specific routes BEFORE generic POST/DELETE to avoid greedy {path} match ---

@router.post("/wiki-page/{path:path}/mark-outdated")
async def mark_wiki_page_outdated(
    path: str,
    user: User = Depends(get_current_user),
):
    """Mark any wiki source page as outdated — returns ALL related items for review."""
    if user.role not in ("leader", "admin"):
        raise HTTPException(status_code=403, detail="需要管理员权限")

    wiki_file = REPO_ROOT / "wiki" / path
    if not wiki_file.exists():
        raise HTTPException(status_code=404, detail="页面不存在")

    page_stem = Path(path).stem
    # Read the source content to find titles/names it mentions
    source_content = ""
    try:
        source_content = wiki_file.read_text(encoding="utf-8")
    except Exception:
        pass

    # Collect all related items, categorized
    related = {
        "source": [{"path": path, "title": _read_title(wiki_file)}],
        "entities": [],
        "concepts": [],
        "syntheses": [],
        "other_sources": [],
    }

    # Search entities
    entities_dir = REPO_ROOT / "wiki" / "entities"
    if entities_dir.exists():
        for ef in entities_dir.glob("*.md"):
            try:
                content = ef.read_text(encoding="utf-8")
                rel = str(ef.relative_to(REPO_ROOT / "wiki"))
                # Match by: page stem in content, path in content, or entity title in source
                title = _read_title(ef)
                if page_stem in content or path in content or (title and title in source_content):
                    related["entities"].append({"path": rel, "title": title})
            except Exception:
                pass

    # Search concepts
    concepts_dir = REPO_ROOT / "wiki" / "concepts"
    if concepts_dir.exists():
        for cf in concepts_dir.glob("*.md"):
            try:
                content = cf.read_text(encoding="utf-8")
                rel = str(cf.relative_to(REPO_ROOT / "wiki"))
                title = _read_title(cf)
                if page_stem in content or path in content or (title and title in source_content):
                    related["concepts"].append({"path": rel, "title": title})
            except Exception:
                pass

    # Search syntheses
    syntheses_dir = REPO_ROOT / "wiki" / "syntheses"
    if syntheses_dir.exists():
        for sf in syntheses_dir.glob("*.md"):
            try:
                content = sf.read_text(encoding="utf-8")
                rel = str(sf.relative_to(REPO_ROOT / "wiki"))
                if page_stem in content or path in content:
                    related["syntheses"].append({"path": rel, "title": _read_title(sf)})
            except Exception:
                pass

    # Search other sources that reference this one
    sources_dir = REPO_ROOT / "wiki" / "sources"
    if sources_dir.exists():
        for sf in sources_dir.rglob("*.md"):
            try:
                rel = str(sf.relative_to(REPO_ROOT / "wiki"))
                if rel == path:
                    continue
                content = sf.read_text(encoding="utf-8")
                if page_stem in content or path in content:
                    related["other_sources"].append({"path": rel, "title": _read_title(sf)})
            except Exception:
                pass

    total = sum(len(v) for v in related.values())
    return {
        "status": "ok",
        "source_path": path,
        "source_title": related["source"][0]["title"] if related["source"] else path,
        "related": related,
        "total": total,
    }


@router.post("/wiki-pages/batch-delete")
async def batch_delete_pages(
    body: dict,
    user: User = Depends(get_current_user),
):
    """Delete multiple wiki pages at once — admin only."""
    if user.role not in ("leader", "admin"):
        raise HTTPException(status_code=403, detail="需要管理员权限")

    paths = body.get("paths", [])
    deleted = []
    not_found = []

    for p in paths:
        wiki_file = REPO_ROOT / "wiki" / p
        if wiki_file.exists():
            wiki_file.unlink()
            deleted.append(p)
        else:
            not_found.append(p)

    # Clean lineage records
    db = SessionLocal()
    for p in deleted:
        db.query(KnowledgeLineage).filter(KnowledgeLineage.wiki_path == p).delete()
    db.commit()

    return {"status": "ok", "deleted": deleted, "deleted_count": len(deleted), "not_found": not_found}


def _read_title(filepath: Path) -> str:
    """Read title from frontmatter of a wiki page."""
    try:
        content = filepath.read_text(encoding="utf-8")
        for line in content.split("\n")[:10]:
            if line.startswith("title:"):
                return line.split(":", 1)[1].strip().strip('"')
    except Exception:
        pass
    return filepath.stem


# --- Generic wiki-page POST/DELETE (must come AFTER specific routes) ---

@router.post("/wiki-page/{path:path}")
async def save_wiki_page_content(
    path: str,
    body: dict,
    user: User = Depends(get_current_user),
):
    """Save edited wiki page content — admin only."""
    if user.role not in ("leader", "admin"):
        raise HTTPException(status_code=403, detail="需要管理员权限")

    wiki_file = REPO_ROOT / "wiki" / path
    if not wiki_file.exists() or not wiki_file.is_file():
        raise HTTPException(status_code=404, detail="页面不存在")

    content = body.get("content", "")
    wiki_file.write_text(content, encoding="utf-8")
    invalidate_cache()
    return {"status": "ok", "path": path}


@router.delete("/wiki-page/{path:path}")
async def delete_wiki_page(
    path: str,
    user: User = Depends(get_current_user),
):
    """Delete a wiki page — admin only."""
    if user.role not in ("leader", "admin"):
        raise HTTPException(status_code=403, detail="需要管理员权限")

    wiki_file = REPO_ROOT / "wiki" / path
    if not wiki_file.exists():
        raise HTTPException(status_code=404, detail="页面不存在")

    wiki_file.unlink()
    invalidate_cache()

    db = SessionLocal()
    db.query(KnowledgeLineage).filter(KnowledgeLineage.wiki_path == path).delete()
    db.commit()

    return {"status": "ok", "path": path}


# ========== Knowledge Audit (file version management) ==========

@router.get("/files")
async def list_uploaded_files(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """List all uploaded files — visible to any logged-in user."""
    files = db.query(UploadedFile).order_by(UploadedFile.uploaded_at.desc()).all()
    result = []
    for f in files:
        lineage_count = db.query(KnowledgeLineage).filter(
            KnowledgeLineage.source_file_id == f.id
        ).count()
        pending_count = db.query(KnowledgeLineage).filter(
            KnowledgeLineage.source_file_id == f.id,
            KnowledgeLineage.wiki_type == "pending_review",
        ).count()
        # Pending flags on this file
        flag_count = db.query(OutdatedFlag).filter(
            OutdatedFlag.file_id == f.id,
            OutdatedFlag.status == "pending",
        ).count()
        uploader = db.query(User).filter(User.id == f.uploader_id).first() if f.uploader_id else None

        result.append({
            "id": f.id,
            "filename": f.filename,
            "wiki_path": f.wiki_path,
            "version_note": f.version_note,
            "status": f.status,
            "uploader": uploader.full_name or uploader.username if uploader else "未知",
            "uploaded_at": f.uploaded_at.strftime("%Y-%m-%d %H:%M") if f.uploaded_at else "",
            "lineage_count": lineage_count,
            "pending_count": pending_count,
            "flag_count": flag_count,
        })
    return {"files": result}


@router.post("/files/{file_id}/flag")
async def flag_file_outdated(
    file_id: int,
    body: dict,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Any logged-in user can flag a file as outdated/error."""
    uf = db.query(UploadedFile).filter(UploadedFile.id == file_id).first()
    if not uf:
        raise HTTPException(status_code=404, detail="文件不存在")
    if uf.status == "outdated":
        raise HTTPException(status_code=400, detail="该文件已被标记为过时")

    reason = body.get("reason", "")

    # Check if user already flagged this file
    existing = db.query(OutdatedFlag).filter(
        OutdatedFlag.file_id == file_id,
        OutdatedFlag.reporter_id == user.id,
        OutdatedFlag.status == "pending",
    ).first()
    if existing:
        raise HTTPException(status_code=400, detail="您已提交过标记，请等待管理员审核")

    flag = OutdatedFlag(
        file_id=file_id,
        reporter_id=user.id,
        reason=reason,
        status="pending",
    )
    db.add(flag)
    db.commit()
    return {"status": "ok", "flag_id": flag.id}


@router.get("/flags")
async def list_pending_flags(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """List pending outdated flags — admin only."""
    if user.role not in ("leader", "admin"):
        raise HTTPException(status_code=403, detail="需要管理员权限")

    flags = db.query(OutdatedFlag).filter(
        OutdatedFlag.status == "pending",
    ).order_by(OutdatedFlag.created_at.desc()).all()

    result = []
    for f in flags:
        reporter = db.query(User).filter(User.id == f.reporter_id).first()
        uf = db.query(UploadedFile).filter(UploadedFile.id == f.file_id).first()
        lineage_count = db.query(KnowledgeLineage).filter(
            KnowledgeLineage.source_file_id == f.file_id,
        ).count()

        result.append({
            "id": f.id,
            "file_id": f.file_id,
            "filename": uf.filename if uf else "未知",
            "version_note": uf.version_note if uf else "",
            "reporter": reporter.full_name or reporter.username if reporter else "未知",
            "department": reporter.department if reporter else "",
            "reason": f.reason,
            "lineage_count": lineage_count,
            "created_at": f.created_at.strftime("%Y-%m-%d %H:%M") if f.created_at else "",
        })
    return {"flags": result}


@router.post("/flags/{flag_id}/confirm")
async def confirm_flag(
    flag_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Admin confirms an outdated flag — marks file outdated + cascade."""
    if user.role not in ("leader", "admin"):
        raise HTTPException(status_code=403, detail="需要管理员权限")

    flag = db.query(OutdatedFlag).filter(OutdatedFlag.id == flag_id).first()
    if not flag:
        raise HTTPException(status_code=404, detail="标记记录不存在")
    if flag.status != "pending":
        raise HTTPException(status_code=400, detail="该标记已被处理")

    uf = db.query(UploadedFile).filter(UploadedFile.id == flag.file_id).first()
    if not uf:
        raise HTTPException(status_code=404, detail="文件不存在")

    # Mark file as outdated
    uf.status = "outdated"

    # Cascade: mark direct lineage as pending_review
    direct_lineages = db.query(KnowledgeLineage).filter(
        KnowledgeLineage.source_file_id == uf.id,
    ).all()

    marked_paths = set()
    for lin in direct_lineages:
        lin.wiki_type = "pending_review"
        marked_paths.add(lin.wiki_path)

    # Cascade: find syntheses that reference any marked source page content
    syntheses_dir = REPO_ROOT / "wiki" / "syntheses"
    if syntheses_dir.exists():
        for syn_file in syntheses_dir.glob("*.md"):
            try:
                content = syn_file.read_text(encoding="utf-8")
                # Check if synthesis references any of the marked source titles
                for path in marked_paths:
                    page_name = Path(path).stem.replace("-", " ")
                    title_from_path = path.split("/")[-1].replace(".md", "")
                    if page_name in content or title_from_path in content or path in content:
                        # Add to lineage if not already tracked
                        existing = db.query(KnowledgeLineage).filter(
                            KnowledgeLineage.source_file_id == uf.id,
                            KnowledgeLineage.wiki_path == str(syn_file.relative_to(REPO_ROOT / "wiki")),
                        ).first()
                        if not existing:
                            db.add(KnowledgeLineage(
                                source_file_id=uf.id,
                                wiki_path=str(syn_file.relative_to(REPO_ROOT / "wiki")),
                                wiki_type="pending_review",
                            ))
                        elif existing.wiki_type != "pending_review":
                            existing.wiki_type = "pending_review"
                        break
            except Exception:
                pass

    # Update flag
    flag.status = "confirmed"
    flag.reviewer_id = user.id
    flag.reviewed_at = datetime.now()

    # Reject other pending flags for the same file
    db.query(OutdatedFlag).filter(
        OutdatedFlag.file_id == flag.file_id,
        OutdatedFlag.status == "pending",
        OutdatedFlag.id != flag_id,
    ).update({"status": "rejected", "reviewer_id": user.id, "reviewed_at": datetime.now()})

    # Count total items marked
    total_marked = db.query(KnowledgeLineage).filter(
        KnowledgeLineage.source_file_id == uf.id,
        KnowledgeLineage.wiki_type == "pending_review",
    ).count()

    db.commit()
    return {"status": "ok", "marked_for_review": total_marked}


@router.post("/flags/{flag_id}/reject")
async def reject_flag(
    flag_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Admin rejects an outdated flag."""
    if user.role not in ("leader", "admin"):
        raise HTTPException(status_code=403, detail="需要管理员权限")

    flag = db.query(OutdatedFlag).filter(OutdatedFlag.id == flag_id).first()
    if not flag:
        raise HTTPException(status_code=404, detail="标记记录不存在")
    if flag.status != "pending":
        raise HTTPException(status_code=400, detail="该标记已被处理")

    flag.status = "rejected"
    flag.reviewer_id = user.id
    flag.reviewed_at = datetime.now()
    db.commit()
    return {"status": "ok"}


@router.get("/audit-queue")
async def get_audit_queue(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    notebook: str = DEFAULT_NOTEBOOK_SLUG,
):
    """List all wiki pages pending review — admin only."""
    if user.role not in ("leader", "admin"):
        raise HTTPException(status_code=403, detail="需要管理员权限")

    selected_notebook, wiki_dir = _selected_notebook_wiki_dir(db, notebook)
    items = db.query(KnowledgeLineage).filter(
        KnowledgeLineage.wiki_type == "pending_review",
        KnowledgeLineage.notebook_id == selected_notebook.id,
    ).all()

    result = []
    seen_paths = set()
    for item in items:
        if item.wiki_path in seen_paths:
            continue
        seen_paths.add(item.wiki_path)

        source = db.query(UploadedFile).filter(UploadedFile.id == item.source_file_id).first()
        wiki_file = wiki_dir / item.wiki_path
        exists = wiki_file.exists()

        # Read content preview
        preview = ""
        if exists:
            try:
                text = wiki_file.read_text(encoding="utf-8")
                preview = text[:200]
            except Exception:
                pass

        result.append({
            "id": item.id,
            "wiki_path": item.wiki_path,
            "source_filename": source.filename if source else "未知",
            "source_id": item.source_file_id,
            "file_exists": exists,
            "preview": preview,
        })

    return {"queue": result}


@router.get("/audit-queue/{lineage_id}/content")
async def get_audited_content(
    lineage_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get full content of a wiki page for editing."""
    if user.role not in ("leader", "admin"):
        raise HTTPException(status_code=403, detail="需要管理员权限")

    lin = db.query(KnowledgeLineage).filter(KnowledgeLineage.id == lineage_id).first()
    if not lin:
        raise HTTPException(status_code=404, detail="记录不存在")

    wiki_file = _lineage_wiki_file(db, lin)
    content = ""
    if wiki_file.exists():
        content = wiki_file.read_text(encoding="utf-8")

    return {"content": content, "path": lin.wiki_path}


@router.post("/audit-queue/{lineage_id}/edit")
async def edit_audited_content(
    lineage_id: int,
    body: dict,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Edit and save a wiki page content."""
    if user.role not in ("leader", "admin"):
        raise HTTPException(status_code=403, detail="需要管理员权限")

    lin = db.query(KnowledgeLineage).filter(KnowledgeLineage.id == lineage_id).first()
    if not lin:
        raise HTTPException(status_code=404, detail="记录不存在")

    new_content = body.get("content", "")
    wiki_file = _lineage_wiki_file(db, lin)
    wiki_file.parent.mkdir(parents=True, exist_ok=True)
    wiki_file.write_text(new_content, encoding="utf-8")

    return {"status": "ok", "path": lin.wiki_path}


@router.post("/audit-queue/{lineage_id}/delete")
async def delete_audited_page(
    lineage_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Delete a wiki page from audit queue."""
    if user.role not in ("leader", "admin"):
        raise HTTPException(status_code=403, detail="需要管理员权限")

    lin = db.query(KnowledgeLineage).filter(KnowledgeLineage.id == lineage_id).first()
    if not lin:
        raise HTTPException(status_code=404, detail="记录不存在")

    wiki_path = lin.wiki_path
    db.query(KnowledgeLineage).filter(
        KnowledgeLineage.wiki_path == wiki_path,
        KnowledgeLineage.notebook_id == lin.notebook_id,
    ).delete()

    wiki_file = _lineage_wiki_file(db, lin)
    deleted_file = False
    if wiki_file.exists():
        wiki_file.unlink()
        deleted_file = True

    db.commit()
    return {"status": "ok", "deleted_file": deleted_file, "path": wiki_path}


@router.post("/audit-queue/{lineage_id}/keep")
async def keep_audited_page(
    lineage_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Keep a wiki page — restore its lineage type."""
    if user.role not in ("leader", "admin"):
        raise HTTPException(status_code=403, detail="需要管理员权限")

    lin = db.query(KnowledgeLineage).filter(KnowledgeLineage.id == lineage_id).first()
    if not lin:
        raise HTTPException(status_code=404, detail="记录不存在")

    for item in db.query(KnowledgeLineage).filter(
        KnowledgeLineage.wiki_path == lin.wiki_path,
        KnowledgeLineage.notebook_id == lin.notebook_id,
    ):
        item.wiki_type = "source"

    db.commit()
    return {"status": "ok", "path": lin.wiki_path}
