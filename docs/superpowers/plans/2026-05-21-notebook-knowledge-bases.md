# Notebook Knowledge Bases Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add notebook-scoped knowledge bases so the default enterprise-management knowledge base stays isolated while admins can create private learning notebooks and ask questions against each notebook's uploaded materials.

**Architecture:** Introduce a `Notebook` database model plus a notebook service that resolves authorized notebook roots. Migrate Web routes and services from global `wiki/` access to notebook-scoped `wiki_dir`, `raw_dir`, and `graph_dir`, then add admin-only notebook selection and management in the frontend.

**Tech Stack:** Python 3.9+, FastAPI, SQLAlchemy, SQLite, Vanilla JavaScript, pytest.

---

## File Structure

- Create: `llmwiki/notebooks.py`
  - Owns notebook constants, slug validation, directory creation, access checks, metadata file writing, and default notebook bootstrap.
- Modify: `llmwiki/web/models.py`
  - Adds `Notebook`; adds `notebook_id` to scoped tables.
- Modify: `llmwiki/web/database.py`
  - Adds idempotent SQLite migrations for notebook tables and columns.
- Modify: `llmwiki/cli.py`
  - Adds `llmwiki notebooks migrate-default --dry-run`.
- Create: `llmwiki/web/routes/notebooks.py`
  - Lists accessible notebooks and supports admin create/update/archive/delete-empty actions.
- Modify: `llmwiki/web/app.py`
  - Registers notebook routes.
- Modify: `llmwiki/web/services/wiki_reader.py`
  - Accepts notebook-scoped `wiki_dir`; removes global-only behavior from public functions.
- Modify: `llmwiki/graph.py`
  - Accepts `wiki_dir` and `graph_dir` parameters.
- Modify: `llmwiki/web/routes/pages.py`
  - Reads notebook slug and authorizes before browsing/searching pages.
- Modify: `llmwiki/web/routes/graph.py`
  - Returns graph for the selected notebook only.
- Modify: `llmwiki/web/services/ingester.py`
  - Writes uploaded raw files and wiki pages into the selected notebook.
- Modify: `llmwiki/web/routes/upload.py`
  - Accepts `notebook_slug`, authorizes it, records `notebook_id`.
- Modify: `llmwiki/web/services/glm_client.py`
  - Builds context from selected notebook; supports admin-only cross-notebook context.
- Modify: `llmwiki/web/routes/query.py`
  - Passes notebook context through Q&A, streaming, agent loop, history, save synthesis, and thread endpoints.
- Modify: `llmwiki/web/static/index.html`
  - Adds admin notebook selector and notebook management controls.
- Modify: `llmwiki/web/static/api.js`
  - Adds notebook-aware API helpers.
- Modify: `llmwiki/web/static/app.js`
  - Initializes notebook state before notebook-scoped components load.
- Modify: `llmwiki/web/static/components/*.js`
  - Browser, QA, uploader, graph, manager, and threads use selected notebook.
- Modify: `.gitignore`
  - Ignores runtime database, JWT secret, env files, and notebook upload raw files.
- Modify: `USERGUIDE.md`, `README.md`
  - Documents Web notebook mode and its first-version scope.
- Test: `tests/test_notebooks.py`
- Test: `tests/test_notebook_migration.py`
- Test: `tests/test_notebook_wiki_reader.py`
- Test: `tests/test_notebook_permissions.py`
- Test: `tests/test_notebook_query_scope.py`

---

### Task 1: Notebook Model, Migration Columns, and Service

**Files:**
- Create: `llmwiki/notebooks.py`
- Modify: `llmwiki/web/models.py`
- Modify: `llmwiki/web/database.py`
- Test: `tests/test_notebooks.py`

- [ ] **Step 1: Write the failing notebook service tests**

Create `tests/test_notebooks.py`:

```python
from pathlib import Path

import pytest

from llmwiki.notebooks import (
    DEFAULT_NOTEBOOK_SLUG,
    NotebookAccessError,
    NotebookNotFoundError,
    NotebookPaths,
    ensure_notebook_dirs,
    is_valid_slug,
    notebook_paths,
)


def test_slug_validation_accepts_safe_slugs():
    assert is_valid_slug("enterprise-management")
    assert is_valid_slug("ai-2026")


@pytest.mark.parametrize("slug", ["", ".", "..", "../x", "AI", "a_b", "a/b", "a b", "中文"])
def test_slug_validation_rejects_unsafe_slugs(slug):
    assert not is_valid_slug(slug)


def test_notebook_paths_are_inside_notebooks_root(tmp_path):
    paths = notebook_paths("ai", notebooks_root=tmp_path / "notebooks")
    assert isinstance(paths, NotebookPaths)
    assert paths.root == tmp_path / "notebooks" / "ai"
    assert paths.raw_dir == paths.root / "raw"
    assert paths.wiki_dir == paths.root / "wiki"
    assert paths.graph_dir == paths.root / "graph"


def test_notebook_paths_reject_path_traversal(tmp_path):
    with pytest.raises(ValueError):
        notebook_paths("../escape", notebooks_root=tmp_path / "notebooks")


def test_ensure_notebook_dirs_writes_metadata(tmp_path):
    paths = notebook_paths(DEFAULT_NOTEBOOK_SLUG, notebooks_root=tmp_path / "notebooks")
    ensure_notebook_dirs(
        paths,
        slug=DEFAULT_NOTEBOOK_SLUG,
        name="Enterprise Management",
        description="Default notebook",
        visibility="public",
        is_default=True,
    )
    assert (paths.root / "notebook.json").is_file()
    assert (paths.wiki_dir / "sources").is_dir()
    assert (paths.wiki_dir / "entities").is_dir()
    assert (paths.wiki_dir / "concepts").is_dir()
    assert (paths.wiki_dir / "syntheses").is_dir()
```

- [ ] **Step 2: Run the failing tests**

Run:

```bash
pytest tests/test_notebooks.py -q
```

Expected: FAIL because `llmwiki.notebooks` does not exist.

- [ ] **Step 3: Add the Notebook model**

In `llmwiki/web/models.py`, add imports if needed:

```python
from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text
```

Add this model above `User`:

```python
class Notebook(Base):
    __tablename__ = "notebooks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    slug: Mapped[str] = mapped_column(String(80), unique=True, nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    description: Mapped[str] = mapped_column(Text, default="")
    owner_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("users.id"), nullable=True)
    visibility: Mapped[str] = mapped_column(String(20), default="private")
    is_default: Mapped[bool] = mapped_column(Boolean, default=False)
    is_archived: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
```

Add nullable `notebook_id` columns to these models:

```python
notebook_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("notebooks.id"), nullable=True)
```

Apply it to `PendingWiki`, `ChatHistory`, `Conversation`, `UploadedFile`, `KnowledgeLineage`, and `OutdatedFlag`.

- [ ] **Step 4: Add idempotent schema migrations**

