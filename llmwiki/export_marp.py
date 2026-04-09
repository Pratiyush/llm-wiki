"""Marp slide deck export — generate presentation-ready markdown from wiki
content (v0.7 · closes #95).

Reads wiki/index.md to find pages relevant to a topic, extracts key claims
from ## Key Facts / ## Key Claims / ## Summary sections, and writes a Marp-
format markdown file that any Marp-compatible tool (VS Code extension, Marp
CLI, or marp-core) can render into HTML/PDF/PPTX slides.

The output is a plain `.marp.md` file — stdlib-only, no Marp CLI dependency.
The user brings their own renderer.

Usage (CLI):

    python3 -m llmwiki export-marp --topic "reinforcement learning"
    python3 -m llmwiki export-marp --topic RAG --out slides/rag.marp.md

Usage (Python):

    from llmwiki.export_marp import export_marp
    path = export_marp("RAG", wiki_dir=Path("wiki"))
"""

from __future__ import annotations

import html
import re
from datetime import date
from pathlib import Path
from typing import Sequence

from llmwiki import REPO_ROOT


# ─── helpers ────────────────────────────────────────────────────────────


def _slugify(text: str) -> str:
    """Convert a topic string to a safe kebab-case filename slug."""
    slug = re.sub(r"[^a-z0-9]+", "-", text.lower().strip())
    return slug.strip("-") or "untitled"


def _escape(text: str) -> str:
    """HTML-escape user-supplied text to prevent XSS in rendered slides."""
    return html.escape(text, quote=True)


def _read_index(wiki_dir: Path) -> str:
    """Read wiki/index.md, returning its content or empty string."""
    index_path = wiki_dir / "index.md"
    if index_path.is_file():
        return index_path.read_text(encoding="utf-8")
    return ""


# ─── page discovery ─────────────────────────────────────────────────────


def _find_matching_pages(
    topic: str,
    wiki_dir: Path,
    index_text: str,
) -> list[tuple[str, Path]]:
    """Return a list of (title, path) tuples for wiki pages that match
    the topic.  Matching is case-insensitive substring search against
    the index line text AND the body of each candidate page."""
    topic_lower = topic.lower()
    results: list[tuple[str, Path]] = []

    # Parse index.md for markdown links: `- [Title](path) — desc`
    link_re = re.compile(r"\[([^\]]+)\]\(([^)]+)\)")
    for m in link_re.finditer(index_text):
        title, rel_path = m.group(1), m.group(2)
        full_path = (wiki_dir / rel_path).resolve()
        if not full_path.is_file():
            continue
        # Check title or surrounding line text
        line_start = index_text.rfind("\n", 0, m.start()) + 1
        line_end = index_text.find("\n", m.end())
        line_text = index_text[line_start:line_end if line_end != -1 else None]
        if topic_lower in line_text.lower():
            results.append((title, full_path))
            continue
        # Fall back: check the file body
        try:
            body = full_path.read_text(encoding="utf-8")
        except OSError:
            continue
        if topic_lower in body.lower():
            results.append((title, full_path))

    return results


# ─── claim extraction ───────────────────────────────────────────────────


def _extract_claims(page_text: str) -> list[str]:
    """Extract bullet-point claims from ## Key Facts, ## Key Claims,
    and the first paragraph of ## Summary."""
    claims: list[str] = []

    # Extract bullets from Key Facts / Key Claims sections
    for section_name in ("Key Facts", "Key Claims"):
        pattern = re.compile(
            rf"^##\s+{section_name}\s*\n(.*?)(?=^##|\Z)",
            re.MULTILINE | re.DOTALL,
        )
        m = pattern.search(page_text)
        if m:
            section_body = m.group(1)
            for line in section_body.splitlines():
                stripped = line.strip()
                if stripped.startswith("- "):
                    claims.append(stripped[2:].strip())

    # Extract first paragraph of Summary
    summary_pattern = re.compile(
        r"^##\s+Summary\s*\n(.*?)(?=^##|\Z)",
        re.MULTILINE | re.DOTALL,
    )
    m = summary_pattern.search(page_text)
    if m:
        section_body = m.group(1).strip()
        # Take the first non-empty paragraph (up to the first blank line)
        para_lines: list[str] = []
        for line in section_body.splitlines():
            if not line.strip():
                if para_lines:
                    break
                continue
            para_lines.append(line.strip())
        if para_lines:
            claims.append(" ".join(para_lines))

    return claims


