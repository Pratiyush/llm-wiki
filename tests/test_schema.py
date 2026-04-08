"""Tests for `llmwiki.schema` — structured entity schema (v0.7 · #55)."""

from __future__ import annotations

import pytest

from llmwiki.schema import (
    ENTITY_KIND_AI_MODEL,
    KNOWN_BENCHMARKS,
    benchmark_label,
    format_price,
    is_model_entity,
    parse_model_profile,
)


# ─── is_model_entity ─────────────────────────────────────────────────────


def test_is_model_entity_true_for_ai_model():
    assert is_model_entity({"type": "entity", "entity_kind": "ai-model"}) is True


def test_is_model_entity_false_for_other_entities():
    assert is_model_entity({"type": "entity", "entity_kind": "person"}) is False
    assert is_model_entity({"type": "entity"}) is False
    assert is_model_entity({"type": "source", "entity_kind": "ai-model"}) is False
    assert is_model_entity({}) is False


# ─── parse_model_profile: happy path ─────────────────────────────────────


def test_parse_model_profile_full_schema():
    meta = {
        "title": "Claude Sonnet 4",
        "provider": "Anthropic",
        "model": '{"context_window": 200000, "max_output": 8192, "license": "proprietary", "released": "2026-03-18"}',
        "pricing": '{"input_per_1m": 3.00, "output_per_1m": 15.00, "currency": "USD", "effective": "2026-01-15"}',
        "modalities": ["text", "vision"],
        "benchmarks": '{"gpqa_diamond": 0.725, "swe_bench": 0.619, "mmlu": 0.887}',
    }
    profile, warnings = parse_model_profile(meta)
    assert warnings == []
    assert profile["title"] == "Claude Sonnet 4"
    assert profile["provider"] == "Anthropic"
    assert profile["model"]["context_window"] == 200000
    assert profile["model"]["max_output"] == 8192
    assert profile["model"]["license"] == "proprietary"
    assert profile["pricing"]["input_per_1m"] == 3.00
    assert profile["pricing"]["output_per_1m"] == 15.00
    assert profile["pricing"]["currency"] == "USD"
    assert profile["modalities"] == ["text", "vision"]
    assert profile["benchmarks"]["gpqa_diamond"] == 0.725
    assert profile["benchmarks"]["mmlu"] == 0.887


def test_parse_model_profile_empty_meta():
    profile, warnings = parse_model_profile({})
    assert profile == {}
    assert warnings == []


def test_parse_model_profile_minimum_fields():
    profile, warnings = parse_model_profile({"title": "Test Model"})
    assert profile == {"title": "Test Model"}
    assert warnings == []


# ─── parse_model_profile: validation errors ──────────────────────────────


def test_parse_model_profile_invalid_context_window():
    meta = {"model": '{"context_window": "not a number"}'}
    profile, warnings = parse_model_profile(meta)
    assert "context_window" not in profile.get("model", {})
    assert any("context_window" in w for w in warnings)


def test_parse_model_profile_negative_price_warns():
    meta = {"pricing": '{"input_per_1m": -1.0}'}
    profile, warnings = parse_model_profile(meta)
    assert "pricing" not in profile
    assert any("input_per_1m" in w for w in warnings)


def test_parse_model_profile_benchmark_out_of_range_rejected():
    """Benchmarks are fractions in [0, 1] — e.g. 0.725 not 72.5.
    Values outside that range are rejected with a warning."""
    meta = {"benchmarks": '{"gpqa_diamond": 72.5}'}
    profile, warnings = parse_model_profile(meta)
    assert "benchmarks" not in profile
    assert any("gpqa_diamond" in w and "fraction" in w for w in warnings)


def test_parse_model_profile_malformed_json_treated_as_empty():
    meta = {"model": "{broken", "pricing": "{also broken"}
    profile, warnings = parse_model_profile(meta)
    assert "model" not in profile
    assert "pricing" not in profile
    # These should generate warnings about the expected JSON shape
    assert any("model block" in w for w in warnings)
    assert any("pricing block" in w for w in warnings)


def test_parse_model_profile_non_numeric_benchmark_warns():
    meta = {"benchmarks": '{"swe_bench": "good"}'}
    profile, warnings = parse_model_profile(meta)
    assert profile.get("benchmarks") in (None, {})
    assert any("swe_bench" in w and "number" in w for w in warnings)


def test_parse_model_profile_unknown_benchmark_key_allowed():
    """Forward-compatible: unknown benchmark keys pass through so users
    can add new benchmarks without waiting for a release."""
    meta = {"benchmarks": '{"new_bench_2027": 0.42}'}
    profile, warnings = parse_model_profile(meta)
    assert profile["benchmarks"] == {"new_bench_2027": 0.42}
    assert warnings == []


# ─── benchmark_label ─────────────────────────────────────────────────────


def test_benchmark_label_known_keys():
    assert benchmark_label("gpqa_diamond") == "GPQA Diamond"
    assert benchmark_label("mmlu") == "MMLU"
    assert benchmark_label("swe_bench") == "SWE-bench"


def test_benchmark_label_unknown_key_formatted_nicely():
    assert benchmark_label("my_custom_bench") == "My Custom Bench"


def test_known_benchmarks_constants_non_empty():
    assert "gpqa_diamond" in KNOWN_BENCHMARKS
    assert "mmlu" in KNOWN_BENCHMARKS
    assert len(KNOWN_BENCHMARKS) >= 10


# ─── format_price ────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    "value,currency,expected",
    [
        (3.0, "USD", "$3.00"),
        (15.50, "USD", "$15.50"),
        (0, "USD", "$0.00"),
        (3.0, "EUR", "€3.00"),
        (3.0, "GBP", "£3.00"),
        (3.0, "JPY", "JPY 3.00"),
        (3.0, "usd", "$3.00"),  # case-insensitive
    ],
)
def test_format_price(value, currency, expected):
    assert format_price(value, currency) == expected
