"""Edge case tests for Sprint 1 modules (confidence, lifecycle, schema, log).

Covers: empty inputs, None values, boundary conditions, invalid data,
negative numbers, extreme values, unicode, type mismatches.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone, timedelta
from pathlib import Path

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
from llmwiki.lifecycle import (
    LifecycleState,
    can_transition,
    transition,
    InvalidTransition,
    check_auto_stale,
    check_confidence_stale,
    parse_lifecycle,
)
from llmwiki.schema import ENTITY_TYPES, validate_entity_type
from llmwiki.synth.pipeline import _append_log, _auto_archive_log


# ═══════════════════════════════════════════════════════════════════════
#  CONFIDENCE — edge cases
# ═══════════════════════════════════════════════════════════════════════


class TestConfidenceEdgeCases:
    """Edge cases for confidence scoring."""

    # ─── source_count_score ────────────────────────────────────────────

    def test_negative_source_count(self):
        assert source_count_score(-1) == 0.0
        assert source_count_score(-100) == 0.0

    def test_very_large_source_count(self):
        assert source_count_score(10_000) == 1.0

    # ─── source_quality_score ──────────────────────────────────────────

    def test_empty_string_quality(self):
        # Empty string isn't in the map → fallback 0.4
        assert source_quality_score("") == 0.4

    def test_unicode_quality_label(self):
        assert source_quality_score("日本語") == 0.4  # unknown → fallback

    def test_whitespace_only_quality(self):
        assert source_quality_score("   ") == 0.4

    def test_mixed_case_quality(self):
        assert source_quality_score("Official") == 1.0
        assert source_quality_score("BLOG") == 0.7
        assert source_quality_score("Forum") == 0.5

    # ─── avg_source_quality ────────────────────────────────────────────

    def test_avg_quality_single_item(self):
        assert avg_source_quality(["official"]) == 1.0

    def test_avg_quality_all_unknown(self):
        result = avg_source_quality(["???", "!!!", "^^^"])
        assert result == pytest.approx(0.4)  # all fallback

    def test_avg_quality_large_list(self):
        # 100 items should not break
        result = avg_source_quality(["blog"] * 100)
        assert result == pytest.approx(0.7)

    # ─── recency_score ─────────────────────────────────────────────────

    def test_recency_empty_string(self):
        assert recency_score("") == 0.3

    def test_recency_epoch_date(self):
        now = datetime(2026, 4, 16, tzinfo=timezone.utc)
        assert recency_score("1970-01-01", now=now) == 0.3  # very old

    def test_recency_date_with_time(self):
        now = datetime(2026, 4, 16, tzinfo=timezone.utc)
        assert recency_score("2026-04-15T10:30:00", now=now) == 1.0

    def test_recency_date_with_timezone(self):
        now = datetime(2026, 4, 16, tzinfo=timezone.utc)
        assert recency_score("2026-04-15T10:30:00+05:30", now=now) == 1.0

    def test_recency_boundary_30_days(self):
        now = datetime(2026, 4, 16, tzinfo=timezone.utc)
        # Exactly 30 days → still 1.0
        assert recency_score("2026-03-17", now=now) == 1.0
        # 31 days → 0.8
        assert recency_score("2026-03-16", now=now) == 0.8

    def test_recency_boundary_90_days(self):
        now = datetime(2026, 4, 16, tzinfo=timezone.utc)
        # 90 days → still 0.8
        assert recency_score("2026-01-16", now=now) == 0.8
        # 91 days → 0.5
        assert recency_score("2026-01-15", now=now) == 0.5

    def test_recency_boundary_365_days(self):
        now = datetime(2026, 4, 16, tzinfo=timezone.utc)
        # 365 days → still 0.5
        assert recency_score("2025-04-16", now=now) == 0.5
        # 366 days → 0.3
        assert recency_score("2025-04-15", now=now) == 0.3

    # ─── cross_reference_score ─────────────────────────────────────────

    def test_negative_inbound_links(self):
        assert cross_reference_score(-5) == 0.3

    def test_huge_inbound_links(self):
        assert cross_reference_score(999_999) == 1.0

    # ─── compute_confidence ────────────────────────────────────────────

    def test_compute_all_zeros(self):
        score = compute_confidence(
            source_count=0,
            source_qualities=[],
            last_updated=None,
            inbound_links=0,
        )
        assert 0.0 <= score <= 1.0
        assert score < 0.3  # everything at minimum

    def test_compute_negative_inputs(self):
        score = compute_confidence(
            source_count=-5,
            source_qualities=[],
            last_updated=None,
            inbound_links=-10,
        )
        assert 0.0 <= score <= 1.0

    def test_compute_none_qualities(self):
        score = compute_confidence(source_qualities=None)
        assert 0.0 <= score <= 1.0

    # ─── decay ─────────────────────────────────────────────────────────

    def test_decay_negative_age(self):
        assert decay_factor("architecture", -10) == 1.0

    def test_decay_very_large_age(self):
        factor = decay_factor("bug", 10_000)
        assert factor >= 0.0
        assert factor < 0.001  # essentially zero

    def test_apply_decay_zero_confidence(self):
        assert apply_decay(0.0, "architecture", 180) == 0.0

    def test_apply_decay_negative_confidence(self):
        # Should not produce positive from negative
        result = apply_decay(-0.5, "architecture", 0)
        assert result == -0.5


# ═══════════════════════════════════════════════════════════════════════
#  LIFECYCLE — edge cases
# ═══════════════════════════════════════════════════════════════════════


class TestLifecycleEdgeCases:
    """Edge cases for lifecycle state machine."""

    def test_transition_same_state_is_invalid(self):
        """Transitioning to the same state should fail."""
        for state in LifecycleState:
            assert can_transition(state, state) is False

    def test_transition_with_reason_in_error(self):
        with pytest.raises(InvalidTransition, match="custom reason"):
            transition(
                LifecycleState.DRAFT,
                LifecycleState.ARCHIVED,
                reason="custom reason",
            )

    def test_auto_stale_exactly_at_boundary(self):
        """89 days = not stale, 90 days = stale."""
        now = datetime(2026, 7, 15, tzinfo=timezone.utc)
        # 89 days
        assert check_auto_stale(
            LifecycleState.DRAFT, "2026-04-17", now=now
        ) is None
        # 90 days
        assert check_auto_stale(
            LifecycleState.DRAFT, "2026-04-16", now=now
        ) == LifecycleState.STALE

    def test_auto_stale_with_timezone_aware_date(self):
        now = datetime(2026, 7, 16, tzinfo=timezone.utc)
        result = check_auto_stale(
            LifecycleState.REVIEWED, "2026-04-16T00:00:00+05:30", now=now
        )
        assert result == LifecycleState.STALE

    def test_auto_stale_empty_string_date(self):
        result = check_auto_stale(LifecycleState.DRAFT, "")
        assert result == LifecycleState.STALE

    def test_confidence_stale_at_exact_boundary(self):
        """0.5 = not stale, 0.49 = stale."""
        assert check_confidence_stale(LifecycleState.REVIEWED, 0.5) is None
        assert check_confidence_stale(LifecycleState.REVIEWED, 0.49) == LifecycleState.STALE

    def test_confidence_stale_zero(self):
        assert check_confidence_stale(LifecycleState.DRAFT, 0.0) == LifecycleState.STALE

    def test_confidence_stale_negative(self):
        assert check_confidence_stale(LifecycleState.VERIFIED, -0.1) == LifecycleState.STALE

    def test_parse_lifecycle_unicode(self):
        with pytest.raises(ValueError, match="Invalid lifecycle"):
            parse_lifecycle("草稿")  # Chinese for "draft"

    def test_parse_lifecycle_empty(self):
        with pytest.raises(ValueError, match="Invalid lifecycle"):
            parse_lifecycle("")

    def test_parse_lifecycle_with_newline(self):
        # strip() handles \n — "draft\n" is valid after stripping
        assert parse_lifecycle("draft\n") == LifecycleState.DRAFT

    def test_all_states_are_str_subclass(self):
        """LifecycleState values can be used as dict keys and YAML values."""
        for state in LifecycleState:
            assert isinstance(state.value, str)
            assert state.value == str(state.value)


# ═══════════════════════════════════════════════════════════════════════
#  SCHEMA (entity types) — edge cases
# ═══════════════════════════════════════════════════════════════════════


class TestEntityTypeEdgeCases:
    """Edge cases for entity type validation."""

    def test_unicode_entity_type(self):
        valid, msg = validate_entity_type("人物")  # Chinese for "person"
        assert valid is False

    def test_entity_type_with_numbers(self):
        valid, _ = validate_entity_type("tool2")
        assert valid is False

    def test_entity_type_with_special_chars(self):
        valid, _ = validate_entity_type("per-son")
        assert valid is False

    def test_entity_type_substring_match_rejected(self):
        """'per' is not 'person' — no partial matching."""
        valid, _ = validate_entity_type("per")
        assert valid is False

    def test_entity_type_with_trailing_newline(self):
        # strip() handles \n — "tool\n" is valid after stripping
        valid, _ = validate_entity_type("tool\n")
        assert valid is True

    def test_entity_types_tuple_is_immutable(self):
        with pytest.raises(TypeError):
            ENTITY_TYPES[0] = "hacked"  # type: ignore[index]

    def test_entity_types_no_duplicates(self):
        assert len(ENTITY_TYPES) == len(set(ENTITY_TYPES))


# ═══════════════════════════════════════════════════════════════════════
#  LOG FORMAT — edge cases
# ═══════════════════════════════════════════════════════════════════════


class TestLogEdgeCases:
    """Edge cases for the rich log format and auto-archival."""

    def test_append_log_nonexistent_parent(self, tmp_path: Path):
        """Should silently skip if parent directory doesn't exist."""
        fake_log = tmp_path / "does_not_exist" / "log.md"
        _append_log("test", log_path=fake_log)  # should not raise

    def test_append_log_empty_title(self, tmp_path: Path):
        log = tmp_path / "wiki" / "log.md"
        log.parent.mkdir(parents=True)
        log.write_text("# Log\n", encoding="utf-8")
        _append_log("", log_path=log)
        content = log.read_text(encoding="utf-8")
        assert "## [" in content  # still writes an entry

    def test_append_log_unicode_title(self, tmp_path: Path):
        log = tmp_path / "wiki" / "log.md"
        log.parent.mkdir(parents=True)
        log.write_text("# Log\n", encoding="utf-8")
        _append_log("日本語テスト", log_path=log)
        content = log.read_text(encoding="utf-8")
        assert "日本語テスト" in content

    def test_append_log_with_details(self, tmp_path: Path):
        log = tmp_path / "wiki" / "log.md"
        log.parent.mkdir(parents=True)
        log.write_text("# Log\n", encoding="utf-8")
        _append_log(
            "my-project/my-slug",
            log_path=log,
            operation="ingest",
            details={
                "processed": "3 sources, 12K tokens",
                "created": ["wiki/entities/Foo.md", "wiki/concepts/Bar.md"],
                "updated": ["wiki/index.md"],
                "entities": ["Foo", "Bar", "Baz"],
            },
        )
        content = log.read_text(encoding="utf-8")
        assert "ingest" in content
        assert "Processed: 3 sources" in content
        assert "Created:" in content
        assert "Entities extracted:" in content

    def test_append_log_with_empty_details(self, tmp_path: Path):
        log = tmp_path / "wiki" / "log.md"
        log.parent.mkdir(parents=True)
        log.write_text("# Log\n", encoding="utf-8")
        _append_log("test", log_path=log, details={})
        content = log.read_text(encoding="utf-8")
        # Should still have the header line, no detail lines
        assert "synthesize | test" in content
        assert "Processed:" not in content

    def test_auto_archive_below_threshold(self, tmp_path: Path):
        log = tmp_path / "log.md"
        log.write_text("# Small log\n" + "x" * 100, encoding="utf-8")
        result = _auto_archive_log(log)
        assert result is None  # no archive needed

    def test_auto_archive_above_threshold(self, tmp_path: Path):
        log = tmp_path / "log.md"
        header = "# Wiki Log\nFormat line\nParse line\n---\n\n"
        body = "## [2026-01-01] test | entry\n" * 3000  # well over 50KB
        log.write_text(header + body, encoding="utf-8")
        assert log.stat().st_size > 50 * 1024

        result = _auto_archive_log(log)
        assert result is not None
        assert "log-archive-" in result.name
        assert result.exists()

        # Log should be reset to header only
        remaining = log.read_text(encoding="utf-8")
        assert len(remaining) < 1000  # just the header
        assert "# Wiki Log" in remaining

        # Archive should contain the body
        archived = result.read_text(encoding="utf-8")
        assert "test | entry" in archived

    def test_auto_archive_nonexistent_file(self, tmp_path: Path):
        result = _auto_archive_log(tmp_path / "nonexistent.md")
        assert result is None

    def test_auto_archive_exactly_at_threshold(self, tmp_path: Path):
        log = tmp_path / "log.md"
        # Create file exactly at threshold - 1 byte
        header = "# Log\n"
        padding = "x" * (50 * 1024 - len(header) - 1)
        log.write_bytes((header + padding).encode("utf-8"))
        assert log.stat().st_size < 50 * 1024
        result = _auto_archive_log(log)
        assert result is None  # just under threshold
