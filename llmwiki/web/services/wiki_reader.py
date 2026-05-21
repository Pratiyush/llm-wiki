"""Read wiki/*.md files, search, and render."""

from __future__ import annotations

import re
import time
from pathlib import Path

import markdown as md_lib

from llmwiki import REPO_ROOT
from llmwiki.text_utils import strip_bom

WIKI_DIR = REPO_ROOT / "wiki"

# ── TTL cache ────────────────────────────────────────────────────────────────

_CACHE_TTL_SEARCH = 60          # seconds — search results
_CACHE_TTL_PAGE = 30            # seconds — page reads
_cache: dict[str, tuple[float, object]] = {}


def _cache_get(key: str) -> object | None:
    entry = _cache.get(key)
    if entry is None:
        return None
    ts, val = entry
    if time.time() - ts > _CACHE_TTL_SEARCH if ":search:" in key else _CACHE_TTL_PAGE:
        del _cache[key]
        return None
    return val


def _cache_set(key: str, value: object) -> None:
    _cache[key] = (time.time(), value)


def invalidate_cache() -> None:
    """Clear the in-memory cache (call after wiki writes)."""
    _cache.clear()


def _parse_frontmatter(text: str) -> tuple[dict, str]:
    """Parse YAML frontmatter from markdown text."""
    text = strip_bom(text)
    if not text.startswith("---"):
        return {}, text
    end = text.find("---", 3)
    if end == -1:
        return {}, text
    fm_text = text[3:end].strip()
    body = text[end + 3:].strip()
    meta: dict = {}
    for line in fm_text.splitlines():
        if ":" in line:
            k, v = line.split(":", 1)
            meta[k.strip()] = v.strip().strip('"').strip("'")
    return meta, body


def get_tree() -> dict:
    """Return wiki directory tree as nested dict."""
    tree: dict = {}
    if not WIKI_DIR.is_dir():
        return tree

    for path in sorted(WIKI_DIR.rglob("*.md")):
        if path.name.startswith("_") or path.name == "log.md":
            continue
        rel = path.relative_to(WIKI_DIR)
        parts = list(rel.parent.parts)
        if parts:
            category = parts[0]
        else:
            category = "root"
        name = path.stem
        if category not in tree:
            tree[category] = []
        meta, _ = _parse_frontmatter(path.read_text(encoding="utf-8"))
        title = meta.get("title", name)
        tree[category].append({
            "name": name,
            "path": str(rel),
            "title": title,
            "type": meta.get("type", ""),
        })
    return tree


def list_pages(category: str | None = None) -> list[dict]:
    """List wiki pages with metadata."""
    pages: list[dict] = []
    if not WIKI_DIR.is_dir():
        return pages

    for path in sorted(WIKI_DIR.rglob("*.md")):
        if path.name.startswith("_") or path.name == "log.md":
            continue
        rel = path.relative_to(WIKI_DIR)
        parts = list(rel.parent.parts)
        cat = parts[0] if parts else "root"

        if category and cat != category:
            continue

        meta, body = _parse_frontmatter(path.read_text(encoding="utf-8"))
        pages.append({
            "name": path.stem,
            "path": str(rel),
            "title": meta.get("title", path.stem),
            "type": meta.get("type", ""),
            "category": cat,
            "lines": len(body.splitlines()),
        })
    return pages


def read_page(path: str) -> dict:
    """Read a wiki page, return raw content + frontmatter (cached)."""
    cache_key = f"page:{path}"
    cached = _cache_get(cache_key)
    if cached is not None:
        return cached  # type: ignore[return-value]

    full = WIKI_DIR / path
    if not full.is_file():
        return {"error": "not found", "path": path}
    text = full.read_text(encoding="utf-8")
    meta, body = _parse_frontmatter(text)
    result = {"meta": meta, "content": body, "path": path}
    _cache_set(cache_key, result)
    return result


