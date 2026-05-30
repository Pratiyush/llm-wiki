"""Import public web pages into notebook wiki sources."""

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
    """User-facing web import failure."""

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
    """Validate that URL is public http(s) and not an internal network target."""
    parsed = urlparse((url or "").strip())
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise ValueError("unsupported or invalid URL")
    host = parsed.hostname
    try:
        addresses = socket.getaddrinfo(
            host,
            parsed.port or (443 if parsed.scheme == "https" else 80),
            type=socket.SOCK_STREAM,
        )
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
    """Fetch and extract a public web page."""
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
) -> tuple[str, list[str], int, int]:
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

    summary = (
        knowledge.get("summary", content[:200].replace("\n", " ").strip())
        if knowledge
        else content[:200].replace("\n", " ").strip()
    )
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
    new_pages: list[str] = []
    if knowledge:
        new_pages.extend(create_entity_concept_pages(knowledge, title, wiki_dir=wiki_dir))
    new_pages.extend(_ensure_wikilink_pages(page, title, wiki_dir=wiki_dir))
    return (
        rel_path,
        new_pages,
        len(knowledge.get("entities", [])) if knowledge else 0,
        len(knowledge.get("concepts", [])) if knowledge else 0,
    )


def process_web_import(
    url: str,
    *,
    title: str = "",
    content: str = "",
    mode: str = "auto",
    raw_dir: Path | None = None,
    wiki_dir: Path | None = None,
) -> dict:
    """Import a public web URL or manually pasted web content."""
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
    wiki_path, new_pages, entity_count, concept_count = _write_web_source_page(
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
        "entities_extracted": entity_count,
        "concepts_extracted": concept_count,
        "new_pages": new_pages,
    }
