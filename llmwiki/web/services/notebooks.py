"""Notebook path, setup, and authorization helpers."""

from __future__ import annotations

import hashlib
import re
import unicodedata
from pathlib import Path
from typing import Any

from sqlalchemy.orm import Session

from llmwiki import REPO_ROOT
from llmwiki.web.models import Notebook

DEFAULT_NOTEBOOK_SLUG = "enterprise-management"
DEFAULT_NOTEBOOK_TITLE = "\u4f01\u4e1a\u7ba1\u7406\u5236\u5ea6"
SLUG_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")

WIKI_SUBDIRS = [
    "sources",
    "entities",
    "concepts",
    "syntheses",
    "categories",
    "hot",
    "projects",
]

PINYIN_BY_CHAR = {
    "\u4f01": "qi",
    "\u4e1a": "ye",
    "\u7ba1": "guan",
    "\u7406": "li",
    "\u5236": "zhi",
    "\u5ea6": "du",
}


def slugify_notebook_title(title: str) -> str:
    """Convert a notebook title into a directory-safe slug."""
    source = title.strip()
    parts: list[str] = []
    for char in source.lower():
        if char.isascii() and char.isalnum():
            parts.append(char)
        elif char in PINYIN_BY_CHAR:
            parts.append(f"-{PINYIN_BY_CHAR[char]}-")
        else:
            normalized = (
                unicodedata.normalize("NFKD", char)
                .encode("ascii", "ignore")
                .decode("ascii")
            )
            parts.append(normalized.lower() if normalized and normalized.isalnum() else "-")

    slug = re.sub(r"[^a-z0-9]+", "-", "".join(parts)).strip("-")
    if slug:
        return slug
    if source:
        digest = hashlib.sha1(source.encode("utf-8")).hexdigest()[:8]
        return f"notebook-{digest}"
    return "notebook"


def validate_notebook_slug(slug: str) -> str:
    """Return a safe notebook slug or raise ValueError."""
    if not SLUG_RE.fullmatch(slug):
        raise ValueError("notebook slug must contain lowercase letters, numbers, and single hyphens only")
    return slug


def notebook_root(slug: str) -> Path:
    slug = validate_notebook_slug(slug)
    base = (REPO_ROOT / "notebooks").resolve()
    path = (base / slug).resolve()
    if path != base and base not in path.parents:
        raise ValueError("notebook slug resolves outside notebooks directory")
    return path


def notebook_wiki_dir(slug: str) -> Path:
    return notebook_root(slug) / "wiki"


def notebook_raw_dir(slug: str) -> Path:
    return notebook_root(slug) / "raw"


def notebook_graph_dir(slug: str) -> Path:
    return notebook_root(slug) / "graph"


def _ensure_gitkeep(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)
    gitkeep = path / ".gitkeep"
    if not gitkeep.exists():
        gitkeep.write_text("", encoding="utf-8")


def ensure_notebook_dirs(slug: str) -> None:
    root = notebook_root(slug)
    wiki_dir = notebook_wiki_dir(slug)

    for path in [root, notebook_raw_dir(slug), wiki_dir, notebook_graph_dir(slug)]:
        _ensure_gitkeep(path)
    for subdir in WIKI_SUBDIRS:
        _ensure_gitkeep(wiki_dir / subdir)


def get_default_notebook(db: Session) -> Notebook | None:
    return db.query(Notebook).filter(Notebook.is_default.is_(True)).first()


def ensure_default_notebook(db: Session) -> Notebook:
    notebook = get_default_notebook(db)
    if notebook:
        ensure_notebook_dirs(notebook.slug)
        return notebook

    notebook = db.query(Notebook).filter(Notebook.slug == DEFAULT_NOTEBOOK_SLUG).first()
    if notebook:
        notebook.title = notebook.title or DEFAULT_NOTEBOOK_TITLE
        notebook.is_default = True
    else:
        notebook = Notebook(
            slug=DEFAULT_NOTEBOOK_SLUG,
            title=DEFAULT_NOTEBOOK_TITLE,
            is_default=True,
        )
        db.add(notebook)
    db.commit()
    db.refresh(notebook)
    ensure_notebook_dirs(notebook.slug)
    return notebook


def can_access_notebook(user: Any, notebook: Notebook) -> bool:
    if getattr(user, "role", None) == "admin":
        return True
    return bool(notebook.is_default)


def can_manage_notebooks(user: Any) -> bool:
    return getattr(user, "role", None) == "admin"
