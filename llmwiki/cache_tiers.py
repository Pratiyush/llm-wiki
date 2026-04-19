"""L1/L2/L3/L4 cache-tier frontmatter (v1.2.0 · #52).

Pages can carry a ``cache_tier`` frontmatter field to tell ``/wiki-query``
how eagerly to load them. This lets the LLM skip the O(N) discovery
walk and go straight to the ~5-10 pages that matter for every query.

The feature is **fully opt-in**: pages without ``cache_tier`` default
to ``L3`` (on-demand), which is what ``/wiki-query`` does today anyway.
Existing wikis keep working byte-identically.

Tiers
-----
- **L1 — always loaded.** The page content is read in full before
  ``/wiki-query`` answers. Use for: index, overview, hints, CRITICAL_FACTS.
  Budget: ≤ 3 pages, ≤ 5k tokens combined.
- **L2 — summary-only pre-load.** Only the first ``## Summary`` section
  (or the first 400 chars of body if no Summary heading exists) is read
  during context build. Full body is fetched on demand. Use for: hot
  entities, active projects.
- **L3 — on-demand (default).** Loaded only when another page references
  it with ``[[wikilink]]``. Most pages.
- **L4 — archive.** Never loaded unless explicitly named. Use for:
  deprecated entities, old session summaries, anything lifecycle-archived.

Public API
----------
- :data:`CACHE_TIERS` — the valid tier tuple
- :data:`DEFAULT_CACHE_TIER` — falls back to ``"L3"``
- :data:`TIER_METADATA` — per-tier description + recommended budgets
- :func:`parse_cache_tier` — normalize + validate a frontmatter value
- :func:`is_preloaded` — ``True`` for L1/L2 (the tiers ``/wiki-query``
  walks eagerly)
- :func:`summary_excerpt` — pull out the ``## Summary`` body for L2 pages
- :func:`tier_budget_tokens` — soft token budget per tier

Design notes
------------
- **Pure stdlib.** Nothing here imports outside ``llmwiki/``.
- **Lint helper, not lint rule.** The companion lint rule lives in
  ``llmwiki/lint/rules.py`` so this module stays import-cycle-free.
- **Forward-compat.** Unknown tier strings are rejected at parse time
  (lint warning) rather than silently accepted — otherwise typos like
  ``l1`` vs ``L1`` would each get their own cache bucket.
"""

from __future__ import annotations

import re
from typing import Any, Mapping, Optional, TypedDict

# ─── Constants ─────────────────────────────────────────────────────────

CACHE_TIERS: tuple[str, ...] = ("L1", "L2", "L3", "L4")
DEFAULT_CACHE_TIER: str = "L3"

# Pages tagged with these tiers are read during context build for every
# `/wiki-query`, not on demand.
PRELOADED_TIERS: frozenset[str] = frozenset({"L1", "L2"})


class TierMeta(TypedDict):
    """Human-readable metadata for a tier — drives docs + UI badges."""

    label: str            # "L1 — Always loaded"
    color: str            # CSS color for site badges
    when: str             # short description of load timing
    token_budget: int     # soft cap, summed across all pages in the tier


TIER_METADATA: dict[str, TierMeta] = {
    "L1": {
        "label": "L1 — Always loaded",
        "color": "#ef4444",   # red — "expensive, use sparingly"
        "when": "read in full during context build for every /wiki-query",
        "token_budget": 5_000,
    },
    "L2": {
        "label": "L2 — Summary pre-load",
        "color": "#f59e0b",   # amber
        "when": "first ## Summary section is pre-loaded; body on demand",
        "token_budget": 20_000,
    },
    "L3": {
        "label": "L3 — On-demand (default)",
        "color": "#10b981",   # green — "free"
        "when": "loaded only when another page links to it",
        "token_budget": 0,    # no pre-load cost
    },
    "L4": {
        "label": "L4 — Archive",
        "color": "#64748b",   # slate
        "when": "never loaded unless named explicitly",
        "token_budget": 0,
    },
}

# Rough character/token ratio for the summary budget check. Matches the
# char/4 heuristic used in llmwiki/cache.py.
_CHARS_PER_TOKEN = 4

