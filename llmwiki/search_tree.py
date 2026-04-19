"""Tree-aware search routing (v1.2.0 · #53).

TreeSearch reports +25% MRR on academic papers and 37× faster than
embedding search when ≥ 30 % of the corpus has heading depth ≥ 3. Below
that threshold, **flat mode is faster and gives better results**, so
this module's job is to decide which mode to use and expose the reason
to the client.

Flow
----
1. `llmwiki build` runs `annotate_entry_headings(entry, body)` on every
   session / page / entity entry it puts into `search-index.json`. That
   injects `heading_max_depth` + `heading_count_by_depth` into the
   entry so the client never has to re-parse markdown.
2. `llmwiki build` calls `decide_search_mode(entries, override=...)`
   after collecting all entries. Result lands at the top level of
   `search-index.json` under `_mode` + `_tree_eligible_ratio`.
3. The client reads `_mode` on first load and branches:
   - ``flat`` → existing behaviour, exact-match first then body match.
   - ``tree`` → match by title first, then best-first walk into the
     highest-depth heading that matched.

Manual override: `llmwiki build --search-mode {auto,tree,flat}`. Default
is ``auto`` — the heuristic picks.

Public API
----------
- :data:`TREE_ELIGIBLE_DEPTH` — minimum heading depth that counts as "deep"
- :data:`TREE_MODE_THRESHOLD` — fraction of deep pages that flips to tree
- :data:`SEARCH_MODES` — the valid mode tuple
- :func:`heading_depths` — pure regex scan for per-body depth stats
- :func:`annotate_entry_headings` — mutate an entry dict in place
- :func:`decide_search_mode` — pick mode from corpus + optional override
- :func:`search_index_footer_badge` — short label the palette footer shows

Design notes
------------
- **Stdlib only.** No markdown parser — a regex over ``^(#+) `` is fast
  and accurate enough; pages aren't exotic markdown.
- **Client-side cost is one extra key per entry.** We don't ship
  heading text into the index (keeps chunk sizes flat) — only counts.
  The client reads the target page's HTML directly when the user
  expands a tree hit.
- **Override beats heuristic.** ``--search-mode tree`` forces tree even
  on a shallow corpus, useful when testing a themed subset.
"""

from __future__ import annotations

import re
from typing import Any, Iterable, Literal, Mapping, Optional, TypedDict

# ─── Constants ─────────────────────────────────────────────────────────

# A heading counts as "deep" at ## or below (h2, h3, h4, ...). The
# benchmark cited in issue #53 is h3+; we use ≥ 3 to match.
TREE_ELIGIBLE_DEPTH = 3

# Fraction of corpus pages with depth ≥ TREE_ELIGIBLE_DEPTH above which
# tree mode wins. Below that, flat is both faster and produces better
# ranking. 30% is the TreeSearch-paper threshold.
TREE_MODE_THRESHOLD = 0.30

SearchMode = Literal["flat", "tree", "auto"]
SEARCH_MODES: tuple[SearchMode, ...] = ("flat", "tree", "auto")
DEFAULT_SEARCH_MODE: SearchMode = "auto"

# Max heading depth we bother recording — h6 is already "use a paragraph
# instead". Deeper headings still count but bucket under depth 6.
_MAX_DEPTH_BUCKET = 6

# ``^#+ `` at line start. Match up to 10 `#` so we can detect
# "not actually a heading, just a really long fence" cases. We use
# `[ \t]+` (not `\s+`) so a bare `#\n` can't match across the newline
# and get treated as depth-1.
_HEADING_RE = re.compile(r"^(#{1,10})[ \t]+\S", re.MULTILINE)


# ─── Per-body heading stats ────────────────────────────────────────────


class HeadingStats(TypedDict):
    """Shape injected into each search-index entry."""

    heading_max_depth: int          # 0 if no headings at all
    heading_count_by_depth: dict[int, int]


def heading_depths(body: str) -> HeadingStats:
    """Scan a markdown body and return ``(max_depth, count_by_depth)``.

    A depth of 1 is ``# H1`` (the page title, often stripped before
    indexing). 2 is ``##``, 3 is ``###``, etc. Deeper than
    :data:`_MAX_DEPTH_BUCKET` is bucketed into the last depth so we
    don't carry tail noise.
    """
    counts: dict[int, int] = {}
    max_depth = 0
    if not body:
        return {"heading_max_depth": 0, "heading_count_by_depth": counts}

    for match in _HEADING_RE.finditer(body):
        raw_hashes = len(match.group(1))
        depth = min(raw_hashes, _MAX_DEPTH_BUCKET)
        counts[depth] = counts.get(depth, 0) + 1
        if depth > max_depth:
            max_depth = depth

    return {
        "heading_max_depth": max_depth,
        "heading_count_by_depth": counts,
    }


def annotate_entry_headings(entry: dict[str, Any], body: str) -> None:
    """Mutate ``entry`` in place to add ``heading_max_depth`` and
    ``heading_count_by_depth`` — the two keys the client + the mode
    decider consume.
    """
    stats = heading_depths(body)
    entry["heading_max_depth"] = stats["heading_max_depth"]
    # JSON serialization: dict keys must be strings. Store as str keys
    # so ``json.dumps(entry)`` doesn't need a custom encoder.
    entry["heading_count_by_depth"] = {
        str(k): v for k, v in stats["heading_count_by_depth"].items()
    }


# ─── Mode decision ─────────────────────────────────────────────────────


def _deep_ratio(entries: Iterable[Mapping[str, Any]]) -> tuple[int, int, float]:
    """Return ``(deep_pages, total_pages, ratio)``."""
    total = 0
    deep = 0
    for entry in entries:
        depth = int(entry.get("heading_max_depth", 0))
        total += 1
        if depth >= TREE_ELIGIBLE_DEPTH:
            deep += 1
    ratio = deep / total if total else 0.0
    return deep, total, ratio


def decide_search_mode(
    entries: Iterable[Mapping[str, Any]],
    *,
    override: Optional[str] = None,
) -> tuple[SearchMode, float]:
    """Pick the search mode (``"tree"`` or ``"flat"``) for a corpus.

    Returns ``(mode, deep_ratio)`` so the caller can surface the ratio
    to the user via the palette footer.

    ``override`` accepts the same values as the CLI flag: ``"auto"``,
    ``"tree"``, or ``"flat"``. Unknown strings fall back to auto +
    heuristic; ``None`` means "no flag passed, use auto".
    """
    normalized = (override or DEFAULT_SEARCH_MODE).strip().lower()
    deep, total, ratio = _deep_ratio(entries)

    if normalized == "tree":
        return "tree", ratio
    if normalized == "flat":
        return "flat", ratio
    if normalized not in SEARCH_MODES:
        # Typo — warn via fallback. The caller prints; we just decide.
        normalized = DEFAULT_SEARCH_MODE

    # Auto path: flip to tree only if the corpus clears the threshold.
    if total == 0:
        return "flat", ratio
    return ("tree" if ratio >= TREE_MODE_THRESHOLD else "flat", ratio)


def search_index_footer_badge(
    mode: SearchMode, ratio: float
) -> str:
    """Short text the search palette displays so users see which mode
    the corpus landed on today."""
    pct = int(round(ratio * 100))
    if mode == "tree":
        return f"tree mode · {pct}% deep pages"
    return f"flat mode · {pct}% deep pages"
