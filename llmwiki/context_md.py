"""Folder-level `_context.md` discovery and helpers (v0.5 · closes #60).

Inspired by tobi/qmd's folder-context pattern. A `_context.md` file sits
alongside other pages in a directory and describes **what the directory
is for**, so an LLM agent walking the tree can decide which folders are
worth entering for a given query instead of opening random files.

Responsibilities:

1. **Detection** — `load_folder_context(path)` reads a `_context.md` file
   if one exists in `path`, returning `(meta, body)` or `None`.
2. **Exclusion from the page index** — `is_context_file(path)` tells
   `discover_sources()` to skip these files so they never render as
   regular wiki pages.
3. **Lint** — `find_uncontexted_folders(root, threshold=10)` walks a
   directory tree and yields any folder that holds more than `threshold`
   pages without a `_context.md` stub. Called by `llmwiki/link_checker.py`
   via `/wiki-lint`.
4. **Summary extraction** — `folder_context_summary(body)` pulls the
   first paragraph (or first sentence) of a `_context.md` body for use
   as a tooltip/header on index pages.

Stdlib-only — plain string and filesystem ops, no new deps.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Iterable, Iterator, Optional

CONTEXT_FILENAME = "_context.md"

_FRONTMATTER_RE = re.compile(r"^---\n(.*?)\n---\n(.*)$", re.DOTALL)
_WS_RE = re.compile(r"\s+")


def is_context_file(path: Path) -> bool:
    """True if `path` points at a folder-level `_context.md` file.

    Used by `discover_sources()` to skip these files so they don't show
    up as regular wiki pages. Matches only the exact filename — a file
    named `my_context.md` is NOT a folder context.
    """
    return path.name == CONTEXT_FILENAME


def load_folder_context(folder: Path) -> Optional[tuple[dict[str, str], str]]:
    """Read `<folder>/_context.md` if present.

    Returns `(frontmatter_dict, body_text)` or `None` if the file doesn't
    exist / can't be read. The frontmatter parser is intentionally minimal
    (key/value only, no lists or nested objects) because `_context.md`
    metadata is expected to be simple — usually just `type: folder-context`.
    """
    ctx_path = folder / CONTEXT_FILENAME
    if not ctx_path.is_file():
        return None
    try:
        text = ctx_path.read_text(encoding="utf-8")
    except OSError:
        return None

    m = _FRONTMATTER_RE.match(text)
    if not m:
        return {}, text

    raw_fm, body = m.group(1), m.group(2)
    meta: dict[str, str] = {}
    for line in raw_fm.splitlines():
        if ":" not in line:
            continue
        key, _, value = line.partition(":")
        value = value.strip()
        # Strip matching single/double quotes around the value
        if len(value) >= 2 and value[0] == value[-1] and value[0] in ("'", '"'):
            value = value[1:-1]
        meta[key.strip()] = value
    return meta, body


def folder_context_summary(body: str, max_chars: int = 240) -> str:
    """Pull a one-line summary from a `_context.md` body.

    Returns the first non-heading paragraph, collapsed to a single line,
    trimmed to `max_chars` chars with an ellipsis if longer. Empty input
    returns an empty string. Used as a tooltip/header on index pages so
    the folder's purpose is visible without opening the file.
    """
    if not body:
        return ""
    paragraphs: list[str] = []
    current: list[str] = []
    for line in body.splitlines():
        stripped = line.strip()
        if not stripped:
            if current:
                paragraphs.append(" ".join(current))
                current = []
            continue
        if stripped.startswith("#"):
            # Skip headings — we want the prose
            if current:
                paragraphs.append(" ".join(current))
                current = []
            continue
        current.append(stripped)
    if current:
        paragraphs.append(" ".join(current))

    if not paragraphs:
        return ""
    summary = _WS_RE.sub(" ", paragraphs[0]).strip()
    if len(summary) > max_chars:
        summary = summary[: max_chars - 1].rstrip() + "…"
    return summary


def find_uncontexted_folders(
    root: Path,
    threshold: int = 10,
    follow_hidden: bool = False,
) -> Iterator[tuple[Path, int]]:
    """Yield `(folder, page_count)` for every folder under `root` that
    contains more than `threshold` `.md` files but lacks a `_context.md`.

    Hidden directories (starting with `.`) are skipped by default to avoid
    noise from `.git`, `.claude`, etc. `_context.md` itself is not counted
    toward the page total — it's metadata, not a page.

    Used by the lint workflow: large knowledge folders without a stub
    context make LLM navigation much more expensive per query.
    """
    if not root.is_dir():
        return
    for folder in _walk_dirs(root, follow_hidden=follow_hidden):
        md_files = [
            p for p in folder.iterdir()
            if p.is_file() and p.suffix == ".md" and not is_context_file(p)
        ]
        if len(md_files) <= threshold:
            continue
        if (folder / CONTEXT_FILENAME).exists():
            continue
        yield folder, len(md_files)


def _walk_dirs(root: Path, follow_hidden: bool) -> Iterator[Path]:
    """Recursively yield directories under `root` (including `root`),
    skipping hidden ones unless `follow_hidden=True`. Pure-Python walk
    so we don't need `os.walk` and keep everything as `Path`."""
    yield root
    try:
        children = sorted(root.iterdir())
    except OSError:
        return
    for child in children:
        if not child.is_dir():
            continue
        if not follow_hidden and child.name.startswith("."):
            continue
        yield from _walk_dirs(child, follow_hidden=follow_hidden)


def collect_folder_contexts(
    root: Path,
    follow_hidden: bool = False,
) -> dict[Path, tuple[dict[str, str], str]]:
    """Walk `root` and return a `{folder_path: (meta, body)}` map of every
    folder that contains a `_context.md`. Useful for bulk-loading folder
    contexts at build time so pages can surface the summaries as headers
    on their parent folder's index page.
    """
    out: dict[Path, tuple[dict[str, str], str]] = {}
    if not root.is_dir():
        return out
    for folder in _walk_dirs(root, follow_hidden=follow_hidden):
        ctx = load_folder_context(folder)
        if ctx is not None:
            out[folder] = ctx
    return out
