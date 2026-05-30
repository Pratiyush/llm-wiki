# Web URL Import Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add public URL and URL + pasted body import to notebook knowledge bases, preserving web source URLs for later answer citations.

**Architecture:** Add a focused `web_ingester` service that validates URLs, fetches or accepts pasted content, writes web source pages, and reuses existing entity/concept extraction plus cache invalidation. Add an `/api/upload/url` route that mirrors file upload authorization and lineage. Update prompt context assembly and upload-tab UI so web source URLs become visible to both users and the model.

**Tech Stack:** FastAPI, SQLAlchemy, pytest, stdlib `urllib`, `html.parser`, `ipaddress`, existing llmwiki notebook/upload services, vanilla JS/CSS.

---

## File Map

- Create `llmwiki/web/services/web_ingester.py`: URL validation, safe fetch, HTML extraction, manual paste import, web source page creation.
- Modify `llmwiki/web/routes/upload.py`: add `/url` endpoint and shared lineage recording helper.
- Modify `llmwiki/web/services/glm_client.py`: include web source URLs in prompt context and answer instructions.
- Modify `llmwiki/web/static/index.html`: add web URL import controls to upload tab.
- Modify `llmwiki/web/static/components/uploader.js`: submit auto/manual URL imports and render results/fallback guidance.
- Modify `llmwiki/web/static/style.css`: style the URL import panel without disrupting the existing file dropzone.
- Create `tests/test_web_ingester.py`: unit tests for URL safety, auto/manual import, source page metadata, and fetch failures.
- Modify `tests/test_notebook_upload.py`: route-level test for URL import notebook scope and lineage.
- Create or modify `tests/test_web_source_context.py`: prompt context test proving `source_url` reaches model context.

---

### Task 1: Web Ingestion Service

**Files:**
- Create: `llmwiki/web/services/web_ingester.py`
- Test: `tests/test_web_ingester.py`

- [ ] **Step 1: Write failing tests for URL validation and manual import**

Create `tests/test_web_ingester.py`:

```python
from __future__ import annotations

import pytest


def test_validate_public_url_blocks_unsafe_targets():
    from llmwiki.web.services.web_ingester import validate_public_url

    for url in [
        "file:///etc/passwd",
        "ftp://example.com/a",
        "http://localhost/a",
        "http://127.0.0.1/a",
        "http://10.0.0.1/a",
        "http://172.16.0.1/a",
        "http://192.168.1.1/a",
        "http://169.254.169.254/latest/meta-data",
    ]:
        with pytest.raises(ValueError):
            validate_public_url(url)


def test_process_manual_web_import_preserves_url_metadata(tmp_path):
    from llmwiki.web.services.web_ingester import process_web_import

    wiki_dir = tmp_path / "notebooks" / "ai" / "wiki"
    raw_dir = tmp_path / "notebooks" / "ai" / "raw" / "web"
    body = "Article paragraph one.\n\nArticle paragraph two with enough content for import."

    result = process_web_import(
        "https://example.gov.cn/rule.html",
        title="Public Rule",
        content=body,
        mode="manual",
        raw_dir=raw_dir,
        wiki_dir=wiki_dir,
    )

    assert result["status"] == "ok"
    assert result["source_type"] == "web"
    assert result["url"] == "https://example.gov.cn/rule.html"
    assert result["capture_method"] == "manual"
    source_path = wiki_dir / result["wiki_path"]
    text = source_path.read_text(encoding="utf-8")
    assert "source_type: web" in text
    assert 'source_url: "https://example.gov.cn/rule.html"' in text
    assert "capture_method: manual" in text
    assert "- URL: https://example.gov.cn/rule.html" in text
    assert body in text
```

- [ ] **Step 2: Run tests to verify failure**

Run:

```bash
pytest tests/test_web_ingester.py -q
```

Expected: FAIL because `llmwiki.web.services.web_ingester` does not exist.

- [ ] **Step 3: Implement minimal web ingestion service**

Create `llmwiki/web/services/web_ingester.py` with these public functions and exceptions:

