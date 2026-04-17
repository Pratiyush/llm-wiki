"""Candidate approval workflow (v1.1.0 · #51).

New entity/concept pages created by `/wiki-ingest` land in
``wiki/candidates/`` first with ``status: candidate`` frontmatter.
A human then runs `/wiki-review` to promote, merge, or discard each
one. Promoted pages move into ``wiki/entities/`` or ``wiki/concepts/``.
Discarded candidates are archived under ``wiki/archive/candidates/``
for audit.

Rationale: hallucinated entities ("CompanyX" that doesn't exist) should
not land in the trusted wiki layer without human review.

Public API:
  - ``list_candidates(wiki_dir)`` → list of Candidate dicts
  - ``promote(slug, wiki_dir, dest)`` → move candidate into trusted area
  - ``merge(slug, wiki_dir, into_slug)`` → fold candidate into an existing page
  - ``discard(slug, wiki_dir, reason)`` → move to archive/
  - ``stale_candidates(wiki_dir, threshold_days=30)`` → list pages flagged stale
  - ``is_candidate(page_path)`` → bool

Design choices:
  - Separate ``candidates/`` mirror tree (vs status field only) so the
    build step can cleanly exclude them from the public site by default.
  - ``## Connections`` links from candidates stay as-is when promoted;
    callers run `llmwiki lint` afterward to catch any stale pointers.
  - Discard is non-destructive: pages move to ``wiki/archive/candidates/``
    with a timestamped reason file so you can recover them later.
"""

from __future__ import annotations

import re
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional, TypedDict

# ─── constants ─────────────────────────────────────────────────────────

CANDIDATES_DIR_NAME = "candidates"
ARCHIVE_DIR_NAME = "archive"
ARCHIVED_CANDIDATES_SUBDIR = "candidates"

# Subfolders mirrored under wiki/candidates/
MIRRORED_SUBDIRS = ["entities", "concepts", "sources", "syntheses"]

# Default staleness threshold (days)
DEFAULT_STALE_DAYS = 30

FRONTMATTER_RE = re.compile(r"^---\n(.*?)\n---\n(.*)$", re.DOTALL)


# ─── types ─────────────────────────────────────────────────────────────

class Candidate(TypedDict):
    """Info about one candidate page waiting for review."""

    slug: str              # bare filename stem (e.g. "NewEntity")
    rel_path: str          # path relative to wiki/ (e.g. "candidates/entities/NewEntity.md")
    abs_path: Path         # absolute path to the file
    kind: str              # "entities" | "concepts" | "sources" | "syntheses"
    title: str             # frontmatter title
    created: Optional[str] # frontmatter created/last_updated date (YYYY-MM-DD)
    age_days: int          # days since `created`
    body_preview: str      # first 200 chars of body


# ─── helpers ───────────────────────────────────────────────────────────

def _parse_frontmatter(text: str) -> tuple[dict[str, str], str]:
    """Return (meta_dict, body)."""
    m = FRONTMATTER_RE.match(text)
    if not m:
        return {}, text
    out: dict[str, str] = {}
    for line in m.group(1).splitlines():
        if ":" not in line:
            continue
        k, _, v = line.partition(":")
        out[k.strip()] = v.strip().strip('"')
    return out, m.group(2)


def _age_days(date_str: Optional[str], *, now: Optional[datetime] = None) -> int:
    """Compute days between ``date_str`` (YYYY-MM-DD) and now."""
    if not date_str:
        return 0
    try:
        dt = datetime.fromisoformat(date_str)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
    except (ValueError, TypeError):
        return 0
    ref = now or datetime.now(timezone.utc)
    return max(0, (ref - dt).days)


def is_candidate(page_path: Path) -> bool:
    """True if the path is inside wiki/candidates/ subtree."""
    parts = page_path.parts
    return CANDIDATES_DIR_NAME in parts


def candidates_dir(wiki_dir: Path) -> Path:
    """Return wiki/candidates/ (creates parent if needed)."""
    return wiki_dir / CANDIDATES_DIR_NAME


def archive_dir(wiki_dir: Path) -> Path:
    """Return wiki/archive/candidates/."""
    return wiki_dir / ARCHIVE_DIR_NAME / ARCHIVED_CANDIDATES_SUBDIR


# ─── public API ────────────────────────────────────────────────────────


def list_candidates(
    wiki_dir: Path,
    *,
    now: Optional[datetime] = None,
) -> list[Candidate]:
    """Walk wiki/candidates/ and return one entry per pending page."""
    root = candidates_dir(wiki_dir)
    if not root.is_dir():
        return []

    out: list[Candidate] = []
    for sub in MIRRORED_SUBDIRS:
        sub_dir = root / sub
        if not sub_dir.is_dir():
            continue
        for path in sorted(sub_dir.glob("*.md")):
            if path.name == "_context.md":
                continue
            try:
                text = path.read_text(encoding="utf-8")
            except OSError:
                continue
            meta, body = _parse_frontmatter(text)
            created = meta.get("last_updated") or meta.get("date")
            out.append({
                "slug": path.stem,
                "rel_path": str(path.relative_to(wiki_dir)),
                "abs_path": path,
                "kind": sub,
                "title": meta.get("title", path.stem),
                "created": created,
                "age_days": _age_days(created, now=now),
                "body_preview": body.strip()[:200],
            })
    return out


