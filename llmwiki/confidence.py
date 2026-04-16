"""Confidence scoring for wiki pages (v1.0 · Sprint 1).

Implements the 4-factor weighted-average confidence formula from the
LLM Book design spec (05-metadata-schema.md):

    confidence = (
        source_count_score  * 0.3 +
        source_quality_score * 0.3 +
        recency_score       * 0.2 +
        cross_reference_score * 0.2
    )

Each factor maps to [0.0, 1.0]. The composite is rounded to 2 decimal
places and stored in YAML frontmatter as ``confidence: 0.85``.

Content-type decay (Ebbinghaus-inspired half-lives):
    architecture    6 months
    tool_version    30 days
    people          3 months
    bug             14 days
    api             2 months
"""

from __future__ import annotations

import math
from datetime import datetime, timezone
from typing import Any, Optional

# ─── Factor 1: Source Count ────────────────────────────────────────────

_SOURCE_COUNT_MAP = {1: 0.4, 2: 0.6, 3: 0.8}


def source_count_score(count: int) -> float:
    """Return a score in [0.0, 1.0] based on the number of raw sources."""
    if count <= 0:
        return 0.0
    return _SOURCE_COUNT_MAP.get(count, 1.0)  # 4+ → 1.0


# ─── Factor 2: Source Quality ──────────────────────────────────────────

_SOURCE_QUALITY_MAP = {
    "official": 1.0,
    "documentation": 1.0,
    "peer_reviewed": 0.9,
    "paper": 0.9,
    "blog": 0.7,
    "tutorial": 0.7,
    "forum": 0.5,
    "llm_generated": 0.3,
    "session_transcript": 0.5,
    "unknown": 0.4,
}


def source_quality_score(quality: str) -> float:
    """Return a score in [0.0, 1.0] for a source quality label."""
    return _SOURCE_QUALITY_MAP.get(quality.lower(), 0.4)


def avg_source_quality(qualities: list[str]) -> float:
    """Average quality score across multiple sources."""
    if not qualities:
        return 0.4
    return sum(source_quality_score(q) for q in qualities) / len(qualities)


# ─── Factor 3: Recency ────────────────────────────────────────────────

def recency_score(
    last_updated: Optional[str],
    *,
    now: Optional[datetime] = None,
) -> float:
    """Return a score in [0.0, 1.0] based on how recently the page was updated.

    Parameters
    ----------
    last_updated : str or None
        ISO-8601 date string (YYYY-MM-DD). ``None`` → 0.3.
    now : datetime, optional
        Override for testing.
    """
    if not last_updated:
        return 0.3
    try:
        dt = datetime.fromisoformat(last_updated)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
    except (ValueError, TypeError):
        return 0.3

    ref = now or datetime.now(timezone.utc)
    age_days = (ref - dt).days
    if age_days < 0:
        return 1.0
    if age_days <= 30:
        return 1.0
    if age_days <= 90:
        return 0.8
    if age_days <= 365:
        return 0.5
    return 0.3


# ─── Factor 4: Cross-References ───────────────────────────────────────

def cross_reference_score(inbound_links: int) -> float:
    """Return a score in [0.0, 1.0] based on the number of inbound wikilinks."""
    if inbound_links <= 0:
        return 0.3
    if inbound_links <= 2:
        return 0.6
    if inbound_links <= 5:
        return 0.8
    return 1.0


# ─── Composite ─────────────────────────────────────────────────────────

def compute_confidence(
    *,
    source_count: int = 1,
    source_qualities: Optional[list[str]] = None,
    last_updated: Optional[str] = None,
    inbound_links: int = 0,
    now: Optional[datetime] = None,
) -> float:
    """Compute the 4-factor confidence score.

    Returns a float in [0.0, 1.0] rounded to 2 decimal places.
    """
    f1 = source_count_score(source_count)
    f2 = avg_source_quality(source_qualities or ["session_transcript"])
    f3 = recency_score(last_updated, now=now)
    f4 = cross_reference_score(inbound_links)

    score = f1 * 0.3 + f2 * 0.3 + f3 * 0.2 + f4 * 0.2
    return round(score, 2)


# ─── Content-Type Decay ───────────────────────────────────────────────

_DECAY_HALF_LIVES_DAYS: dict[str, int] = {
    "architecture": 180,
    "tool_version": 30,
    "people": 90,
    "bug": 14,
    "api": 60,
    "default": 90,
}


def decay_factor(
    content_type: str,
    age_days: int,
) -> float:
    """Ebbinghaus-inspired decay multiplier in (0, 1].

    Uses exponential decay with the content-type's half-life:
        factor = 2^(−age / half_life)

    The caller multiplies the base confidence by this factor.
    """
    hl = _DECAY_HALF_LIVES_DAYS.get(content_type, _DECAY_HALF_LIVES_DAYS["default"])
    if age_days <= 0:
        return 1.0
    return round(2 ** (-age_days / hl), 3)


def apply_decay(
    base_confidence: float,
    content_type: str,
    age_days: int,
) -> float:
    """Apply content-type decay to a base confidence score."""
    return round(base_confidence * decay_factor(content_type, age_days), 2)
