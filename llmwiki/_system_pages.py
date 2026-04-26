"""Canonical list of system / nav / scaffolding pages used across
graph.py, lint/rules.py, and (potentially) future emitters.

#arch-l7 (#628 sibling): graph.py and lint/rules.py shipped two
hand-maintained lists of "pages that are exempt from the source /
entity / concept schema." The lists overlapped but drifted —
graph.py had `log-archive-2026`, lint missed it; lint had
`index.md`, graph used type-checks instead.

This module owns the single source of truth. Callers can request
either form via the helpers below.
"""
from __future__ import annotations

# Slugs (no `.md` suffix) — the form graph.py wants because it
# operates on graph-node ids that are already stripped of extension.
SYSTEM_PAGE_SLUGS: frozenset[str] = frozenset({
    "CRITICAL_FACTS",
    "MEMORY",
    "SOUL",
    "hints",
    "hot",
    "dashboard",
    "overview",
    "log",
    "log-archive-2026",
    "index",
})

# Filenames (with `.md`) — the form lint/rules.py wants because its
# input is page paths read off disk.
SYSTEM_PAGE_FILES: frozenset[str] = frozenset(
    f"{slug}.md" for slug in SYSTEM_PAGE_SLUGS
)


def is_system_slug(slug: str) -> bool:
    """True if ``slug`` (no extension) is a known system / nav page."""
    return slug in SYSTEM_PAGE_SLUGS


def is_system_file(basename: str) -> bool:
    """True if ``basename`` ends with ``.md`` and names a system page."""
    return basename in SYSTEM_PAGE_FILES
