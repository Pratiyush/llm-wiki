"""Tag operations across the wiki (G-15 · #301 / G-16 · #302).

Tags accumulate noise over time — an ingest labels a page ``obsidian``
while another labels it ``Obsidian`` while a third coins
``obsidian-vault``.  Nothing in the pipeline reconciles them.  This
module surfaces four operations so a maintainer can curate the tag
space from the CLI:

* ``list`` — enumerate every tag with usage count.
* ``add <tag> <page>`` — append to a page's frontmatter ``tags:``.
* ``rename <old> <new>`` — rewrite across every page (dry-runnable).
* ``check`` — flag near-duplicate tags (similarity ≥ 0.85, case-insensitive).

Also exposes helpers used by the ``topics_vs_tags_convention`` lint
rule (G-16 · #302) — projects are supposed to use ``topics:`` while
sources/entities/concepts use ``tags:``.

Stdlib-only. No changes to frontmatter format.  Dry-runs never write
to disk.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any, Iterable, Optional

from llmwiki import REPO_ROOT


# ─── frontmatter parsing (minimal, schema-agnostic) ──────────────────────


# #495: replaced local LF-only regex with the canonical
# parse_frontmatter_or_none helper, which also strips BOM and accepts
# CRLF line endings — the previous local regex silently parsed
# Windows-authored / BOM-prefixed pages as no-frontmatter, so every
# tag-rename run skipped them.
from llmwiki._frontmatter import parse_frontmatter_or_none as _parse_frontmatter

# Inline-list tag value: ``tags: [a, b, c]``.
_INLINE_LIST_RE = re.compile(
    r"^(?P<key>tags|topics):\s*\[(?P<body>.*?)\]\s*$",
    re.MULTILINE,
)

# Block-list tag value:
#   tags:
#     - a
#     - b
_BLOCK_LIST_RE = re.compile(
    r"^(?P<key>tags|topics):\s*\n(?P<body>(?:\s{2,}-\s+.+\n?)+)",
    re.MULTILINE,
)


@dataclass(frozen=True)
class TagEntry:
    """One (page, field, tag) row used by list + check."""

    page: Path
    field: str   # "tags" or "topics"
    tag: str


def _iter_tags_in_frontmatter(fm: str) -> list[tuple[str, list[str]]]:
    """Yield ``(field, [tag, ...])`` for every ``tags:`` / ``topics:`` block."""
    out: list[tuple[str, list[str]]] = []
    for m in _INLINE_LIST_RE.finditer(fm):
        body = m.group("body")
        tags = [t.strip().strip('"').strip("'") for t in body.split(",")]
        out.append((m.group("key"), [t for t in tags if t]))
    for m in _BLOCK_LIST_RE.finditer(fm):
        body = m.group("body")
        tags = []
        for line in body.splitlines():
            line = line.strip()
            if line.startswith("-"):
                tags.append(line[1:].strip().strip('"').strip("'"))
        out.append((m.group("key"), [t for t in tags if t]))
    return out


# ─── discovery ───────────────────────────────────────────────────────────


def _iter_wiki_pages(wiki_dir: Path) -> list[Path]:
    if not wiki_dir.is_dir():
        return []
    return sorted(
        p for p in wiki_dir.rglob("*.md")
        if not p.name.startswith("_") and "archive" not in p.parts
    )


def collect_tags(wiki_dir: Optional[Path] = None) -> list[TagEntry]:
    """Walk ``wiki_dir`` and return every tag occurrence."""
    root = wiki_dir or (REPO_ROOT / "wiki")
    out: list[TagEntry] = []
    for p in _iter_wiki_pages(root):
        try:
            text = p.read_text(encoding="utf-8")
        except OSError:
            continue
        fm, _ = _parse_frontmatter(text)
        if fm is None:
            continue
        for field, tags in _iter_tags_in_frontmatter(fm):
            for t in tags:
                out.append(TagEntry(page=p, field=field, tag=t))
    return out


def count_tags(entries: Iterable[TagEntry]) -> dict[str, int]:
    """Usage count per tag (case-sensitive — surface the drift)."""
    out: dict[str, int] = {}
    for e in entries:
        out[e.tag] = out.get(e.tag, 0) + 1
    return out


# ─── rename / add — file surgery ─────────────────────────────────────────


def _rewrite_frontmatter_tags(
    text: str,
    *,
    rename_from: Optional[str] = None,
    rename_to: Optional[str] = None,
    add_tag: Optional[str] = None,
    add_page_field: Optional[str] = None,
) -> tuple[str, int]:
    """Return ``(new_text, change_count)`` after applying the op."""
    fm, body = _parse_frontmatter(text)
    if fm is None:
        if add_tag and add_page_field:
            # Seed frontmatter with the requested tag.
            new_fm = f"{add_page_field}: [{add_tag}]"
            return f"---\n{new_fm}\n---\n{text}", 1
        return text, 0

    changes = 0
    new_fm = fm

    if rename_from and rename_to:
        # Inline list — ``tags: [a, b, c]`` — do per-token replacement
        # so ``"obsidian"`` doesn't clobber ``"obsidian-vault"``.
        def _sub_inline(m: re.Match) -> str:
            nonlocal changes
            body_ = m.group("body")
            items = [t.strip() for t in body_.split(",") if t.strip()]
            new_items = []
            for it in items:
                stripped = it.strip('"').strip("'")
                if stripped == rename_from:
                    new_items.append(rename_to)
                    changes += 1
                else:
                    new_items.append(it)
            return f"{m.group('key')}: [{', '.join(new_items)}]"

        new_fm = _INLINE_LIST_RE.sub(_sub_inline, new_fm)

        # Block list — ``  - obsidian`` line-level swap.
        def _sub_block(m: re.Match) -> str:
            nonlocal changes
            key = m.group("key")
            body_lines = []
            for line in m.group("body").splitlines():
                stripped = line.strip()
                if stripped.startswith("-"):
                    val = stripped[1:].strip().strip('"').strip("'")
                    if val == rename_from:
                        indent = line[: len(line) - len(line.lstrip())]
                        body_lines.append(f"{indent}- {rename_to}")
                        changes += 1
                        continue
                body_lines.append(line)
            return f"{key}:\n" + "\n".join(body_lines) + "\n"

        new_fm = _BLOCK_LIST_RE.sub(_sub_block, new_fm)

    if add_tag and add_page_field:
        # Only add if the requested field exists AND the tag isn't
        # already present; otherwise append a new field.
        field_lines = _iter_tags_in_frontmatter(new_fm)
        existing_fields = {f for f, _ in field_lines}
        if add_page_field in existing_fields:
            existing_values = {
                t
                for f, vals in field_lines if f == add_page_field
                for t in vals
            }
            if add_tag not in existing_values:
                # Inline first — append to the inline block when present.
                def _append_inline(m: re.Match) -> str:
                    nonlocal changes
                    if m.group("key") != add_page_field:
                        return m.group(0)
                    body_ = m.group("body").strip()
                    new_body = f"{body_}, {add_tag}" if body_ else add_tag
                    changes += 1
                    return f"{m.group('key')}: [{new_body}]"

                before_changes = changes
                new_fm = _INLINE_LIST_RE.sub(_append_inline, new_fm)
                if changes == before_changes:
                    # Block form — append a new bullet under the block.
                    def _append_block(m: re.Match) -> str:
                        nonlocal changes
                        if m.group("key") != add_page_field:
                            return m.group(0)
                        changes += 1
                        return m.group(0).rstrip() + f"\n  - {add_tag}\n"

                    new_fm = _BLOCK_LIST_RE.sub(_append_block, new_fm)
        else:
            new_fm = new_fm.rstrip() + f"\n{add_page_field}: [{add_tag}]"
            changes += 1

    if changes == 0:
        return text, 0
    return f"---\n{new_fm}\n---\n{body}", changes


def rename_tag(
    old: str,
    new: str,
    *,
    wiki_dir: Optional[Path] = None,
    dry_run: bool = False,
) -> dict[Path, int]:
    """Rename ``old`` → ``new`` across every page.

    Returns ``{page: changes}``.  With ``dry_run=True`` the files are
    not written — the return value tells the caller what *would* happen.
    """
    if not old or not new:
        raise ValueError("both old and new tags are required")
    if old == new:
        return {}
    root = wiki_dir or (REPO_ROOT / "wiki")
    touched: dict[Path, int] = {}
    for p in _iter_wiki_pages(root):
        try:
            text = p.read_text(encoding="utf-8")
        except OSError:
            continue
        new_text, count = _rewrite_frontmatter_tags(
            text, rename_from=old, rename_to=new
        )
        if count:
            touched[p] = count
            if not dry_run:
                p.write_text(new_text, encoding="utf-8")
    return touched


def add_tag_to_page(
    tag: str,
    page: Path,
    *,
    field: str = "tags",
) -> int:
    """Add ``tag`` to ``page``'s frontmatter (field defaults to ``tags``).

    Returns the number of changes (0 or 1).  Idempotent: adding a tag
    that already exists is a no-op and returns 0.
    """
    if not tag:
        raise ValueError("tag is required")
    if field not in {"tags", "topics"}:
        raise ValueError(f"field must be 'tags' or 'topics', got {field!r}")
    if not page.is_file():
        raise FileNotFoundError(page)
    text = page.read_text(encoding="utf-8")
    new_text, count = _rewrite_frontmatter_tags(
        text, add_tag=tag, add_page_field=field
    )
    if count:
        page.write_text(new_text, encoding="utf-8")
    return count


# ─── check — near-duplicate detector ─────────────────────────────────────


def near_duplicate_tags(
    entries: Iterable[TagEntry],
    *,
    threshold: float = 0.85,
) -> list[tuple[str, str, float]]:
    """Return ``(a, b, similarity)`` pairs exceeding the threshold.

    Comparison is case-insensitive; ``(a, b)`` is always lexicographic.
    Identical tags (case-insensitive) short-circuit to similarity 1.0.
    """
    unique = sorted({e.tag for e in entries}, key=str.lower)
    out: list[tuple[str, str, float]] = []
    for i, a in enumerate(unique):
        for b in unique[i + 1 :]:
            ratio = SequenceMatcher(None, a.lower(), b.lower()).ratio()
            if ratio >= threshold:
                out.append((a, b, ratio))
    return out


# ─── G-16 · topics-vs-tags convention ───────────────────────────────────


def convention_violations(
    entries: Iterable[TagEntry],
) -> list[tuple[Path, str, str]]:
    """Flag pages using the wrong frontmatter field for their type.

    Convention (G-16 · #302):

    * ``wiki/projects/*.md`` MUST use ``topics:``
    * ``wiki/sources/**``, ``wiki/entities/**``, ``wiki/concepts/**``,
      ``wiki/syntheses/**`` MUST use ``tags:``

    Returns ``[(page, expected_field, actual_field), ...]``.
    """
    out: list[tuple[Path, str, str]] = []
    seen_fields: dict[Path, set[str]] = {}
    for e in entries:
        seen_fields.setdefault(e.page, set()).add(e.field)

    for page, fields in seen_fields.items():
        posix = page.as_posix()
        if "/projects/" in posix:
            expected = "topics"
        elif any(
            seg in posix
            for seg in ("/sources/", "/entities/", "/concepts/", "/syntheses/")
        ):
            expected = "tags"
        else:
            # Unknown folder — skip.
            continue
        for field in fields:
            if field != expected:
                out.append((page, expected, field))
    return out


def format_tag_table(counts: dict[str, int]) -> str:
    """Human-readable sort-by-count-desc table."""
    if not counts:
        return "No tags found."
    items = sorted(counts.items(), key=lambda kv: (-kv[1], kv[0].lower()))
    width = max(len(k) for k, _ in items)
    rows = [f"  {'tag':<{width}}  count"]
    rows.append("  " + "-" * width + "  -----")
    for tag, count in items:
        rows.append(f"  {tag:<{width}}  {count:>5}")
    return "\n".join(rows)