In `llmwiki/web/database.py`, extend `init_db()` after `Base.metadata.create_all(bind=engine)`:

```python
    with engine.connect() as conn:
        def columns(table: str) -> set[str]:
            return {row[1] for row in conn.execute(sa.text(f"PRAGMA table_info({table})")).fetchall()}

        for table in (
            "pending_wikis",
            "chat_history",
            "conversations",
            "uploaded_files",
            "knowledge_lineage",
            "outdated_flags",
        ):
            if "notebook_id" not in columns(table):
                conn.execute(sa.text(f"ALTER TABLE {table} ADD COLUMN notebook_id INTEGER REFERENCES notebooks(id)"))

        if "is_archived" not in columns("notebooks"):
            conn.execute(sa.text("ALTER TABLE notebooks ADD COLUMN is_archived BOOLEAN DEFAULT FALSE"))

        conn.commit()
```

Keep the existing `chat_history.thread_id` migration, but rewrite it to reuse the `columns("chat_history")` helper so repeated runs remain safe.

- [ ] **Step 5: Implement `llmwiki/notebooks.py`**

Create `llmwiki/notebooks.py`:

```python
from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Iterable

from llmwiki import REPO_ROOT

DEFAULT_NOTEBOOK_SLUG = "enterprise-management"
DEFAULT_NOTEBOOK_NAME = "企业管理制度"
NOTEBOOKS_ROOT = REPO_ROOT / "notebooks"
_SLUG_RE = re.compile(r"^[a-z0-9](?:[a-z0-9-]{0,78}[a-z0-9])?$")


class NotebookAccessError(PermissionError):
    pass


class NotebookNotFoundError(FileNotFoundError):
    pass


@dataclass(frozen=True)
class NotebookPaths:
    slug: str
    root: Path
    raw_dir: Path
    wiki_dir: Path
    graph_dir: Path
    uploads_dir: Path


def is_valid_slug(slug: str) -> bool:
    return bool(_SLUG_RE.fullmatch(slug or ""))


def notebook_paths(slug: str, *, notebooks_root: Path = NOTEBOOKS_ROOT) -> NotebookPaths:
    if not is_valid_slug(slug):
        raise ValueError(f"invalid notebook slug: {slug!r}")
    root = (notebooks_root / slug).resolve()
    notebooks_root_resolved = notebooks_root.resolve()
    try:
        root.relative_to(notebooks_root_resolved)
    except ValueError as exc:
        raise ValueError(f"notebook path escapes notebooks root: {slug!r}") from exc
    return NotebookPaths(
        slug=slug,
        root=root,
        raw_dir=root / "raw",
        wiki_dir=root / "wiki",
        graph_dir=root / "graph",
        uploads_dir=root / "raw" / "uploads",
    )


def ensure_notebook_dirs(
    paths: NotebookPaths,
    *,
    slug: str,
    name: str,
    description: str = "",
    visibility: str = "private",
    is_default: bool = False,
) -> None:
    for directory in (
        paths.raw_dir,
        paths.uploads_dir,
        paths.wiki_dir / "sources",
        paths.wiki_dir / "entities",
        paths.wiki_dir / "concepts",
        paths.wiki_dir / "syntheses",
        paths.graph_dir,
    ):
        directory.mkdir(parents=True, exist_ok=True)

    metadata = {
        "slug": slug,
        "name": name,
        "description": description,
        "visibility": visibility,
        "is_default": is_default,
        "updated_at": datetime.now().isoformat(timespec="seconds"),
    }
    (paths.root / "notebook.json").write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
```

- [ ] **Step 6: Run notebook service tests**

Run:

```bash
pytest tests/test_notebooks.py -q
```

Expected: PASS.

- [ ] **Step 7: Run existing database model smoke tests**

Run:

```bash
pytest tests/test_web_clipper.py tests/test_cli.py -q
```

Expected: PASS or unrelated existing failures only. Investigate any failure that mentions SQLAlchemy models, `init_db`, or `Notebook`.

- [ ] **Step 8: Commit**

```bash
git add llmwiki/notebooks.py llmwiki/web/models.py llmwiki/web/database.py tests/test_notebooks.py
git commit -m "feat: add notebook model and service"
```

---

### Task 2: Default Notebook Bootstrap and Migration Command

**Files:**
- Modify: `llmwiki/notebooks.py`
- Modify: `llmwiki/cli.py`
- Test: `tests/test_notebook_migration.py`

- [ ] **Step 1: Write migration tests**

Create `tests/test_notebook_migration.py`:

```python
from pathlib import Path

from llmwiki.notebooks import DEFAULT_NOTEBOOK_SLUG, migrate_default_notebook


def test_migrate_default_notebook_dry_run_does_not_write(tmp_path):
    repo = tmp_path
    (repo / "wiki").mkdir()
    (repo / "wiki" / "index.md").write_text("# Wiki Index\n", encoding="utf-8")
    (repo / "raw" / "company-docs").mkdir(parents=True)
    (repo / "raw" / "company-docs" / "doc.md").write_text("source", encoding="utf-8")

    result = migrate_default_notebook(repo_root=repo, dry_run=True)

    assert result["would_copy"]
    assert not (repo / "notebooks" / DEFAULT_NOTEBOOK_SLUG).exists()


def test_migrate_default_notebook_copies_existing_wiki_and_raw(tmp_path):
    repo = tmp_path
    (repo / "wiki").mkdir()
    (repo / "wiki" / "index.md").write_text("# Wiki Index\n", encoding="utf-8")
    (repo / "graph").mkdir()
    (repo / "graph" / "graph.json").write_text("{}", encoding="utf-8")
    (repo / "raw" / "company-docs").mkdir(parents=True)
    (repo / "raw" / "company-docs" / "policy.md").write_text("policy", encoding="utf-8")

    result = migrate_default_notebook(repo_root=repo, dry_run=False)

    root = repo / "notebooks" / DEFAULT_NOTEBOOK_SLUG
    assert result["copied"]
    assert (root / "wiki" / "index.md").read_text(encoding="utf-8") == "# Wiki Index\n"
    assert (root / "raw" / "company-docs" / "policy.md").read_text(encoding="utf-8") == "policy"
    assert (root / "graph" / "graph.json").read_text(encoding="utf-8") == "{}"
    assert (root / "notebook.json").is_file()


def test_migrate_default_notebook_refuses_overwrite(tmp_path):
    repo = tmp_path
    (repo / "wiki").mkdir()
    (repo / "wiki" / "index.md").write_text("# Wiki Index\n", encoding="utf-8")
    target = repo / "notebooks" / DEFAULT_NOTEBOOK_SLUG / "wiki"
    target.mkdir(parents=True)
    (target / "index.md").write_text("existing", encoding="utf-8")

    result = migrate_default_notebook(repo_root=repo, dry_run=False)

    assert result["blocked"]
    assert (target / "index.md").read_text(encoding="utf-8") == "existing"
```

- [ ] **Step 2: Run failing migration tests**

