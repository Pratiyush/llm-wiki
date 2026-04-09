"""Tests for `llmwiki.compare` — auto-generated vs-comparison pages (v0.7 · #58)."""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from llmwiki.compare import (
    compare_pair_score,
    discover_user_overrides,
    generate_pairs,
    pair_slug,
    render_benchmark_chart,
    render_comparison_body,
    render_comparison_table,
    render_comparisons_index,
)


def _make_entry(slug, **profile) -> tuple[Path, dict]:
    return Path(f"/tmp/{slug}.md"), profile


PROFILE_SONNET = {
    "title": "Claude Sonnet 4",
    "provider": "Anthropic",
    "model": {"context_window": 200000, "max_output": 8192, "license": "proprietary"},
    "pricing": {"input_per_1m": 3.0, "output_per_1m": 15.0, "currency": "USD"},
    "modalities": ["text", "vision"],
    "benchmarks": {"gpqa_diamond": 0.725, "swe_bench": 0.619, "mmlu": 0.887},
}

PROFILE_GPT5 = {
    "title": "GPT-5",
    "provider": "OpenAI",
    "model": {"context_window": 128000, "max_output": 16384, "license": "proprietary"},
    "pricing": {"input_per_1m": 5.0, "output_per_1m": 20.0, "currency": "USD"},
    "modalities": ["text", "vision", "audio"],
    "benchmarks": {"gpqa_diamond": 0.680, "swe_bench": 0.595, "mmlu": 0.875},
}

PROFILE_STUB = {"title": "Stub Model"}  # no structured fields


# ─── compare_pair_score ─────────────────────────────────────────────────


def test_compare_pair_score_counts_shared_fields():
    score, shared = compare_pair_score(PROFILE_SONNET, PROFILE_GPT5)
    # Both have: provider, context_window, max_output, license,
    # input_per_1m, output_per_1m, modalities, and 3 shared benchmarks.
    # That's 10+ shared fields.
    assert score >= 8
    assert "provider" in shared
    assert "benchmarks.gpqa_diamond" in shared
    assert "pricing.input_per_1m" in shared


def test_compare_pair_score_empty_profiles():
    score, shared = compare_pair_score({}, {})
    assert score == 0
    assert shared == []


def test_compare_pair_score_disjoint_fields():
    a = {"provider": "X"}
    b = {"benchmarks": {"mmlu": 0.9}}
    score, shared = compare_pair_score(a, b)
    assert score == 0


# ─── generate_pairs ─────────────────────────────────────────────────────


def test_generate_pairs_respects_min_shared_fields():
    entries = [
        _make_entry("Sonnet", **PROFILE_SONNET),
        _make_entry("Stub", **PROFILE_STUB),
    ]
    # Stub has no structured fields → no shared fields → no pair
    pairs = generate_pairs(entries, min_shared_fields=3)
    assert pairs == []


def test_generate_pairs_emits_one_pair_for_two_comparable_entities():
    entries = [
        _make_entry("Sonnet", **PROFILE_SONNET),
        _make_entry("GPT5", **PROFILE_GPT5),
    ]
    pairs = generate_pairs(entries)
    assert len(pairs) == 1
    p = pairs[0]
    # Alphabetical slug order
    assert p["slug_a"] == "GPT5"
    assert p["slug_b"] == "Sonnet"
    assert p["title_a"] == "GPT-5"
    assert p["title_b"] == "Claude Sonnet 4"
    assert p["score"] >= 8


def test_generate_pairs_sorts_by_score_descending():
    """Pairs with more shared fields come first so the build surfaces
    the most comparable ones when the max_pairs cap kicks in."""
    PROFILE_C = dict(PROFILE_SONNET)  # clone
    entries = [
        _make_entry("A", **PROFILE_SONNET),
        _make_entry("B", **PROFILE_GPT5),
        _make_entry("C", **PROFILE_C),  # identical to A → maximal score
    ]
    pairs = generate_pairs(entries)
    assert len(pairs) == 3  # (A,B), (A,C), (B,C)
    assert pairs[0]["score"] >= pairs[1]["score"] >= pairs[2]["score"]


def test_generate_pairs_respects_max_pairs_cap():
    entries = [
        (Path(f"/tmp/M{i}.md"), dict(PROFILE_SONNET, title=f"M{i}"))
        for i in range(10)
    ]
    # 10 choose 2 = 45, cap at 3 → only the top 3 by score
    pairs = generate_pairs(entries, max_pairs=3)
    assert len(pairs) == 3


def test_generate_pairs_single_entry_returns_empty():
    entries = [_make_entry("Only", **PROFILE_SONNET)]
    assert generate_pairs(entries) == []


def test_generate_pairs_empty_input():
    assert generate_pairs([]) == []


# ─── pair_slug ──────────────────────────────────────────────────────────


def test_pair_slug_is_alphabetical():
    entries = [
        _make_entry("ZModel", **PROFILE_SONNET),
        _make_entry("AModel", **PROFILE_GPT5),
    ]
    pairs = generate_pairs(entries)
    slug = pair_slug(pairs[0])
    assert slug == "AModel-vs-ZModel"


# ─── render_comparison_table ────────────────────────────────────────────