```python
from __future__ import annotations

import html
import ipaddress
import re
import socket
from dataclasses import dataclass
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urljoin, urlparse
from urllib.request import Request, urlopen

from llmwiki import REPO_ROOT
from llmwiki.web.services.ingester import (
    _ensure_wikilink_pages,
    _safe_upload_filename,
    _slugify,
    create_entity_concept_pages,
)


MAX_DOWNLOAD_BYTES = 5 * 1024 * 1024
MIN_CONTENT_CHARS = 40
USER_AGENT = "llmwiki-web-import/1.0 (+public knowledge import)"


class WebImportError(ValueError):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code
        self.message = message


@dataclass
class FetchedPage:
    requested_url: str
    final_url: str
    canonical_url: str
    title: str
    content: str


class _ReadableHTMLParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.title_parts: list[str] = []
        self.h1_parts: list[str] = []
        self.body_parts: list[str] = []
        self.canonical_url = ""
        self._skip_depth = 0
        self._capture_title = False
        self._capture_h1 = False

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attrs_dict = {k.lower(): (v or "") for k, v in attrs}
        tag = tag.lower()
        if tag in {"script", "style", "noscript", "svg"}:
            self._skip_depth += 1
        if tag == "title":
            self._capture_title = True
        if tag == "h1":
            self._capture_h1 = True
        if tag == "link" and attrs_dict.get("rel", "").lower() == "canonical":
            self.canonical_url = attrs_dict.get("href", "")
        if tag in {"p", "div", "section", "article", "main", "br", "li", "h1", "h2", "h3"}:
            self.body_parts.append("\n")

    def handle_endtag(self, tag: str) -> None:
        tag = tag.lower()
        if tag in {"script", "style", "noscript", "svg"} and self._skip_depth:
            self._skip_depth -= 1
        if tag == "title":
            self._capture_title = False
        if tag == "h1":
            self._capture_h1 = False
        if tag in {"p", "div", "section", "article", "main", "li", "h1", "h2", "h3"}:
            self.body_parts.append("\n")

    def handle_data(self, data: str) -> None:
        if self._skip_depth:
            return
        text = data.strip()
        if not text:
            return
        if self._capture_title:
            self.title_parts.append(text)
        if self._capture_h1:
            self.h1_parts.append(text)
        self.body_parts.append(text)

    def title(self) -> str:
        return _normalize_text(" ".join(self.title_parts) or " ".join(self.h1_parts))

    def body(self) -> str:
        return _normalize_text(" ".join(self.body_parts))


def _normalize_text(text: str) -> str:
    text = html.unescape(text or "")
    text = re.sub(r"[ \t\r\f\v]+", " ", text)
    text = re.sub(r"\n\s*\n\s*", "\n\n", text)
    text = re.sub(r" *\n *", "\n", text)
    return text.strip()


def _is_private_ip(ip: str) -> bool:
    parsed = ipaddress.ip_address(ip)
    return (
        parsed.is_private
        or parsed.is_loopback
        or parsed.is_link_local
        or parsed.is_multicast
        or parsed.is_reserved
        or parsed.is_unspecified
    )


def validate_public_url(url: str) -> str:
    parsed = urlparse((url or "").strip())
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise ValueError("unsupported or invalid URL")
    host = parsed.hostname
    try:
        addresses = socket.getaddrinfo(host, parsed.port or (443 if parsed.scheme == "https" else 80), type=socket.SOCK_STREAM)
    except socket.gaierror as exc:
        raise ValueError("URL hostname cannot be resolved") from exc
    for item in addresses:
        ip = item[4][0]
        if _is_private_ip(ip):
            raise ValueError("URL resolves to an unsafe private address")
    return parsed.geturl()


def _extract_html(raw: bytes, final_url: str, requested_url: str) -> FetchedPage:
    text = raw.decode("utf-8", errors="replace")
    parser = _ReadableHTMLParser()
    parser.feed(text)
    title = parser.title() or urlparse(final_url).netloc
    body = parser.body()
    if len(body) < MIN_CONTENT_CHARS:
        raise WebImportError("empty_content", "No readable page body was extracted from this URL.")
    canonical_url = urljoin(final_url, parser.canonical_url) if parser.canonical_url else final_url
    try:
        canonical_url = validate_public_url(canonical_url)
    except ValueError:
        canonical_url = final_url
    return FetchedPage(requested_url, final_url, canonical_url, title, body)


def fetch_public_page(url: str) -> FetchedPage:
    safe_url = validate_public_url(url)
    request = Request(safe_url, headers={"User-Agent": USER_AGENT})
    try:
        with urlopen(request, timeout=15) as response:
            final_url = validate_public_url(response.geturl())
            raw = response.read(MAX_DOWNLOAD_BYTES + 1)
    except HTTPError as exc:
        code = "fetch_forbidden" if exc.code in {401, 403, 429} else "fetch_http_error"
        raise WebImportError(code, f"Target site rejected the fetch (HTTP {exc.code}).") from exc
    except (TimeoutError, URLError) as exc:
        raise WebImportError("fetch_failed", f"Unable to fetch URL: {exc}") from exc
    if len(raw) > MAX_DOWNLOAD_BYTES:
        raise WebImportError("content_too_large", "Downloaded page is too large.")
    return _extract_html(raw, final_url, safe_url)


def _quote_yaml(value: str) -> str:
    return '"' + value.replace("\\", "\\\\").replace('"', '\\"') + '"'


def _write_web_source_page(
    *,
    title: str,
    source_url: str,
    canonical_url: str,
    content: str,
    capture_method: str,
    wiki_dir: Path,
) -> str:
    today = datetime.now(timezone.utc).date().isoformat()
    fetched_at = datetime.now(timezone.utc).isoformat()
    wiki_sources = wiki_dir / "sources" / "web"
    wiki_sources.mkdir(parents=True, exist_ok=True)
    slug = _slugify(title) or _slugify(urlparse(source_url).netloc) or "web-source"
    page_path = wiki_sources / f"{slug}.md"

    try:
        from llmwiki.web.services.glm_client import extract_knowledge
        knowledge = extract_knowledge(content)
    except Exception:
        knowledge = None

    summary = knowledge.get("summary", content[:200].replace("\n", " ").strip()) if knowledge else content[:200].replace("\n", " ").strip()
    claims = knowledge.get("key_claims", []) if knowledge else []
    claims_text = "\n".join(f"- {claim}" for claim in claims) if claims else "- Pending AI extraction"
    connections = []
    if knowledge:
        for entity in knowledge.get("entities", []):
            connections.append(f"- [[{entity['name']}]] - {entity.get('description', '')}")
        for concept in knowledge.get("concepts", []):
            connections.append(f"- [[{concept['name']}]] - {concept.get('description', '')}")
    connections_text = "\n".join(connections) if connections else "- [[web source]]"

    page = f"""---
title: {_quote_yaml(title)}
type: source
tags: [web-source]
date: {today}
source_type: web
source_url: {_quote_yaml(source_url)}
canonical_url: {_quote_yaml(canonical_url)}
fetched_at: {_quote_yaml(fetched_at)}
capture_method: {capture_method}
project: web
---

## Source

- URL: {source_url}
- Canonical URL: {canonical_url}
- Captured at: {fetched_at}
- Capture method: {capture_method}

## Summary

{summary}

## Key Claims

{claims_text}

## Connections

{connections_text}

{content}
"""
    page_path.write_text(page, encoding="utf-8")
    rel_path = f"sources/web/{page_path.name}"
    if knowledge:
        create_entity_concept_pages(knowledge, title, wiki_dir=wiki_dir)
    _ensure_wikilink_pages(page, title, wiki_dir=wiki_dir)
    return rel_path


def process_web_import(
    url: str,
    *,
    title: str = "",
    content: str = "",
    mode: str = "auto",
    raw_dir: Path | None = None,
    wiki_dir: Path | None = None,
) -> dict:
    target_wiki_dir = wiki_dir or (REPO_ROOT / "wiki")
    target_raw_dir = raw_dir or (REPO_ROOT / "raw" / "web")
    target_raw_dir.mkdir(parents=True, exist_ok=True)
    if mode == "manual":
        source_url = validate_public_url(url)
        body = _normalize_text(content)
        if len(body) < MIN_CONTENT_CHARS:
            raise WebImportError("manual_content_too_short", "Pasted body is too short to import.")
        page_title = _normalize_text(title) or urlparse(source_url).netloc
        canonical_url = source_url
        capture_method = "manual"
    else:
        fetched = fetch_public_page(url)
        source_url = fetched.requested_url
        canonical_url = fetched.canonical_url
        page_title = fetched.title
        body = fetched.content
        capture_method = "auto"

    raw_name = _safe_upload_filename(f"{page_title}.md")
    (target_raw_dir / raw_name).write_text(body, encoding="utf-8")
    wiki_path = _write_web_source_page(
        title=page_title,
        source_url=source_url,
        canonical_url=canonical_url,
        content=body,
        capture_method=capture_method,
        wiki_dir=target_wiki_dir,
    )
    from llmwiki.web.services.wiki_reader import invalidate_cache
    invalidate_cache()
    return {
        "status": "ok",
        "source_type": "web",
        "url": source_url,
        "canonical_url": canonical_url,
        "title": page_title,
        "capture_method": capture_method,
        "wiki_path": wiki_path,
        "content_length": len(body),
        "entities_extracted": 0,
        "concepts_extracted": 0,
        "new_pages": [],
    }
```