Run:

```bash
pytest tests/test_notebook_migration.py -q
```

Expected: FAIL because `migrate_default_notebook` is not implemented.

- [ ] **Step 3: Implement copy helpers and migration**

Add to `llmwiki/notebooks.py`:

```python
import shutil


def _copytree_no_overwrite(src: Path, dst: Path, copied: list[str], blocked: list[str]) -> None:
    if not src.exists():
        return
    if dst.exists() and any(dst.iterdir()):
        blocked.append(str(dst))
        return
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(src, dst, dirs_exist_ok=True)
    copied.append(f"{src} -> {dst}")


def migrate_default_notebook(*, repo_root: Path = REPO_ROOT, dry_run: bool = False) -> dict[str, object]:
    paths = notebook_paths(DEFAULT_NOTEBOOK_SLUG, notebooks_root=repo_root / "notebooks")
    sources = [
        (repo_root / "wiki", paths.wiki_dir),
        (repo_root / "graph", paths.graph_dir),
        (repo_root / "raw" / "company-docs", paths.raw_dir / "company-docs"),
    ]
    would_copy = [f"{src} -> {dst}" for src, dst in sources if src.exists()]
    if dry_run:
        return {"dry_run": True, "would_copy": would_copy, "copied": [], "blocked": []}

    copied: list[str] = []
    blocked: list[str] = []
    ensure_notebook_dirs(
        paths,
        slug=DEFAULT_NOTEBOOK_SLUG,
        name=DEFAULT_NOTEBOOK_NAME,
        description="Default enterprise management notebook",
        visibility="public",
        is_default=True,
    )
    for src, dst in sources:
        _copytree_no_overwrite(src, dst, copied, blocked)
    return {"dry_run": False, "would_copy": would_copy, "copied": copied, "blocked": blocked}
```

- [ ] **Step 4: Add CLI subcommand**

In `llmwiki/cli.py`, add command function:

```python
def cmd_notebooks(args: argparse.Namespace) -> int:
    from llmwiki.notebooks import migrate_default_notebook

    if args.notebook_cmd == "migrate-default":
        result = migrate_default_notebook(dry_run=args.dry_run)
        if result["dry_run"]:
            print("Dry run: default notebook migration plan")
            for line in result["would_copy"]:
                print(f"  would copy {line}")
            return 0
        if result["blocked"]:
            print("Migration blocked; target directories already contain files:")
            for line in result["blocked"]:
                print(f"  {line}")
            return 1
        print("Default notebook migration complete:")
        for line in result["copied"]:
            print(f"  copied {line}")
        return 0
    print(f"error: unknown notebooks command {args.notebook_cmd!r}", file=sys.stderr)
    return 2
```

In `build_parser()`, add:

```python
    notebooks = sub.add_parser("notebooks", help="Manage notebook knowledge bases")
    notebooks_sub = notebooks.add_subparsers(dest="notebook_cmd", metavar="NOTEBOOK_COMMAND")
    migrate = notebooks_sub.add_parser("migrate-default", help="Migrate existing wiki/raw into the default notebook")
    migrate.add_argument("--dry-run", action="store_true")
    migrate.set_defaults(func=cmd_notebooks)
```

- [ ] **Step 5: Run migration tests and CLI smoke**

Run:

```bash
pytest tests/test_notebook_migration.py tests/test_cli.py -q
python -m llmwiki notebooks migrate-default --dry-run
```

Expected: tests PASS; dry-run prints copy plan or an empty plan without writing files.

- [ ] **Step 6: Commit**

```bash
git add llmwiki/notebooks.py llmwiki/cli.py tests/test_notebook_migration.py
git commit -m "feat: add default notebook migration"
```

---

### Task 3: Notebook-Scoped Wiki Reader and Pages API

**Files:**
- Modify: `llmwiki/notebooks.py`
- Modify: `llmwiki/web/services/wiki_reader.py`
- Modify: `llmwiki/web/routes/pages.py`
- Create: `llmwiki/web/routes/notebooks.py`
- Modify: `llmwiki/web/app.py`
- Test: `tests/test_notebook_wiki_reader.py`

- [ ] **Step 1: Write scoped wiki reader tests**

Create `tests/test_notebook_wiki_reader.py`:

```python
from pathlib import Path

from llmwiki.web.services import wiki_reader


def _write_page(root: Path, rel: str, title: str, body: str):
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(f'---\ntitle: "{title}"\ntype: source\n---\n\n{body}', encoding="utf-8")


def test_search_is_scoped_to_wiki_dir(tmp_path):
    a = tmp_path / "a" / "wiki"
    b = tmp_path / "b" / "wiki"
    _write_page(a, "sources/a.md", "A", "alpha-only material")
    _write_page(b, "sources/b.md", "B", "beta-only material")

    assert wiki_reader.search("alpha-only", wiki_dir=a)
    assert wiki_reader.search("alpha-only", wiki_dir=b) == []


def test_get_tree_is_scoped_to_wiki_dir(tmp_path):
    a = tmp_path / "a" / "wiki"
    b = tmp_path / "b" / "wiki"
    _write_page(a, "sources/a.md", "A", "alpha")
    _write_page(b, "sources/b.md", "B", "beta")

    tree = wiki_reader.get_tree(wiki_dir=a)

    assert tree["sources"][0]["title"] == "A"
    assert "B" not in str(tree)
```

- [ ] **Step 2: Run failing tests**

Run:

```bash
pytest tests/test_notebook_wiki_reader.py -q
```

Expected: FAIL because `wiki_reader` functions do not accept `wiki_dir`.

- [ ] **Step 3: Refactor wiki reader signatures**

In `llmwiki/web/services/wiki_reader.py`, replace global-only usage with helpers:

```python
DEFAULT_WIKI_DIR = REPO_ROOT / "wiki"


def _resolve_wiki_dir(wiki_dir: Path | None = None) -> Path:
    return wiki_dir or DEFAULT_WIKI_DIR
```

Change public functions:

```python
def get_tree(*, wiki_dir: Path | None = None) -> dict:
    root = _resolve_wiki_dir(wiki_dir)
    ...
    for path in sorted(root.rglob("*.md")):
        rel = path.relative_to(root)
```

Apply the same pattern to:

```python
def list_pages(category: str | None = None, *, wiki_dir: Path | None = None) -> list[dict]:
def read_page(path: str, *, wiki_dir: Path | None = None) -> dict:
def render_page(path: str, *, wiki_dir: Path | None = None) -> dict:
def search(query: str, limit: int = 20, *, wiki_dir: Path | None = None) -> list[dict]:
def get_stats(*, wiki_dir: Path | None = None) -> dict:
```

Include `str(root)` in cache keys:

```python
cache_key = f"page:{root}:{path}"
cache_key = f":search:{root}:{query}:{limit}"
```

- [ ] **Step 4: Add route-level notebook resolution**

In `llmwiki/notebooks.py`, add minimal DB-aware helpers:

```python
def current_notebook_slug(raw: str | None) -> str:
    return raw if raw and is_valid_slug(raw) else DEFAULT_NOTEBOOK_SLUG
```

In `llmwiki/web/routes/pages.py`, accept a query param:

```python
from pathlib import Path
from fastapi import APIRouter, Query, HTTPException
from llmwiki.notebooks import current_notebook_slug, notebook_paths


def _wiki_dir(notebook: str | None) -> Path:
    slug = current_notebook_slug(notebook)
    paths = notebook_paths(slug)
    if not paths.wiki_dir.is_dir():
        raise HTTPException(status_code=404, detail="notebook wiki not found")
    return paths.wiki_dir
```

Update endpoints:

```python
@router.get("/tree")
async def api_tree(notebook: str | None = Query(None)):
    return {"tree": get_tree(wiki_dir=_wiki_dir(notebook))}
```

Apply the same to list, content, rendered, index, and search.

- [ ] **Step 5: Add notebook listing route skeleton**

Create `llmwiki/web/routes/notebooks.py`:

```python
from __future__ import annotations

from fastapi import APIRouter

from llmwiki.notebooks import DEFAULT_NOTEBOOK_NAME, DEFAULT_NOTEBOOK_SLUG

router = APIRouter()


@router.get("")
async def list_notebooks():
    return {
        "notebooks": [
            {
                "slug": DEFAULT_NOTEBOOK_SLUG,
                "name": DEFAULT_NOTEBOOK_NAME,
                "description": "Default enterprise management notebook",
                "is_default": True,
                "visibility": "public",
            }
        ]
    }
```

Register in `llmwiki/web/app.py`:

```python
from llmwiki.web.routes import pages, query, upload, graph, manage, auth, notebooks
app.include_router(notebooks.router, prefix="/api/notebooks", tags=["notebooks"])
```

- [ ] **Step 6: Run scoped reader tests**

Run:

```bash
pytest tests/test_notebook_wiki_reader.py -q
```

Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add llmwiki/notebooks.py llmwiki/web/services/wiki_reader.py llmwiki/web/routes/pages.py llmwiki/web/routes/notebooks.py llmwiki/web/app.py tests/test_notebook_wiki_reader.py
git commit -m "feat: scope wiki browsing by notebook"
```

---

### Task 4: Notebook Permissions and Admin Notebook API

**Files:**
- Modify: `llmwiki/notebooks.py`
- Modify: `llmwiki/web/routes/notebooks.py`
- Modify: `llmwiki/web/routes/pages.py`
- Test: `tests/test_notebook_permissions.py`

- [ ] **Step 1: Write permission tests**

Create `tests/test_notebook_permissions.py`:

```python
from types import SimpleNamespace

from llmwiki.notebooks import can_access_notebook


def test_non_admin_can_only_access_default_notebook():
    user = SimpleNamespace(id=2, role="staff")
    default_nb = SimpleNamespace(slug="enterprise-management", owner_id=None, is_default=True, visibility="public")
    private_nb = SimpleNamespace(slug="ai", owner_id=1, is_default=False, visibility="private")

    assert can_access_notebook(user, default_nb)
    assert not can_access_notebook(user, private_nb)


def test_admin_can_access_default_and_owned_private_notebook():
    user = SimpleNamespace(id=1, role="admin")
    default_nb = SimpleNamespace(slug="enterprise-management", owner_id=None, is_default=True, visibility="public")
    private_nb = SimpleNamespace(slug="ai", owner_id=1, is_default=False, visibility="private")

    assert can_access_notebook(user, default_nb)
    assert can_access_notebook(user, private_nb)


def test_admin_cannot_access_other_admin_private_notebook():
    user = SimpleNamespace(id=1, role="admin")
    private_nb = SimpleNamespace(slug="legal-research", owner_id=2, is_default=False, visibility="private")

    assert not can_access_notebook(user, private_nb)
```

- [ ] **Step 2: Run failing tests**

Run:

```bash
pytest tests/test_notebook_permissions.py -q
```

Expected: FAIL because `can_access_notebook` is not implemented.

- [ ] **Step 3: Implement access helpers**

Add to `llmwiki/notebooks.py`:

```python
def can_access_notebook(user: object | None, notebook: object) -> bool:
    if getattr(notebook, "is_default", False):
        return True
    if user is None:
        return False
    role = getattr(user, "role", "")
    if role != "admin":
        return False
    return getattr(notebook, "owner_id", None) == getattr(user, "id", None)


def user_is_admin(user: object | None) -> bool:
    return bool(user and getattr(user, "role", "") == "admin")
```

- [ ] **Step 4: Implement admin create endpoint**

In `llmwiki/web/routes/notebooks.py`, expand from skeleton:

```python
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from llmwiki.notebooks import ensure_notebook_dirs, is_valid_slug, notebook_paths, user_is_admin
from llmwiki.web.database import get_db
from llmwiki.web.models import Notebook, User
from llmwiki.web.routes.auth import get_current_user