# Regex that finds the ``## Summary`` section body for L2 pre-load.
_SUMMARY_RE = re.compile(
    r"^##\s+Summary\s*\n+(.*?)(?=\n##\s+|\Z)",
    re.IGNORECASE | re.MULTILINE | re.DOTALL,
)


# ─── Parsing / validation ──────────────────────────────────────────────


def parse_cache_tier(value: Any) -> tuple[str, Optional[str]]:
    """Normalize a raw frontmatter value into a valid tier string.

    Returns ``(tier, warning)``. On missing or invalid input the caller
    gets ``DEFAULT_CACHE_TIER`` with a warning string it can surface
    through the lint pipeline.
    """
    if value is None or (isinstance(value, str) and not value.strip()):
        return DEFAULT_CACHE_TIER, None

    raw = str(value).strip().upper()
    # Accept bare "L1" or "L1 — Always" (split on first non-alnum).
    tier = raw.split()[0] if raw else ""

    if tier in CACHE_TIERS:
        return tier, None

    return DEFAULT_CACHE_TIER, (
        f"cache_tier {value!r} is not one of {CACHE_TIERS}; "
        f"treating as {DEFAULT_CACHE_TIER}"
    )


def is_preloaded(tier: str) -> bool:
    """True if the tier is pre-loaded (L1 or L2) vs on-demand (L3/L4)."""
    return tier in PRELOADED_TIERS


def tier_badge_class(tier: str) -> str:
    """CSS class for site badges. Pages get ``cache-tier-L1`` etc."""
    return f"cache-tier-{tier}"


def tier_budget_tokens(tier: str) -> int:
    """Soft token budget for the tier. Used by the lint rule to warn
    when the L1 pool blows past its 5 k cap."""
    meta = TIER_METADATA.get(tier)
    return meta["token_budget"] if meta else 0


# ─── Summary excerpt for L2 pre-load ───────────────────────────────────


def summary_excerpt(body: str, *, max_chars: int = 400) -> str:
    """Pull the ``## Summary`` section out of a page body.

    Called by context builders for L2 pages: we read this once during
    context build and leave the rest of the body for on-demand fetch.

    Fallback: if no ``## Summary`` heading exists, return the first
    ``max_chars`` chars of the body so the caller still has *something*
    to show.
    """
    if not body:
        return ""

    m = _SUMMARY_RE.search(body)
    if m:
        text = m.group(1).strip()
    else:
        text = body.strip()[:max_chars]

    if len(text) > max_chars:
        text = text[:max_chars].rstrip() + "…"
    return text


def estimate_tier_tokens(pages: list[Mapping[str, Any]], tier: str) -> int:
    """Sum the rough token count of every page at the given tier.

    ``pages`` is the list shape returned by :func:`llmwiki.lint.load_pages`
    (each dict has ``meta`` + ``body`` keys). We use the char/4 heuristic
    so this stays stdlib-only.
    """
    total = 0
    for page in pages:
        meta = page.get("meta") or {}
        body = page.get("body") or ""
        parsed, _ = parse_cache_tier(meta.get("cache_tier"))
        if parsed != tier:
            continue
        if tier == "L2":
            total += max(1, len(summary_excerpt(body)) // _CHARS_PER_TOKEN)
        else:
            total += max(1, len(body) // _CHARS_PER_TOKEN)
    return total


# ─── Inbound-link hints for lint rule ──────────────────────────────────


def conflicting_tier_reason(
    tier: str, inbound_links: int, has_archived_status: bool = False
) -> Optional[str]:
    """Return a one-line warning if the tier choice conflicts with
    reality, else ``None``.

    Examples:
      - L1 page with 0 inbound links → "wasted preload"
      - L4 (archive) page with many inbound links → "archived but still
        referenced"
      - L3 page with ``status: archived`` → "mark L4 to match lifecycle"
    """
    if tier == "L1" and inbound_links == 0:
        return (
            "L1 page has no inbound [[wikilinks]] — pre-loading a page "
            "nothing else references wastes context tokens"
        )
    if tier == "L4" and inbound_links >= 3:
        return (
            f"L4 (archive) page has {inbound_links} inbound links — "
            "consider promoting to L3 or fixing the callers"
        )
    if tier != "L4" and has_archived_status:
        return (
            "page has status: archived but cache_tier != L4 — "
            "archived pages should be L4 so /wiki-query skips them"
        )
    return None