- [ ] **Step 4: Run service tests**

Run:

```bash
pytest tests/test_web_ingester.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add llmwiki/web/services/web_ingester.py tests/test_web_ingester.py
git commit -m "feat: add web import service"
```

---

### Task 2: URL Upload Route And Lineage

**Files:**
- Modify: `llmwiki/web/routes/upload.py`
- Modify: `tests/test_notebook_upload.py`

- [ ] **Step 1: Write failing route test**

Append this test to `tests/test_notebook_upload.py`:

```python
def test_upload_url_route_records_notebook_id_and_lineage(monkeypatch, tmp_path):
    monkeypatch.setenv("JWT_SECRET_KEY", "test-secret")

    from llmwiki.web import database
    from llmwiki.web.database import Base
    from llmwiki.web.models import KnowledgeLineage, Notebook, UploadedFile, User
    from llmwiki.web.routes.auth import _create_token
    from llmwiki.web.routes.upload import upload_url
    from llmwiki.web.services import notebooks

    monkeypatch.setattr(notebooks, "REPO_ROOT", tmp_path)
    engine = create_engine(f"sqlite:///{tmp_path / 'app.db'}")
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    monkeypatch.setattr(database, "SessionLocal", Session)

    db = Session()
    try:
        admin = User(username="admin", hashed_password="x", role="admin")
        selected = Notebook(slug="ai", title="AI", is_default=False)
        db.add_all([admin, selected])
        db.commit()
        db.refresh(admin)
        db.refresh(selected)
        token = _create_token(admin)
        notebook_id = selected.id
    finally:
        db.close()

    notebooks.ensure_notebook_dirs("ai")
    body = {
        "url": "https://example.gov.cn/rule.html",
        "title": "Public Rule",
        "content": "Manual web body with enough content to be imported into the notebook.",
        "mode": "manual",
        "version_note": "manual capture",
        "notebook": "ai",
        "token": token,
    }

    result = asyncio.run(upload_url(body=body))

    assert result["status"] == "ok"
    assert result["notebook"] == "ai"
    db = Session()
    try:
        uploaded = db.query(UploadedFile).one()
        assert uploaded.notebook_id == notebook_id
        assert uploaded.version_note == "manual capture"
        assert uploaded.wiki_path.startswith("sources/web/")
        lineages = db.query(KnowledgeLineage).all()
        assert lineages
        assert {lineage.notebook_id for lineage in lineages} == {notebook_id}
    finally:
        db.close()
```

