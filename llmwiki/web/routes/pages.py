"""Wiki page browsing API."""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, HTTPException, Query

from llmwiki.notebooks import DEFAULT_NOTEBOOK_SLUG, is_valid_slug, notebook_wiki_dir
from llmwiki.web.services.wiki_reader import get_tree, list_pages, read_page, render_page, search

router = APIRouter()


def _wiki_dir_or_404(notebook: str | None) -> Path:
    if notebook is None:
        slug = DEFAULT_NOTEBOOK_SLUG
    elif is_valid_slug(notebook):
        slug = notebook
    else:
        raise HTTPException(status_code=404, detail="notebook wiki not found")
    wiki_dir = notebook_wiki_dir(slug)
    if not wiki_dir.is_dir():
        raise HTTPException(status_code=404, detail="notebook wiki not found")
    return wiki_dir


@router.get("/tree")
async def api_tree(notebook: str | None = Query(None)):
    wiki_dir = _wiki_dir_or_404(notebook)
    return {"tree": get_tree(wiki_dir=wiki_dir)}


@router.get("/list")
async def api_list(
    category: str | None = Query(None),
    notebook: str | None = Query(None),
):
    wiki_dir = _wiki_dir_or_404(notebook)
    return {"pages": list_pages(category, wiki_dir=wiki_dir)}


@router.get("/content/{path:path}")
async def api_content(path: str, notebook: str | None = Query(None)):
    wiki_dir = _wiki_dir_or_404(notebook)
    return read_page(path, wiki_dir=wiki_dir)


@router.get("/rendered/{path:path}")
async def api_rendered(path: str, notebook: str | None = Query(None)):
    wiki_dir = _wiki_dir_or_404(notebook)
    return render_page(path, wiki_dir=wiki_dir)


@router.get("/index")
async def api_index(notebook: str | None = Query(None)):
    wiki_dir = _wiki_dir_or_404(notebook)
    idx = wiki_dir / "index.md"
    if not idx.is_file():
        return {"index": ""}
    return {"index": idx.read_text(encoding="utf-8")}


@router.get("/search")
async def api_search(q: str = Query(""), notebook: str | None = Query(None)):
    wiki_dir = _wiki_dir_or_404(notebook)
    return {"results": search(q, wiki_dir=wiki_dir), "query": q}