def test_table_highlights_different_cells():
    entries = [
        _make_entry("Sonnet", **PROFILE_SONNET),
        _make_entry("GPT5", **PROFILE_GPT5),
    ]
    pair = generate_pairs(entries)[0]
    table = render_comparison_table(pair)
    assert "<table" in table
    # Context windows differ → should have cell-diff class
    assert "cell-diff" in table
    # Both provider strings present
    assert "Anthropic" in table
    assert "OpenAI" in table
    # Context formatted
    assert "200K" in table
    assert "128K" in table


def test_table_shows_em_dash_for_missing_field():
    partial_a = {"title": "A", "provider": "X", "model": {"context_window": 100000}}
    partial_b = {"title": "B", "provider": "Y", "model": {"context_window": 200000}}
    entries = [_make_entry("A", **partial_a), _make_entry("B", **partial_b)]
    pairs = generate_pairs(entries, min_shared_fields=2)
    assert pairs
    table = render_comparison_table(pairs[0])
    # Neither has modalities → both cells render em-dash
    assert "—" in table


# ─── render_benchmark_chart ─────────────────────────────────────────────


def test_benchmark_chart_empty_when_no_shared_benchmarks():
    a = dict(PROFILE_SONNET, benchmarks={"mmlu": 0.9})
    b = dict(PROFILE_GPT5, benchmarks={"gpqa_diamond": 0.8})
    entries = [_make_entry("A", **a), _make_entry("B", **b)]
    pairs = generate_pairs(entries)
    assert render_benchmark_chart(pairs[0]) == ""


def test_benchmark_chart_emits_svg_with_bars_for_shared_keys():
    entries = [
        _make_entry("Sonnet", **PROFILE_SONNET),
        _make_entry("GPT5", **PROFILE_GPT5),
    ]
    pair = generate_pairs(entries)[0]
    svg = render_benchmark_chart(pair)
    assert svg.startswith("<svg")
    assert 'role="img"' in svg
    # Both models have: gpqa_diamond, swe_bench, mmlu → 3 labels
    for label in ("GPQA Diamond", "SWE-bench", "MMLU"):
        assert label in svg
    # Two bars per row = 6 rects minimum
    rects = re.findall(r'<rect ', svg)
    assert len(rects) >= 6


def test_benchmark_chart_tooltip_includes_titles():
    entries = [
        _make_entry("Sonnet", **PROFILE_SONNET),
        _make_entry("GPT5", **PROFILE_GPT5),
    ]
    pair = generate_pairs(entries)[0]
    svg = render_benchmark_chart(pair)
    assert "GPT-5" in svg
    assert "Claude Sonnet 4" in svg


# ─── render_comparison_body ─────────────────────────────────────────────


def test_comparison_body_has_all_three_sections():
    entries = [
        _make_entry("Sonnet", **PROFILE_SONNET),
        _make_entry("GPT5", **PROFILE_GPT5),
    ]
    pair = generate_pairs(entries)[0]
    body = render_comparison_body(pair)
    assert "<h2>Side-by-side</h2>" in body
    assert "<h2>Benchmarks</h2>" in body
    assert "<h2>Summary</h2>" in body
    # Price delta should trigger since inputs differ
    assert "<h2>Price delta</h2>" in body


def test_comparison_body_skips_price_delta_when_equal():
    a = dict(PROFILE_SONNET, pricing=dict(PROFILE_SONNET["pricing"]))
    b = dict(PROFILE_GPT5, pricing=dict(PROFILE_SONNET["pricing"]))
    entries = [_make_entry("A", **a), _make_entry("B", **b)]
    pair = generate_pairs(entries)[0]
    body = render_comparison_body(pair)
    assert "<h2>Price delta</h2>" not in body


def test_comparison_body_price_delta_identifies_cheaper_model():
    entries = [
        _make_entry("Sonnet", **PROFILE_SONNET),  # $3
        _make_entry("GPT5", **PROFILE_GPT5),      # $5
    ]
    pair = generate_pairs(entries)[0]
    body = render_comparison_body(pair)
    # Claude Sonnet 4 is cheaper ($3 vs $5)
    assert "Claude Sonnet 4</strong> is" in body
    assert "cheaper" in body


# ─── render_comparisons_index ──────────────────────────────────────────


def test_index_empty_renders_placeholder():
    html_out = render_comparisons_index([])
    assert "No comparable model pairs found" in html_out


def test_index_rows_link_to_pair_slugs():
    entries = [
        _make_entry("Sonnet", **PROFILE_SONNET),
        _make_entry("GPT5", **PROFILE_GPT5),
    ]
    pairs = generate_pairs(entries)
    html_out = render_comparisons_index(pairs)
    assert "GPT5-vs-Sonnet.html" in html_out
    assert "GPT-5 vs Claude Sonnet 4" in html_out


# ─── discover_user_overrides ───────────────────────────────────────────


def test_discover_user_overrides_missing_dir(tmp_path):
    assert discover_user_overrides(tmp_path / "nope") == {}


def test_discover_user_overrides_reads_files(tmp_path):
    (tmp_path / "ClaudeSonnet4-vs-GPT5.md").write_text(
        "# Hand-written comparison\n\nFull narrative here.\n",
        encoding="utf-8",
    )
    (tmp_path / "Other-vs-Thing.md").write_text("body", encoding="utf-8")
    overrides = discover_user_overrides(tmp_path)
    assert set(overrides.keys()) == {"ClaudeSonnet4-vs-GPT5", "Other-vs-Thing"}
    assert "Hand-written comparison" in overrides["ClaudeSonnet4-vs-GPT5"]