- [ ] **Step 2: Run test to verify failure**

Run:

```bash
pytest tests/test_notebook_upload.py::test_upload_url_route_records_notebook_id_and_lineage -q
```

Expected: FAIL because `upload_url` does not exist.

- [ ] **Step 3: Add route and shared lineage helper**

In `llmwiki/web/routes/upload.py`, add a helper near `_bearer_token`:

```python
def _record_lineage(db, *, notebook_id: int | None, source_file_id: int, source_path: str, new_pages: list[str]) -> None:
    from llmwiki.web.models import KnowledgeLineage

    if source_path:
        db.add(KnowledgeLineage(notebook_id=notebook_id, source_file_id=source_file_id, wiki_path=source_path, wiki_type="source"))
    for page in new_pages:
        if page == source_path:
            continue
        page_type = "concept" if page.startswith("concepts/") else "entity"
        db.add(KnowledgeLineage(notebook_id=notebook_id, source_file_id=source_file_id, wiki_path=page, wiki_type=page_type))
```

Replace the duplicated lineage block in `upload_file()` with:

```python
_record_lineage(
    db,
    notebook_id=notebook_row.id,
    source_file_id=uf.id,
    source_path=source_path,
    new_pages=result.get("new_pages", []),
)
```

Add this endpoint below `upload_file()`:

```python
@router.post("/url")
async def upload_url(body: dict, authorization: str | None = Header(None)):
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
            from llmwiki.web.routes.auth import get_current_user
            user = get_current_user(token=token, db=db)
            uploader_id = user.id

        if not can_access_notebook(user, notebook_row):
            raise HTTPException(status_code=403, detail="notebook access denied")

        raw_dir = notebook_raw_dir(slug) / "web"
        wiki_dir = notebook_wiki_dir(slug)
        ensure_notebook_dirs(slug)
        result = process_web_import(url, title=title, content=content, mode=mode, raw_dir=raw_dir, wiki_dir=wiki_dir)

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
```

- [ ] **Step 4: Run route tests**

Run:

```bash
pytest tests/test_notebook_upload.py::test_upload_url_route_records_notebook_id_and_lineage tests/test_notebook_upload.py::test_upload_route_records_notebook_id_and_uses_selected_notebook -q
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add llmwiki/web/routes/upload.py tests/test_notebook_upload.py
git commit -m "feat: add url upload route"
```

---

### Task 3: Web Source URLs In Q&A Context

**Files:**
- Modify: `llmwiki/web/services/glm_client.py`
- Test: `tests/test_web_source_context.py`

- [ ] **Step 1: Write failing context test**

Create `tests/test_web_source_context.py`:

```python
from __future__ import annotations


def test_build_context_includes_web_source_url(tmp_path):
    from llmwiki.web.services.glm_client import build_context

    wiki_dir = tmp_path / "wiki"
    source_dir = wiki_dir / "sources" / "web"
    source_dir.mkdir(parents=True)
    (source_dir / "rule.md").write_text(
        """---
title: "Public Rule"
type: source
source_type: web
source_url: "https://example.gov.cn/rule.html"
canonical_url: "https://example.gov.cn/rule.html"
---

## Source

Government rule about procurement approval thresholds.
""",
        encoding="utf-8",
    )

    context = build_context("procurement approval thresholds", wiki_dir=wiki_dir)

    assert "Public Rule" in context
    assert "Web source URL: https://example.gov.cn/rule.html" in context
```

- [ ] **Step 2: Run test to verify failure**

Run:

```bash
pytest tests/test_web_source_context.py -q
```

Expected: FAIL because context headers do not include `source_url`.

- [ ] **Step 3: Add URL-aware context headers and prompt rule**

In `llmwiki/web/services/glm_client.py`, add helper near `_build_context_from_wiki`:

```python
def _source_metadata_lines(page: dict) -> str:
    meta = page.get("meta") or {}
    if meta.get("source_type") == "web" and meta.get("source_url"):
        lines = [f"Web source URL: {meta['source_url']}"]
        if meta.get("canonical_url") and meta.get("canonical_url") != meta.get("source_url"):
            lines.append(f"Canonical URL: {meta['canonical_url']}")
        return "\n".join(lines) + "\n"
    return ""
```

Change context chunk assembly:

```python
metadata = _source_metadata_lines(page)
chunk = header + metadata + page["content"][:per_page_chars] + "\n\n"
```

Append this ASCII sentence to both `SYSTEM_PROMPT` and `AGENT_SYSTEM_PROMPT` strings:

```text

Citation rule for web sources: when context contains "Web source URL:", cite both the wiki page link and the exact URL.
```

- [ ] **Step 4: Run context tests**

Run:

```bash
pytest tests/test_web_source_context.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add llmwiki/web/services/glm_client.py tests/test_web_source_context.py
git commit -m "feat: cite web source urls in context"
```

---

