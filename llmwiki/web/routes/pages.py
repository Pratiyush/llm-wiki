"""Wiki page browsing API."""

from __future__ import annotations

from fastapi import APIRouter, Query

from llmwiki.web.services.wiki_reader import get_tree, list_pages, read_page, render_page, search

router = APIRouter()


@router.get("/tree")
async def api_tree():
    return {"tree": get_tree()}


@router.get("/list")
async def api_list(category: str | None = Query(None)):
    return {"pages": list_pages(category)}


@router.get("/content/{path:path}")
async def api_content(path: str):
    return read_page(path)


@router.get("/rendered/{path:path}")
async def api_rendered(path: str):
    return render_page(path)


@router.get("/index")
async def api_index():
    from llmwiki import REPO_ROOT
    idx = REPO_ROOT / "wiki" / "index.md"
    if not idx.is_file():
        return {"index": ""}
    return {"index": idx.read_text(encoding="utf-8")}


@router.get("/search")
async def api_search(q: str = Query("")):
    return {"results": search(q), "query": q}