@router.post("")
async def create_notebook(
    body: dict,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if not user_is_admin(user):
        raise HTTPException(status_code=403, detail="admin only")
    slug = (body.get("slug") or "").strip().lower()
    name = (body.get("name") or "").strip()
    description = (body.get("description") or "").strip()
    if not name:
        raise HTTPException(status_code=400, detail="name is required")
    if not is_valid_slug(slug):
        raise HTTPException(status_code=400, detail="invalid slug")
    if db.query(Notebook).filter(Notebook.slug == slug).first():
        raise HTTPException(status_code=409, detail="notebook slug already exists")

    notebook = Notebook(
        slug=slug,
        name=name,
        description=description,
        owner_id=user.id,
        visibility="private",
        is_default=False,
    )
    db.add(notebook)
    db.commit()
    paths = notebook_paths(slug)
    ensure_notebook_dirs(paths, slug=slug, name=name, description=description, visibility="private")
    return {"status": "ok", "notebook": {"slug": slug, "name": name, "description": description}}
```

- [ ] **Step 5: Update listing endpoint**

Use database rows when available:

```python
@router.get("")
async def list_notebooks(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    query = db.query(Notebook).filter(Notebook.is_archived == False)  # noqa: E712
    if user.role != "admin":
        query = query.filter(Notebook.is_default == True)  # noqa: E712
    else:
        query = query.filter((Notebook.is_default == True) | (Notebook.owner_id == user.id))  # noqa: E712
    notebooks = query.order_by(Notebook.is_default.desc(), Notebook.created_at.asc()).all()
    return {
        "notebooks": [
            {
                "slug": n.slug,
                "name": n.name,
                "description": n.description,
                "visibility": n.visibility,
                "is_default": n.is_default,
            }
            for n in notebooks
        ]
    }
```

- [ ] **Step 6: Run permission tests**

Run:

```bash
pytest tests/test_notebook_permissions.py -q
```

Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add llmwiki/notebooks.py llmwiki/web/routes/notebooks.py tests/test_notebook_permissions.py
git commit -m "feat: enforce notebook permissions"
```

---

### Task 5: Notebook-Scoped Graph

**Files:**
- Modify: `llmwiki/graph.py`
- Modify: `llmwiki/web/routes/graph.py`
- Test: `tests/test_graph_viewer.py`

- [ ] **Step 1: Add a graph unit test for scoped roots**

Append to `tests/test_graph_viewer.py`:

```python
def test_graph_scan_pages_uses_supplied_wiki_dir(tmp_path):
    from llmwiki.graph import scan_pages

    wiki_a = tmp_path / "a" / "wiki"
    wiki_b = tmp_path / "b" / "wiki"
    wiki_a.mkdir(parents=True)
    wiki_b.mkdir(parents=True)
    (wiki_a / "Alpha.md").write_text('---\ntitle: "Alpha"\n---\n\n[[Shared]]', encoding="utf-8")
    (wiki_b / "Beta.md").write_text('---\ntitle: "Beta"\n---\n\n[[Shared]]', encoding="utf-8")

    pages = scan_pages(wiki_dir=wiki_a)

    assert "Alpha" in pages
    assert "Beta" not in pages
```

- [ ] **Step 2: Run failing graph test**

Run:

```bash
pytest tests/test_graph_viewer.py::test_graph_scan_pages_uses_supplied_wiki_dir -q
```

Expected: FAIL because `scan_pages` does not accept `wiki_dir`.

- [ ] **Step 3: Refactor graph functions**

In `llmwiki/graph.py`, change:

```python
def scan_pages(wiki_dir: Path = WIKI_DIR) -> dict[str, dict[str, Any]]:
    pages: dict[str, dict[str, Any]] = {}
    if not wiki_dir.exists():
        return pages
    for p in sorted(wiki_dir.rglob("*.md")):
        ...
        rel = p.relative_to(wiki_dir)
        ...
        pages[slug] = {
            "path": str(rel),
            "type": type_,
            "title": title,
            "out_links": out_links,
        }
```

Change:

```python
def build_graph(wiki_dir: Path = WIKI_DIR) -> dict[str, Any]:
    pages = scan_pages(wiki_dir=wiki_dir)
```

Change JSON writing functions and `build_and_report` to accept `graph_dir: Path = GRAPH_DIR`.

- [ ] **Step 4: Update Web graph route**

In `llmwiki/web/routes/graph.py`, add notebook query param and resolve:

```python
from fastapi import APIRouter, Query, HTTPException
from llmwiki.notebooks import current_notebook_slug, notebook_paths


def _paths(notebook: str | None):
    slug = current_notebook_slug(notebook)
    paths = notebook_paths(slug)
    if not paths.wiki_dir.is_dir():
        raise HTTPException(status_code=404, detail="notebook wiki not found")
    return paths
```

Use:

```python
pages = scan_pages(wiki_dir=paths.wiki_dir)
```

and:

```python
graph = build_graph(wiki_dir=paths.wiki_dir)
```

- [ ] **Step 5: Run graph tests**

Run:

```bash
pytest tests/test_graph_viewer.py -q
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add llmwiki/graph.py llmwiki/web/routes/graph.py tests/test_graph_viewer.py
git commit -m "feat: scope graph data by notebook"
```

---

### Task 6: Notebook-Scoped Upload and Ingester

**Files:**
- Modify: `llmwiki/web/services/ingester.py`
- Modify: `llmwiki/web/routes/upload.py`
- Test: `tests/test_webhook_handler.py` or create `tests/test_notebook_upload.py`

- [ ] **Step 1: Write upload path test**

Create `tests/test_notebook_upload.py`:

```python
from pathlib import Path

from llmwiki.web.services.ingester import save_raw_file


def test_save_raw_file_uses_notebook_uploads_dir(tmp_path):
    uploads = tmp_path / "notebooks" / "ai" / "raw" / "uploads"
    path = save_raw_file("AI Notes.md", b"# Notes", uploads_dir=uploads)

    assert path.parent == uploads
    assert path.name == "AI-Notes.md"
    assert path.read_bytes() == b"# Notes"
```

- [ ] **Step 2: Run failing upload test**

Run:

```bash
pytest tests/test_notebook_upload.py -q
```

Expected: FAIL because `save_raw_file` does not accept `uploads_dir`.

- [ ] **Step 3: Refactor ingester paths**

In `llmwiki/web/services/ingester.py`, change:

```python
def save_raw_file(filename: str, content: bytes, *, uploads_dir: Path | None = None) -> Path:
    target_dir = uploads_dir or (REPO_ROOT / "raw" / "uploads")
    target_dir.mkdir(parents=True, exist_ok=True)
    safe = filename.replace("\\", "-").replace("/", "-").replace(" ", "-")
    path = target_dir / safe
    path.write_bytes(content)
    return path
```

Change:

```python
def create_source_page(filename: str, md_content: str, knowledge: dict | None = None, *, wiki_dir: Path | None = None) -> str:
    target_wiki = wiki_dir or (REPO_ROOT / "wiki")
    sources_dir = target_wiki / "sources"
```

Change:

```python
def create_entity_concept_pages(knowledge: dict, source_slug: str, *, wiki_dir: Path | None = None) -> list[str]:
    target_wiki = wiki_dir or (REPO_ROOT / "wiki")
```

Change:

```python
def process_upload(filename: str, content: bytes, *, uploads_dir: Path | None = None, wiki_dir: Path | None = None) -> dict:
    filepath = save_raw_file(filename, content, uploads_dir=uploads_dir)
    ...
    wiki_path = create_source_page(filename, md_content, knowledge, wiki_dir=wiki_dir)
```

- [ ] **Step 4: Update upload route**

In `llmwiki/web/routes/upload.py`, add form field:

```python
notebook_slug: str = Form("enterprise-management")
```

Resolve:

```python
from llmwiki.notebooks import notebook_paths
paths = notebook_paths(notebook_slug)
result = process_upload(filename, content, uploads_dir=paths.uploads_dir, wiki_dir=paths.wiki_dir)
```

When recording `UploadedFile` and `KnowledgeLineage`, set `notebook_id` after resolving the database `Notebook` row.

- [ ] **Step 5: Run upload tests**

Run:

```bash
pytest tests/test_notebook_upload.py tests/test_web_clipper.py -q
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add llmwiki/web/services/ingester.py llmwiki/web/routes/upload.py tests/test_notebook_upload.py
git commit -m "feat: scope uploads by notebook"
```

---

### Task 7: Notebook-Scoped Q&A, Chat History, and Syntheses

**Files:**
- Modify: `llmwiki/web/services/glm_client.py`
- Modify: `llmwiki/web/routes/query.py`
- Test: `tests/test_notebook_query_scope.py`

- [ ] **Step 1: Write context scoping test**

Create `tests/test_notebook_query_scope.py`:

```python
from pathlib import Path

from llmwiki.web.services.glm_client import build_context


def _page(wiki: Path, name: str, body: str):
    p = wiki / "sources" / f"{name}.md"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(f'---\ntitle: "{name}"\n---\n\n{body}', encoding="utf-8")


def test_build_context_uses_selected_wiki_dir(tmp_path):
    wiki_a = tmp_path / "a" / "wiki"
    wiki_b = tmp_path / "b" / "wiki"
    _page(wiki_a, "ai", "transformer attention material")
    _page(wiki_b, "policy", "contract approval material")

    context = build_context("transformer", wiki_dir=wiki_a)

    assert "transformer attention material" in context
    assert "contract approval material" not in context
```

- [ ] **Step 2: Run failing query scope test**

Run:

```bash
pytest tests/test_notebook_query_scope.py -q
```

Expected: FAIL because `build_context` does not accept `wiki_dir`.

- [ ] **Step 3: Refactor GLM context builder**

In `llmwiki/web/services/glm_client.py`, update:

```python
def _build_context_from_wiki(
    question: str,
    *,
    wiki_dir: Path | None = None,
    search_limit: int = 8,
    ...
) -> str:
    from llmwiki.web.services.wiki_reader import search, read_page
    results = search(question, limit=search_limit, wiki_dir=wiki_dir)
    ...
    page = read_page(r["path"], wiki_dir=wiki_dir)
```

Update:

```python
def build_context(question: str, max_chars: int = 20000, *, wiki_dir: Path | None = None) -> str:
    return _build_context_from_wiki(question, total_max_chars=max_chars, wiki_dir=wiki_dir)
```

Update `ask`, `ask_stream`, and `ask_agent` to accept `wiki_dir: Path | None = None` and pass it through.

- [ ] **Step 4: Update query route body fields**

In `llmwiki/web/routes/query.py`, read:

```python
notebook_slug = body.get("notebook_slug") or "enterprise-management"
cross_notebook = bool(body.get("cross_notebook", False))
```

Resolve `paths = notebook_paths(notebook_slug)` and pass `wiki_dir=paths.wiki_dir` to GLM service calls.

For history functions, add `notebook_id` argument:

```python
def _save_chat_history(token: str, question: str, answer: str, model: str = "", thread_id: int | None = None, notebook_id: int | None = None) -> int | None:
```

When creating `Conversation` and `ChatHistory`, set `notebook_id=notebook_id`.

For `_write_synthesis`, change:

```python
def _write_synthesis(question: str, answer: str, *, wiki_dir: Path | None = None) -> str:
    target_wiki = wiki_dir or (REPO_ROOT / "wiki")
    out_dir = target_wiki / "syntheses"
```

- [ ] **Step 5: Add cross-notebook guard**

In `agent_stream` and `ask`, reject non-admin cross-notebook:

```python
if cross_notebook and (not user or user.role != "admin"):
    return {"answer": "跨知识库搜索仅管理员可用", "question": question}
```

For the streaming endpoint, emit an SSE error event with the same message.

- [ ] **Step 6: Run query tests**

Run:

```bash
pytest tests/test_notebook_query_scope.py tests/test_ollama_backend.py -q
```

Expected: PASS, with no regressions in backend context helpers.

- [ ] **Step 7: Commit**

```bash
git add llmwiki/web/services/glm_client.py llmwiki/web/routes/query.py tests/test_notebook_query_scope.py
git commit -m "feat: scope question answering by notebook"
```

---

### Task 8: Frontend Notebook Selector and Component Wiring

**Files:**
- Modify: `llmwiki/web/static/index.html`
- Modify: `llmwiki/web/static/api.js`
- Modify: `llmwiki/web/static/app.js`
- Create: `llmwiki/web/static/components/notebooks.js`
- Modify: `llmwiki/web/static/components/browser.js`
- Modify: `llmwiki/web/static/components/qa.js`
- Modify: `llmwiki/web/static/components/uploader.js`
- Modify: `llmwiki/web/static/components/graph-viewer.js`
- Modify: `llmwiki/web/static/components/manager.js`
- Modify: `llmwiki/web/static/components/threads.js`

- [ ] **Step 1: Add notebook component script to HTML**

In `llmwiki/web/static/index.html`, add a selector in `.nav-actions` before the theme toggle:

```html
<div class="notebook-selector" id="notebook-selector" style="display:none">
  <label for="notebook-select">知识库</label>
  <select id="notebook-select"></select>
</div>
```

Add script tag before component consumers initialize:

```html
<script src="/static/components/notebooks.js?v=1"></script>
```

- [ ] **Step 2: Add API helpers**

In `llmwiki/web/static/api.js`, add:

```javascript
  // Notebooks
  getNotebooks: () => API.get('/api/notebooks'),
  createNotebook: (body) => API.post('/api/notebooks', body),
```

Add helper:

```javascript
function notebookQuery() {
  const slug = window.Notebooks ? Notebooks.currentSlug() : 'enterprise-management';
  return 'notebook=' + encodeURIComponent(slug);
}
```

Update page and graph helpers:

```javascript
getTree: () => API.get('/api/pages/tree?' + notebookQuery()),
getPage: (path) => API.get(`/api/pages/rendered/${encodeURIComponent(path)}?` + notebookQuery()),
search: (q) => API.get(`/api/pages/search?q=${encodeURIComponent(q)}&` + notebookQuery()),
getGraph: () => API.get('/api/graph/data?' + notebookQuery()),
```

- [ ] **Step 3: Create notebook frontend state**

Create `llmwiki/web/static/components/notebooks.js`:

```javascript
const Notebooks = {
  notebooks: [],
  slug: localStorage.getItem('llmwiki-notebook') || 'enterprise-management',

  init() {
    this.selector = document.getElementById('notebook-selector');
    this.select = document.getElementById('notebook-select');
    if (!this.select) return Promise.resolve();
    this.select.addEventListener('change', () => {
      this.slug = this.select.value || 'enterprise-management';
      localStorage.setItem('llmwiki-notebook', this.slug);
      window.dispatchEvent(new CustomEvent('notebook:change', { detail: { slug: this.slug } }));
    });
    return this.load();
  },

  currentSlug() {
    return this.slug || 'enterprise-management';
  },

  async load() {
    try {
      const data = await API.getNotebooks();
      this.notebooks = data.notebooks || [];
      this.render();
    } catch (e) {
      this.notebooks = [{ slug: 'enterprise-management', name: '企业管理制度', is_default: true }];
      this.render();
    }
  },

  render() {
    if (!this.select) return;
    this.select.innerHTML = this.notebooks.map(n =>
      '<option value="' + this.escape(n.slug) + '">' + this.escape(n.name) + '</option>'
    ).join('');
    if (!this.notebooks.find(n => n.slug === this.slug)) {
      this.slug = 'enterprise-management';
      localStorage.setItem('llmwiki-notebook', this.slug);
    }
    this.select.value = this.slug;
    const showSelector = this.notebooks.length > 1 || (Auth.user && Auth.user.role === 'admin');
    if (this.selector) this.selector.style.display = showSelector ? 'flex' : 'none';
  },

  escape(s) {
    return String(s || '').replace(/[&<>"']/g, ch => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[ch]));
  }
};
```

- [ ] **Step 4: Initialize notebooks before scoped components**

In `llmwiki/web/static/app.js`, replace direct init sequence with:

```javascript
  Auth.init();
  Promise.resolve(Notebooks.init()).finally(() => {
    Browser.init();
    QA.init();
    Uploader.init();
    GraphViewer.init();
    Manager.init();
  });
```

- [ ] **Step 5: Reload components on notebook change**

In `browser.js`, add:

```javascript
window.addEventListener('notebook:change', () => {
  Browser.tree = null;
  Browser.currentPage = null;
  Browser.loadTree();
});
```

In `graph-viewer.js`, add:

```javascript
window.addEventListener('notebook:change', () => {
  GraphViewer.network = null;
  GraphViewer.loadGraph();
});
```

In `qa.js`, include notebook fields in agent request body:

```javascript
notebook_slug: Notebooks.currentSlug(),
cross_notebook: !!document.getElementById('cross-notebook-search')?.checked,
```

In `uploader.js`, append:

```javascript
fd.append('notebook_slug', Notebooks.currentSlug());
```

- [ ] **Step 6: Add admin cross-notebook checkbox**

In Q&A welcome markup, add:

```html
<label class="cross-notebook-row" id="cross-notebook-row" style="display:none">
  <input type="checkbox" id="cross-notebook-search">
  跨知识库搜索
</label>
```

In `qa.js`, after auth loads:

```javascript
const row = document.getElementById('cross-notebook-row');
if (row) row.style.display = (Auth.user && Auth.user.role === 'admin') ? 'flex' : 'none';
```

- [ ] **Step 7: Manual frontend smoke**

Run the Web UI:

```bash
python -m llmwiki web --port 8765
```

Expected:

- Normal user sees no selector when API returns one notebook.
- Admin sees selector when API returns multiple notebooks.
- Changing selector triggers wiki tree reload.

- [ ] **Step 8: Commit**

```bash
git add llmwiki/web/static/index.html llmwiki/web/static/api.js llmwiki/web/static/app.js llmwiki/web/static/components/notebooks.js llmwiki/web/static/components/browser.js llmwiki/web/static/components/qa.js llmwiki/web/static/components/uploader.js llmwiki/web/static/components/graph-viewer.js llmwiki/web/static/components/manager.js llmwiki/web/static/components/threads.js
git commit -m "feat: add notebook selector to web ui"
```

---

### Task 9: Admin Notebook Management UI

**Files:**
- Modify: `llmwiki/web/routes/notebooks.py`
- Modify: `llmwiki/web/static/index.html`
- Modify: `llmwiki/web/static/components/manager.js`
- Modify: `llmwiki/web/static/style.css`

- [ ] **Step 1: Add notebook management markup**

In the Manage tab section of `index.html`, add:

```html
<section class="manage-section" id="notebook-management-section" style="display:none">
  <h3>Notebook 管理</h3>
  <form id="notebook-create-form" class="notebook-form">
    <input id="notebook-name" placeholder="名称，例如：人工智能" required>
    <input id="notebook-slug" placeholder="slug，例如：ai" required>
    <input id="notebook-description" placeholder="描述，可选">
    <button class="btn btn-primary" type="submit">新建 Notebook</button>
  </form>
  <div id="notebook-admin-list" class="notebook-admin-list"></div>
</section>
```

- [ ] **Step 2: Add update/archive routes**

In `llmwiki/web/routes/notebooks.py`, add:

```python
@router.patch("/{slug}")
async def update_notebook(slug: str, body: dict, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if not user_is_admin(user):
        raise HTTPException(status_code=403, detail="admin only")
    notebook = db.query(Notebook).filter(Notebook.slug == slug, Notebook.owner_id == user.id).first()
    if not notebook or notebook.is_default:
        raise HTTPException(status_code=404, detail="notebook not found")
    notebook.name = (body.get("name") or notebook.name).strip()
    notebook.description = (body.get("description") or notebook.description).strip()
    db.commit()
    return {"status": "ok"}


@router.post("/{slug}/archive")
async def archive_notebook(slug: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if not user_is_admin(user):
        raise HTTPException(status_code=403, detail="admin only")
    notebook = db.query(Notebook).filter(Notebook.slug == slug, Notebook.owner_id == user.id).first()
    if not notebook or notebook.is_default:
        raise HTTPException(status_code=404, detail="notebook not found")
    notebook.is_archived = True
    db.commit()
    return {"status": "ok"}
```

- [ ] **Step 3: Wire manager component**

In `manager.js`, during `init()`:

```javascript
document.getElementById('notebook-create-form')?.addEventListener('submit', (e) => {
  e.preventDefault();
  this.createNotebook();
});
```

Add:

```javascript
async createNotebook() {
  if (!Auth.isAdmin()) return;
  const name = document.getElementById('notebook-name').value.trim();
  const slug = document.getElementById('notebook-slug').value.trim().toLowerCase();
  const description = document.getElementById('notebook-description').value.trim();
  const data = await API.createNotebook({ name, slug, description });
  if (data.status === 'ok') {
    document.getElementById('notebook-create-form').reset();
    await Notebooks.load();
    this.loadNotebookAdminList();
  }
},

async loadNotebookAdminList() {
  const section = document.getElementById('notebook-management-section');
  const list = document.getElementById('notebook-admin-list');
  if (!section || !list) return;
  if (!Auth.isAdmin()) {
    section.style.display = 'none';
    return;
  }
  section.style.display = 'block';
  await Notebooks.load();
  list.innerHTML = Notebooks.notebooks.map(n =>
    '<div class="notebook-admin-item">' +
    '<strong>' + this._esc(n.name) + '</strong>' +
    '<span class="muted">' + this._esc(n.slug) + '</span>' +
    '<p>' + this._esc(n.description || '') + '</p>' +
    '</div>'
  ).join('');
}
```

Call `this.loadNotebookAdminList()` when manage tab is shown.

- [ ] **Step 4: Add minimal styles**

In `style.css`, add:

```css
.notebook-selector { align-items: center; gap: 8px; color: var(--text-on-dark); font-size: 13px; }
.notebook-selector select { border: 1px solid rgba(255,255,255,0.18); background: rgba(255,255,255,0.08); color: #fff; border-radius: 6px; padding: 5px 8px; }
.notebook-form { display: grid; grid-template-columns: minmax(160px,1fr) minmax(120px,180px) minmax(220px,2fr) auto; gap: 10px; }
.notebook-admin-list { display: grid; gap: 10px; margin-top: 14px; }
.notebook-admin-item { border: 1px solid var(--border); background: var(--bg-card); border-radius: var(--radius-sm); padding: 12px; }
@media (max-width: 760px) { .notebook-form { grid-template-columns: 1fr; } }
```

- [ ] **Step 5: Manual smoke**

Run:

```bash
python -m llmwiki web --port 8765
```

Expected:

- Admin can create `ai`.
- Selector refreshes and includes `ai`.
- Manage page lists `ai`.
- Normal user does not see the management section.

- [ ] **Step 6: Commit**

```bash
git add llmwiki/web/routes/notebooks.py llmwiki/web/static/index.html llmwiki/web/static/components/manager.js llmwiki/web/static/style.css
git commit -m "feat: add admin notebook management"
```

---

### Task 10: Mojibake Cleanup and Runtime Ignores

**Files:**
- Modify: `llmwiki/web/routes/auth.py`
- Modify: `llmwiki/web/routes/upload.py`
- Modify: `llmwiki/web/routes/query.py`
- Modify: `llmwiki/web/routes/manage.py`
- Modify: `llmwiki/web/services/glm_client.py`
- Modify: `llmwiki/web/static/index.html`
- Modify: `llmwiki/web/static/components/*.js`
- Modify: `.gitignore`

- [ ] **Step 1: Add runtime ignores**

Append to `.gitignore`:

```gitignore
# llmwiki web runtime state
llmwiki.db
llmwiki.db-*
.jwt_secret
.env

# Notebook uploads can contain private source documents
notebooks/*/raw/uploads/
```

- [ ] **Step 2: Replace corrupted auth messages**

In `llmwiki/web/routes/auth.py`, replace mojibake detail strings with UTF-8 Chinese:

```python
HTTPException(status_code=401, detail="未登录或登录已过期")
HTTPException(status_code=403, detail="需要部门长或管理员权限")
HTTPException(status_code=400, detail="请输入用户名和密码")
HTTPException(status_code=401, detail="用户名或密码错误")
HTTPException(status_code=403, detail="账号已被禁用")
HTTPException(status_code=400, detail="用户名和密码不能为空")
HTTPException(status_code=400, detail="用户名至少2个字符")
HTTPException(status_code=400, detail="密码至少4个字符")
HTTPException(status_code=400, detail="用户名已存在")
```

- [ ] **Step 3: Replace corrupted upload/query UI strings**

In frontend files, replace visible mojibake labels with:

```text
问答
上传
图谱
管理
登录
退出
知识库问答
基于已入库的企业知识，为你提供精准答案
模型：
输入你的问题...
选择文件
拖拽文件到此处上传
支持 .doc .docx .pdf .md .txt 格式
当前对话中
新对话
删除
加载中...
暂无页面
```

Keep this as a targeted cleanup. Do not redesign the UI.

- [ ] **Step 4: Run mojibake grep**

Run:

```bash
rg -n "鐧|闂|涓|鍥|绠|鏌|瀹|浼|浜|鈥|鈫|锛|銆" llmwiki/web
```

Expected: no matches in user-visible Web route/static strings. If matches remain inside comments or legacy docs, either fix them or record the exact file and reason in the commit message.

- [ ] **Step 5: Run focused tests**

Run:

```bash
pytest tests/test_notebooks.py tests/test_notebook_permissions.py tests/test_notebook_wiki_reader.py tests/test_notebook_query_scope.py -q
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add .gitignore llmwiki/web/routes/auth.py llmwiki/web/routes/upload.py llmwiki/web/routes/query.py llmwiki/web/routes/manage.py llmwiki/web/services/glm_client.py llmwiki/web/static/index.html llmwiki/web/static/components llmwiki/web/static/style.css
git commit -m "fix: clean web ui text and runtime ignores"
```

---

### Task 11: Documentation and Final Verification

**Files:**
- Modify: `README.md`
- Modify: `USERGUIDE.md`
- Test: default test suite

- [ ] **Step 1: Update README scope note**

Add a section near Web UI documentation:

```markdown
## Web notebook mode

The Web UI can run llmwiki as a notebook-based knowledge platform. The default notebook is `enterprise-management`, shown to users as "企业管理制度". Admin users can create private notebooks, upload source documents, generate wiki pages and graphs, and ask questions scoped to the selected notebook.

The first notebook version scopes the Web UI. CLI static-site exports, MCP tools, and per-notebook publishing remain separate follow-up work.
```

- [ ] **Step 2: Update USERGUIDE**

Add:

```markdown
## Notebook 知识库

- 普通用户只能使用默认的“企业管理制度”知识库。
- 管理员可以新建私有 Notebook，例如“人工智能”。
- 上传文件、Wiki 浏览、图谱和问答默认只使用当前 Notebook 的内容。
- 管理员可手动开启“跨知识库搜索”，系统会标明答案来源于哪个 Notebook。
```

- [ ] **Step 3: Run the focused notebook suite**

Run:

```bash
pytest tests/test_notebooks.py tests/test_notebook_migration.py tests/test_notebook_wiki_reader.py tests/test_notebook_permissions.py tests/test_notebook_query_scope.py tests/test_notebook_upload.py -q
```

Expected: PASS.

- [ ] **Step 4: Run broader non-E2E suite**

Run:

```bash
pytest tests/ -q
```

Expected: PASS for non-E2E tests. If failures occur, fix notebook-related failures before proceeding. If unrelated pre-existing failures occur, record exact failing test names and error summaries.

- [ ] **Step 5: Manual Web acceptance**

Run:

```bash
python -m llmwiki web --port 8765
```

Verify:

- Normal user only sees default notebook.
- Admin creates `ai`.
- Admin uploads a Markdown file into `ai`.
- Wiki tree in `ai` shows only `ai` pages.
- Graph in `ai` shows only `ai` pages.
- Q&A in `ai` builds context only from `ai`.
- Switching back to default notebook hides `ai` content.
- Cross-notebook search is visible only to admin.
- UI text renders as normal Chinese.

- [ ] **Step 6: Commit docs**

```bash
git add README.md USERGUIDE.md
git commit -m "docs: document web notebook mode"
```

---

## Self-Review Checklist

- Spec coverage:
  - Independent notebook directory trees: Task 1, Task 2.
  - Default enterprise-management migration: Task 2.
  - Backend permission enforcement: Task 4.
  - Scoped wiki browsing/search: Task 3.
  - Scoped graph: Task 5.
  - Scoped upload: Task 6.
  - Scoped Q&A and history: Task 7.
  - Admin selector and management UI: Task 8, Task 9.
  - Mojibake cleanup and runtime ignores: Task 10.
  - Docs and verification: Task 11.
- Placeholder scan:
  - The plan intentionally avoids open implementation placeholders. Every task names exact files, commands, expected results, and concrete code shapes.
- Type consistency:
  - `notebook_slug` is the frontend/API request field.
  - `notebook` is the pages/graph query parameter.
  - `notebook_id` is the database foreign key on scoped records.
  - `wiki_dir`, `raw_dir`, `graph_dir`, and `uploads_dir` are filesystem parameters.