def promote(
    slug: str,
    wiki_dir: Path,
    *,
    kind: Optional[str] = None,
) -> Path:
    """Move ``wiki/candidates/<kind>/<slug>.md`` → ``wiki/<kind>/<slug>.md``.

    If ``kind`` is omitted, infers from where the candidate lives. Rewrites
    the frontmatter ``status:`` from ``candidate`` → ``reviewed`` so the
    lifecycle rule picks it up.

    Returns the new (promoted) path. Raises FileNotFoundError if the
    candidate does not exist.
    """
    candidate = _find_candidate(slug, wiki_dir, kind)
    inferred_kind = candidate.parent.name
    target_dir = wiki_dir / inferred_kind
    target_dir.mkdir(parents=True, exist_ok=True)
    target = target_dir / candidate.name

    text = candidate.read_text(encoding="utf-8")
    text = _rewrite_status(text, old="candidate", new="reviewed")
    target.write_text(text, encoding="utf-8")
    candidate.unlink()
    return target


def merge(
    slug: str,
    wiki_dir: Path,
    *,
    into_slug: str,
    kind: Optional[str] = None,
) -> Path:
    """Append the candidate's body under a ``## Candidate merge — <date>``
    heading into the existing wiki page ``<into_slug>.md``, then discard
    the candidate.

    Returns the path of the target page. Raises FileNotFoundError if either
    page is missing.
    """
    candidate = _find_candidate(slug, wiki_dir, kind)
    inferred_kind = candidate.parent.name
    target = wiki_dir / inferred_kind / f"{into_slug}.md"
    if not target.is_file():
        raise FileNotFoundError(
            f"merge target not found: {target} (candidate={candidate})"
        )

    candidate_text = candidate.read_text(encoding="utf-8")
    _, candidate_body = _parse_frontmatter(candidate_text)

    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    appended = (
        target.read_text(encoding="utf-8").rstrip() +
        f"\n\n## Candidate merge — {today}\n\n" +
        f"Merged from `{candidate.relative_to(wiki_dir)}`:\n\n" +
        candidate_body.strip() + "\n"
    )
    target.write_text(appended, encoding="utf-8")

    # Discard candidate by moving it to archive with a merge-reason file
    _archive_candidate(candidate, wiki_dir, reason=f"merged into {into_slug}")
    return target


def discard(
    slug: str,
    wiki_dir: Path,
    *,
    reason: str = "",
    kind: Optional[str] = None,
) -> Path:
    """Move the candidate to ``wiki/archive/candidates/<timestamp>/<slug>.md``
    with an adjacent ``<slug>.reason.txt`` capturing why.

    Returns the archived path.
    """
    candidate = _find_candidate(slug, wiki_dir, kind)
    return _archive_candidate(candidate, wiki_dir, reason=reason)


def stale_candidates(
    wiki_dir: Path,
    *,
    threshold_days: int = DEFAULT_STALE_DAYS,
    now: Optional[datetime] = None,
) -> list[Candidate]:
    """Return candidates older than ``threshold_days``."""
    return [
        c for c in list_candidates(wiki_dir, now=now)
        if c["age_days"] >= threshold_days
    ]


# ─── internals ─────────────────────────────────────────────────────────


def _find_candidate(
    slug: str,
    wiki_dir: Path,
    kind: Optional[str],
) -> Path:
    """Locate ``<slug>.md`` under wiki/candidates/, optionally filtered by kind."""
    root = candidates_dir(wiki_dir)
    subs = [kind] if kind else MIRRORED_SUBDIRS
    for sub in subs:
        path = root / sub / f"{slug}.md"
        if path.is_file():
            return path
    raise FileNotFoundError(
        f"candidate not found: {slug!r} under {root}"
        + (f" (kind={kind})" if kind else "")
    )


def _rewrite_status(text: str, *, old: str, new: str) -> str:
    """Replace ``status: <old>`` with ``status: <new>`` in frontmatter."""
    pattern = re.compile(
        rf"^(status:\s*){re.escape(old)}(\s*)$",
        re.MULTILINE,
    )
    if pattern.search(text):
        return pattern.sub(rf"\g<1>{new}\g<2>", text)
    # Add status line to frontmatter if missing
    m = FRONTMATTER_RE.match(text)
    if m:
        new_fm = m.group(1) + f"\nstatus: {new}"
        return f"---\n{new_fm}\n---\n{m.group(2)}"
    return text


def _archive_candidate(
    candidate: Path,
    wiki_dir: Path,
    *,
    reason: str,
) -> Path:
    """Move candidate into archive with reason file."""
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H-%M-%S")
    dest_dir = archive_dir(wiki_dir) / stamp
    dest_dir.mkdir(parents=True, exist_ok=True)

    dest = dest_dir / candidate.name
    shutil.move(str(candidate), str(dest))

    if reason:
        reason_file = dest.with_suffix(".reason.txt")
        reason_file.write_text(
            f"Discarded at: {datetime.now(timezone.utc).isoformat()}\n"
            f"Reason: {reason}\n"
            f"Original path: candidates/{candidate.parent.name}/{candidate.name}\n",
            encoding="utf-8",
        )
    return dest
