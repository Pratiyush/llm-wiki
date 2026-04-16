"""Tests for the lifecycle state machine (v1.0, #136)."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from llmwiki.lifecycle import (
    LifecycleState,
    can_transition,
    transition,
    InvalidTransition,
    check_auto_stale,
    check_confidence_stale,
    initial_state,
    parse_lifecycle,
    AUTO_STALE_DAYS,
)


# ─── LifecycleState enum ──────────────────────────────────────────────


def test_lifecycle_states_have_5_values():
    assert len(LifecycleState) == 5


def test_lifecycle_state_values():
    assert LifecycleState.DRAFT.value == "draft"
    assert LifecycleState.REVIEWED.value == "reviewed"
    assert LifecycleState.VERIFIED.value == "verified"
    assert LifecycleState.STALE.value == "stale"
    assert LifecycleState.ARCHIVED.value == "archived"


# ─── Valid transitions ─────────────────────────────────────────────────


@pytest.mark.parametrize("current,target", [
    (LifecycleState.DRAFT, LifecycleState.REVIEWED),
    (LifecycleState.DRAFT, LifecycleState.STALE),
    (LifecycleState.REVIEWED, LifecycleState.VERIFIED),
    (LifecycleState.REVIEWED, LifecycleState.STALE),
    (LifecycleState.VERIFIED, LifecycleState.STALE),
    (LifecycleState.STALE, LifecycleState.REVIEWED),
    (LifecycleState.STALE, LifecycleState.ARCHIVED),
    (LifecycleState.ARCHIVED, LifecycleState.REVIEWED),
])
def test_valid_transitions(current, target):
    assert can_transition(current, target) is True
    result = transition(current, target)
    assert result == target


# ─── Invalid transitions ──────────────────────────────────────────────


@pytest.mark.parametrize("current,target", [
    (LifecycleState.DRAFT, LifecycleState.VERIFIED),  # must go through reviewed
    (LifecycleState.DRAFT, LifecycleState.ARCHIVED),
    (LifecycleState.REVIEWED, LifecycleState.DRAFT),  # no going back
    (LifecycleState.REVIEWED, LifecycleState.ARCHIVED),
    (LifecycleState.VERIFIED, LifecycleState.DRAFT),
    (LifecycleState.VERIFIED, LifecycleState.REVIEWED),
    (LifecycleState.ARCHIVED, LifecycleState.DRAFT),
    (LifecycleState.ARCHIVED, LifecycleState.VERIFIED),
])
def test_invalid_transitions(current, target):
    assert can_transition(current, target) is False
    with pytest.raises(InvalidTransition):
        transition(current, target)


# ─── Auto-stale detection ─────────────────────────────────────────────


def test_auto_stale_triggers_after_90_days():
    now = datetime(2026, 7, 16, tzinfo=timezone.utc)
    result = check_auto_stale(
        LifecycleState.DRAFT, "2026-04-16", now=now
    )
    assert result == LifecycleState.STALE  # 91 days


def test_auto_stale_does_not_trigger_within_90_days():
    now = datetime(2026, 7, 14, tzinfo=timezone.utc)
    result = check_auto_stale(
        LifecycleState.DRAFT, "2026-04-16", now=now
    )
    assert result is None  # 89 days


def test_auto_stale_skips_already_stale():
    now = datetime(2026, 12, 1, tzinfo=timezone.utc)
    result = check_auto_stale(
        LifecycleState.STALE, "2025-01-01", now=now
    )
    assert result is None


def test_auto_stale_skips_archived():
    now = datetime(2026, 12, 1, tzinfo=timezone.utc)
    result = check_auto_stale(
        LifecycleState.ARCHIVED, "2025-01-01", now=now
    )
    assert result is None


def test_auto_stale_none_date_triggers():
    result = check_auto_stale(LifecycleState.DRAFT, None)
    assert result == LifecycleState.STALE


def test_auto_stale_invalid_date_triggers():
    result = check_auto_stale(LifecycleState.REVIEWED, "not-a-date")
    assert result == LifecycleState.STALE


# ─── Confidence-based stale ───────────────────────────────────────────


def test_confidence_stale_triggers_below_threshold():
    result = check_confidence_stale(LifecycleState.REVIEWED, 0.4)
    assert result == LifecycleState.STALE


def test_confidence_stale_ok_above_threshold():
    result = check_confidence_stale(LifecycleState.REVIEWED, 0.5)
    assert result is None


def test_confidence_stale_skips_already_stale():
    result = check_confidence_stale(LifecycleState.STALE, 0.1)
    assert result is None


# ─── Helpers ──────────────────────────────────────────────────────────


def test_initial_state_is_draft():
    assert initial_state() == LifecycleState.DRAFT


def test_parse_lifecycle_valid():
    assert parse_lifecycle("draft") == LifecycleState.DRAFT
    assert parse_lifecycle("REVIEWED") == LifecycleState.REVIEWED
    assert parse_lifecycle("  verified  ") == LifecycleState.VERIFIED


def test_parse_lifecycle_invalid():
    with pytest.raises(ValueError, match="Invalid lifecycle"):
        parse_lifecycle("unknown")
