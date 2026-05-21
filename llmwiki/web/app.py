"""FastAPI application for llmwiki web UI."""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from llmwiki import REPO_ROOT

STATIC_DIR = Path(__file__).parent / "static"


def create_app() -> FastAPI:
    app = FastAPI(title="llmwiki-web", docs_url=None, redoc_url=None)

    # --- Database ---
    from llmwiki.web.database import init_db
    init_db()

    # --- API routes ---
    from llmwiki.web.routes import pages, query, upload, graph, manage, auth, notebooks

    app.include_router(auth.router, prefix="/api/auth", tags=["auth"])
    app.include_router(notebooks.router, prefix="/api/notebooks", tags=["notebooks"])
    app.include_router(pages.router, prefix="/api/pages", tags=["pages"])
    app.include_router(query.router, prefix="/api/query", tags=["query"])
    app.include_router(upload.router, prefix="/api/upload", tags=["upload"])
    app.include_router(graph.router, prefix="/api/graph", tags=["graph"])
    app.include_router(manage.router, prefix="/api/manage", tags=["manage"])

    # --- static files ---
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="ui-static")

    # existing built site (if present)
    site_dir = REPO_ROOT / "site"
    if site_dir.is_dir():
        app.mount("/site", StaticFiles(directory=str(site_dir), html=True), name="site")

    # SPA fallback — serve index.html for the root path
    @app.get("/")
    async def index():
        return FileResponse(STATIC_DIR / "index.html")

    @app.get("/favicon.ico")
    async def favicon():
        return FileResponse(STATIC_DIR / "favicon.svg", media_type="image/svg+xml")

    return app