def _page_title_from_path(page_path: Path) -> str:
    """Derive a wiki-link style name from a page's path."""
    return page_path.stem


# ─── slide rendering ────────────────────────────────────────────────────


def _render_slide_deck(
    topic: str,
    today: str,
    pages: Sequence[tuple[str, list[str]]],
) -> str:
    """Render the full Marp markdown slide deck.

    `pages` is a list of (page_title, [claims...]) tuples.
    """
    safe_topic = _escape(topic)
    slides: list[str] = []

    # ── Marp frontmatter
    slides.append(
        "---\n"
        "marp: true\n"
        "theme: default\n"
        "paginate: true\n"
        "---\n"
    )

    # ── Title slide
    slides.append(
        f"# {safe_topic}\n"
        "\n"
        f"Generated from the LLM Wiki on {today}\n"
    )

    if not pages:
        # No matching pages — single "not found" slide
        slides.append(
            "---\n"
            "\n"
            "## No pages found\n"
            "\n"
            f"No wiki pages matched the topic **{safe_topic}**.\n"
            "\n"
            "Try a broader search term or check `wiki/index.md`.\n"
        )
    else:
        # ── Outline slide
        outline_items = "\n".join(
            f"- {_escape(title)}" for title, _ in pages
        )
        slides.append(
            "---\n"
            "\n"
            "## Outline\n"
            "\n"
            f"{outline_items}\n"
        )

        # ── One slide per page's claims
        for title, claims in pages:
            safe_title = _escape(title)
            if claims:
                bullets = "\n".join(
                    f"- {_escape(c)}" for c in claims
                )
                slides.append(
                    "---\n"
                    "\n"
                    f"## {safe_title}\n"
                    "\n"
                    f"{bullets}\n"
                    "\n"
                    f"*Source: [[{safe_title}]]*\n"
                )
            else:
                slides.append(
                    "---\n"
                    "\n"
                    f"## {safe_title}\n"
                    "\n"
                    "*(No key claims extracted from this page.)*\n"
                    "\n"
                    f"*Source: [[{safe_title}]]*\n"
                )

        # ── Summary slide
        total_claims = sum(len(c) for _, c in pages)
        slides.append(
            "---\n"
            "\n"
            "## Summary\n"
            "\n"
            f"- **{len(pages)}** wiki pages reviewed\n"
            f"- **{total_claims}** key claims extracted\n"
            f"- Topic: **{safe_topic}**\n"
            "\n"
            "*Generated by llmwiki `export-marp`*\n"
        )

    return "\n".join(slides)


# ─── entry point ─────────────────────────────────────────────────────────


def export_marp(
    topic: str,
    wiki_dir: Path | None = None,
    out_path: Path | None = None,
) -> Path:
    """Generate a Marp slide deck from wiki content matching `topic`.

    Args:
        topic: Free-text topic string for substring matching.
        wiki_dir: Path to the wiki/ directory. Defaults to REPO_ROOT/wiki.
        out_path: Output file path. Defaults to
                  wiki/exports/<topic-slug>.marp.md.

    Returns:
        The Path of the written .marp.md file.
    """
    if wiki_dir is None:
        wiki_dir = REPO_ROOT / "wiki"

    slug = _slugify(topic)

    if out_path is None:
        out_path = wiki_dir / "exports" / f"{slug}.marp.md"

    # Read index and discover matching pages
    index_text = _read_index(wiki_dir)
    matching = _find_matching_pages(topic, wiki_dir, index_text)

    # Extract claims from each page
    pages: list[tuple[str, list[str]]] = []
    for title, page_path in matching:
        try:
            body = page_path.read_text(encoding="utf-8")
        except OSError:
            continue
        claims = _extract_claims(body)
        pages.append((title, claims))

    # Render the deck
    today = date.today().isoformat()
    deck = _render_slide_deck(topic, today, pages)

    # Write output
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(deck, encoding="utf-8")

    return out_path