### Task 4: Upload Tab URL Import UI

**Files:**
- Modify: `llmwiki/web/static/index.html`
- Modify: `llmwiki/web/static/components/uploader.js`
- Modify: `llmwiki/web/static/style.css`

- [ ] **Step 1: Add static DOM controls**

In `llmwiki/web/static/index.html`, inside `<div class="upload-layout">` after the existing dropzone, add:

```html
<div class="web-import-panel" id="web-import-panel">
  <div class="web-import-header">
    <h3>Web URL Import</h3>
    <div class="web-import-mode" role="group" aria-label="Web import mode">
      <button class="web-mode-btn active" id="web-mode-auto" type="button">Auto fetch</button>
      <button class="web-mode-btn" id="web-mode-manual" type="button">Paste body</button>
    </div>
  </div>
  <div class="form-group">
    <label for="web-import-url">URL</label>
    <input type="url" id="web-import-url" placeholder="https://example.gov.cn/rule.html">
  </div>
  <div class="form-group web-manual-only" style="display:none">
    <label for="web-import-title">Title</label>
    <input type="text" id="web-import-title" placeholder="Page title">
  </div>
  <div class="form-group web-manual-only" style="display:none">
    <label for="web-import-content">Page body</label>
    <textarea id="web-import-content" rows="8" placeholder="Paste page text here"></textarea>
  </div>
  <div class="form-group">
    <label for="web-import-note">Source note</label>
    <input type="text" id="web-import-note" placeholder="Source date, version, or capture note">
  </div>
  <button class="btn btn-primary" id="web-import-btn" type="button">Import URL</button>
</div>
```

- [ ] **Step 2: Wire uploader JS**

In `llmwiki/web/static/components/uploader.js`:

Add state in the object:

```javascript
  webMode: 'auto',
```

In `init()`, after upload confirm listeners:

```javascript
    this.webUrl = document.getElementById('web-import-url');
    this.webTitle = document.getElementById('web-import-title');
    this.webContent = document.getElementById('web-import-content');
    this.webNote = document.getElementById('web-import-note');
    this.webImportBtn = document.getElementById('web-import-btn');
    this.webModeAuto = document.getElementById('web-mode-auto');
    this.webModeManual = document.getElementById('web-mode-manual');
    if (this.webImportBtn) {
      this.webModeAuto.addEventListener('click', () => this._setWebMode('auto'));
      this.webModeManual.addEventListener('click', () => this._setWebMode('manual'));
      this.webImportBtn.addEventListener('click', () => this.importUrl());
    }
```

Add methods:

```javascript
  _setWebMode(mode) {
    this.webMode = mode;
    this.webModeAuto.classList.toggle('active', mode === 'auto');
    this.webModeManual.classList.toggle('active', mode === 'manual');
    document.querySelectorAll('.web-manual-only').forEach((el) => {
      el.style.display = mode === 'manual' ? '' : 'none';
    });
  },

  async importUrl() {
    const url = (this.webUrl.value || '').trim();
    const item = document.createElement('div');
    item.className = 'upload-item';
    item.innerHTML = '<div class="status pending"></div><div><strong>' + this._escapeHtml(url || 'URL') + '</strong><br><span class="upload-status">Importing web source...</span></div>';
    this.results.appendChild(item);
    if (!url) {
      item.querySelector('.status').className = 'status error';
      item.querySelector('.upload-status').textContent = 'URL is required';
      return;
    }
    const headers = { 'Content-Type': 'application/json' };
    const body = {
      url: url,
      mode: this.webMode,
      title: this.webTitle ? this.webTitle.value.trim() : '',
      content: this.webContent ? this.webContent.value : '',
      version_note: this.webNote ? this.webNote.value.trim() : '',
      notebook: this.notebookSlug()
    };
    if (typeof Auth !== 'undefined' && Auth.isLoggedIn()) {
      const token = Auth.getToken();
      body.token = token;
      headers.Authorization = 'Bearer ' + token;
    }
    try {
      const resp = await fetch('/api/upload/url', { method: 'POST', headers: headers, body: JSON.stringify(body) });
      const data = await resp.json().catch(() => ({}));
      const statusDot = item.querySelector('.status');
      const statusText = item.querySelector('.upload-status');
      if (!resp.ok) {
        statusDot.className = 'status error';
        statusText.textContent = data.detail || 'Import failed: HTTP ' + resp.status;
      } else if (data.status === 'ok') {
        statusDot.className = 'status success';
        statusText.innerHTML = 'Imported ' + data.content_length + ' characters<br>URL: ' + this._escapeHtml(data.canonical_url || data.url) + '<br>Page: <a href="#wiki" onclick="Uploader.openPage(\\'' + data.wiki_path + '\\')">' + data.wiki_path + '</a>';
      } else {
        statusDot.className = 'status error';
        statusText.textContent = data.message || 'Import failed';
        if (data.code && data.code.indexOf('fetch') === 0) this._setWebMode('manual');
      }
    } catch (e) {
      item.querySelector('.status').className = 'status error';
      item.querySelector('.upload-status').textContent = 'Request failed: ' + e.message;
    }
  },

  _escapeHtml(value) {
    return String(value || '').replace(/[&<>"']/g, (ch) => ({
      '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'
    }[ch]));
  },
```