def render_page(path: str) -> dict:
    """Read and render a wiki page as HTML."""
    data = read_page(path)
    if "error" in data:
        return data

    body = data["content"]
    # Convert wikilinks [[Name]] to clickable spans
    body = re.sub(
        r'\[\[([^\]]+)\]\]',
        r'<a class="wikilink" href="#wiki/\1">\1</a>',
        body,
    )
    html = md_lib.markdown(
        body,
        extensions=["tables", "fenced_code", "toc"],
    )
    return {"html": html, "meta": data["meta"], "path": path}


def search(query: str, limit: int = 20) -> list[dict]:
    """Search wiki pages by keyword (Chinese-aware n-gram tokenization, cached)."""
    if not query:
        return []

    cache_key = f":search:{query}:{limit}"
    cached = _cache_get(cache_key)
    if cached is not None:
        return cached  # type: ignore[return-value]

    # Build tokens: split by spaces, punctuation, then n-gram Chinese segments
    tokens: list[str] = []

    # 1. Split by common Chinese/English punctuation and spaces
    import re as _re
    parts = _re.split(r'[，。？、！；：\u201c\u201d\u2018\u2019（）《》\s,.\?!;:()]+', query)

    for part in parts:
        part = part.strip()
        if not part:
            continue
        part_lower = part.lower()
        if len(part_lower) >= 2:
            tokens.append(part_lower)
        # For Chinese segments, also extract 2-char and 3-char n-grams
        cn_chars = _re.findall(r'[\u4e00-\u9fff]+', part)
        for seg in cn_chars:
            if len(seg) >= 2:
                tokens.append(seg.lower())
            if len(seg) >= 4:
                # Add 2-char sliding window
                for i in range(len(seg) - 1):
                    tokens.append(seg[i:i+2].lower())
            if len(seg) >= 6:
                # Add 3-char sliding window
                for i in range(len(seg) - 2):
                    tokens.append(seg[i:i+3].lower())

    # Deduplicate while preserving order
    seen = set()
    unique_tokens = []
    for t in tokens:
        if t not in seen:
            seen.add(t)
            unique_tokens.append(t)
    tokens = unique_tokens

    if not tokens:
        return []

    # 2. Score each wiki page
    results: list[dict] = []
    for path in sorted(WIKI_DIR.rglob("*.md")):
        if path.name.startswith("_") or path.name == "log.md":
            continue
        text = path.read_text(encoding="utf-8").lower()
        score = 0
        matched_tokens = 0
        for token in tokens:
            count = text.count(token)
            if count > 0:
                matched_tokens += 1
                # Longer tokens get higher weight
                weight = min(len(token), 4)
                score += min(count * weight, 30)
                # Bonus for title match
                if token in path.stem.lower():
                    score += 20
        # Bonus for matching multiple different tokens (relevance)
        if matched_tokens >= 3:
            score += matched_tokens * 5
        if score > 0:
            rel = path.relative_to(WIKI_DIR)
            meta, _ = _parse_frontmatter(path.read_text(encoding="utf-8"))
            results.append({
                "name": path.stem,
                "path": str(rel),
                "title": meta.get("title", path.stem),
                "score": score,
            })

    results.sort(key=lambda x: x["score"], reverse=True)
    top = results[:limit]
    _cache_set(cache_key, top)
    return top


def get_stats() -> dict:
    """Return wiki statistics."""
    stats = {"pages": 0, "sources": 0, "entities": 0, "concepts": 0, "syntheses": 0}
    if not WIKI_DIR.is_dir():
        return stats

    for path in WIKI_DIR.rglob("*.md"):
        if path.name.startswith("_") or path.name == "log.md":
            continue
        stats["pages"] += 1
        rel = str(path.relative_to(WIKI_DIR))
        if rel.startswith("sources"):
            stats["sources"] += 1
        elif rel.startswith("entities"):
            stats["entities"] += 1
        elif rel.startswith("concepts"):
            stats["concepts"] += 1
        elif rel.startswith("syntheses"):
            stats["syntheses"] += 1
    return stats
