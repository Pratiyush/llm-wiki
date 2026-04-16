"""Tests for the confidence scoring module (v1.0, #135)."""

from __future__ import annotations

from datetime import datetime, timezone, timedelta

import pytest

from llmwiki.confidence import (
    source_count_score,
    source_quality_score,
    avg_source_quality,
    recency_score,
    cross_reference_score,
    compute_confidence,
    decay_factor,
    apply_decay,
)


# ─── Factor 1: Source Count ────────────────────────────────────────────


@pytest.mark.parametrize("count,expected", [
    (0, 0.0),
    (1, 0.4),
    (2, 0.6),
    (3, 0.8),
    (4, 1.0),
    (10, 1.0),
])
def test_source_count_score(count, expected):
    assert source_count_score(count) == expected


# ─── Factor 2: Source Quality ──────────────────────────────────────────


@pytest.mark.parametrize("quality,expected", [
    ("official", 1.0),
    ("documentation", 1.0),
    ("peer_reviewed", 0.9),
    ("blog", 0.7),
    ("forum", 0.5),
    ("llm_generated", 0.3),
    ("session_transcript", 0.5),
    ("unknown", 0.4),
    ("OFFICIAL", 1.0),  # case-insensitive
    ("nonexistent", 0.4),  # fallback
])
def test_source_quality_score(quality, expected):
    assert source_quality_score(quality) == expected


def test_avg_source_quality_empty():
    assert avg_source_quality([]) == 0.4


def test_avg_source_quality_mixed():
    result = avg_source_quality(["official", "blog"])
    assert result == pytest.approx((1.0 + 0.7) / 2)


# ─── Factor 3: Recency ────────────────────────────────────────────────


def test_recency_score_recent():
    now = datetime(2026, 4, 16, tzinfo=timezone.utc)
    assert recency_score("2026-04-10", now=now) == 1.0  # 6 days ago


def test_recency_score_medium():
    now = datetime(2026, 4, 16, tzinfo=timezone.utc)
    assert recency_score("2026-02-16", now=now) == 0.8  # 59 days


def test_recency_score_old():
    now = datetime(2026, 4, 16, tzinfo=timezone.utc)
    assert recency_score("2025-10-01", now=now) == 0.5  # ~198 days


def test_recency_score_very_old():
    now = datetime(2026, 4, 16, tzinfo=timezone.utc)
    assert recency_score("2024-01-01", now=now) == 0.3  # >1 year


def test_recency_score_none():
    assert recency_score(None) == 0.3


def test_recency_score_invalid():
    assert recency_score("not-a-date") == 0.3


def test_recency_score_future():
    now = datetime(2026, 4, 16, tzinfo=timezone.utc)
    assert recency_score("2027-01-01", now=now) == 1.0


# ─── Factor 4: Cross-References ───────────────────────────────────────


@pytest.mark.parametrize("links,expected", [
    (0, 0.3),
    (1, 0.6),
    (2, 0.6),
    (3, 0.8),
    (5, 0.8),
    (6, 1.0),
    (100, 1.0),
])
def test_cross_reference_score(links, expected):
    assert cross_reference_score(links) == expected


# ─── Composite ─────────────────────────────────────────────────────────


def test_compute_confidence_defaults():
    score = compute_confidence()
    assert 0.0 <= score <= 1.0


def test_compute_confidence_perfect():
    now = datetime(2026, 4, 16, tzinfo=timezone.utc)
    score = compute_confidence(
        source_count=5,
        source_qualities=["official", "official"],
        last_updated="2026-04-15",
        inbound_links=10,
        now=now,
    )
    assert score == 1.0


def test_compute_confidence_minimal():
    now = datetime(2026, 4, 16, tzinfo=timezone.utc)
    score = compute_confidence(
        source_count=0,
        source_qualities=[],
        last_updated=None,
        inbound_links=0,
        now=now,
    )
    assert score < 0.3


def test_compute_confidence_rounded():
    score = compute_confidence(source_count=2, inbound_links=3)
    # Check it's rounded to 2 decimal places
    assert score == round(score, 2)


# ─── Decay ─────────────────────────────────────────────────────────────


def test_decay_factor_zero_age():
    assert decay_factor("architecture", 0) == 1.0


def test_decay_factor_half_life():
    factor = decay_factor("architecture", 180)  # half-life = 180 days
    assert factor == pytest.approx(0.5, abs=0.01)


def test_decay_factor_tool_version_fast():
    factor = decay_factor("tool_version", 30)  # half-life = 30 days
    assert factor == pytest.approx(0.5, abs=0.01)


def test_decay_factor_bug_very_fast():
    factor = decay_factor("bug", 14)  # half-life = 14 days
    assert factor == pytest.approx(0.5, abs=0.01)


def test_decay_factor_unknown_uses_default():
    factor = decay_factor("unknown_type", 90)  # default half-life = 90 days
    assert factor == pytest.approx(0.5, abs=0.01)


def test_apply_decay():
    result = apply_decay(0.8, "architecture", 0)
    assert result == 0.8

    result = apply_decay(0.8, "architecture", 180)
    assert result == pytest.approx(0.4, abs=0.02)