- [ ] **Step 3: Add CSS**

In `llmwiki/web/static/style.css`, near upload styles:

```css
.web-import-panel {
  width: 100%;
  max-width: 760px;
  margin-top: 24px;
  padding: 18px;
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  background: var(--surface);
}
.web-import-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 14px;
}
.web-import-header h3 {
  margin: 0;
  font-size: 16px;
}
.web-import-mode {
  display: inline-flex;
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  overflow: hidden;
}
.web-mode-btn {
  border: 0;
  background: transparent;
  padding: 7px 10px;
  cursor: pointer;
  color: var(--text-secondary);
}
.web-mode-btn.active {
  background: var(--accent);
  color: white;
}
#web-import-content {
  width: 100%;
  resize: vertical;
}
@media (max-width: 700px) {
  .web-import-header {
    align-items: stretch;
    flex-direction: column;
  }
}
```

- [ ] **Step 4: Run a smoke syntax check**

Run:

```bash
python -m compileall llmwiki/web/routes/upload.py llmwiki/web/services/web_ingester.py
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add llmwiki/web/static/index.html llmwiki/web/static/components/uploader.js llmwiki/web/static/style.css
git commit -m "feat: add web import ui"
```

---

### Task 5: Integration Verification

**Files:**
- No new files unless fixes are required.

- [ ] **Step 1: Run focused tests**

Run:

```bash
pytest tests/test_web_ingester.py tests/test_web_source_context.py tests/test_notebook_upload.py -q
```

Expected: PASS.

- [ ] **Step 2: Run full test suite**

Run:

```bash
pytest -q
```

Expected: PASS or only pre-existing skips.

- [ ] **Step 3: Manual server check**

Start the FastAPI app with:

```bash
uvicorn llmwiki.web.app:create_app --factory --host 127.0.0.1 --port 8765
```

Open the upload tab and verify:

- File upload UI still renders.
- Web URL panel renders below the dropzone.
- Auto mode hides pasted title/body.
- Manual mode shows title/body.
- Manual import of `https://example.com/rule` plus pasted text returns success and opens the generated source page.

- [ ] **Step 4: Final commit for fixes only**

If verification required fixes:

```bash
git status -sb
git add llmwiki/web/services/web_ingester.py llmwiki/web/routes/upload.py llmwiki/web/services/glm_client.py llmwiki/web/static/index.html llmwiki/web/static/components/uploader.js llmwiki/web/static/style.css tests/test_web_ingester.py tests/test_web_source_context.py tests/test_notebook_upload.py
git commit -m "fix: stabilize web url import"
```

If no fixes were required, do not create an empty commit.

---

## Self-Review

- Spec coverage: The plan covers public URL import, manual paste fallback, URL metadata, notebook permissions, lineage, Q&A URL context, UI controls, anti-bot failure behavior, and SSRF protections.
- Red-flag scan: The plan uses concrete file paths, commands, snippets, and expected outcomes.
- Type consistency: The route calls `process_web_import()`, handles `WebImportError`, and records existing `UploadedFile` plus `KnowledgeLineage`. The context test expects `Web source URL:` which matches the planned helper output.
