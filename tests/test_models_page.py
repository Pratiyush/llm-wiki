"""Tests for `llmwiki.models_page` — model-entity discovery + rendering (v0.7 · #55)."""

from __future__ import annotations

from pathlib import Path

import pytest

from llmwiki.models_page import (
    discover_model_entities,
    render_model_info_card,
    render_models_index,
)


# ─── discover_model_entities ─────────────────────────────────────────────


def _write_entity(folder: Path, filename: str, content: str) -> Path:
    path = folder / filename
    path.write_text(content, encoding="utf-8")
    return path


def test_discover_model_entities_empty_dir(tmp_path):
    assert discover_model_entities(tmp_path) == []


def test_discover_model_entities_filters_non_model_pages(tmp_path):
    _write_entity(
        tmp_path, "Alice.md",
        "---\ntype: entity\nentity_kind: person\n---\n\nA person.\n",
    )
    _write_entity(
        tmp_path, "ClaudeSonnet4.md",
        "---\ntype: entity\nentity_kind: ai-model\nprovider: Anthropic\n"
        'model: {"context_window": 200000}\n'
        '---\n\nThe model.\n',
    )
    entries = discover_model_entities(tmp_path)
    assert len(entries) == 1
    path, profile, warnings, body = entries[0]
    assert path.name == "ClaudeSonnet4.md"
    assert profile["provider"] == "Anthropic"


def test_discover_model_entities_skips_context_files(tmp_path):
    _write_entity(
        tmp_path, "_context.md",
        "---\ntype: folder-context\nentity_kind: ai-model\n---\n\nFolder ctx.\n",
    )
    assert discover_model_entities(tmp_path) == []


def test_discover_model_entities_surfaces_warnings(tmp_path):
    _write_entity(
        tmp_path, "BadModel.md",
        '---\ntype: entity\nentity_kind: ai-model\n'
        'pricing: {"input_per_1m": -5}\n'
        '---\n\nBody.\n',
    )
    entries = discover_model_entities(tmp_path)
    assert len(entries) == 1
    _, profile, warnings, _ = entries[0]
    assert warnings  # has at least one warning
    assert "pricing" not in profile


def test_discover_model_entities_missing_dir_returns_empty(tmp_path):
    assert discover_model_entities(tmp_path / "nope") == []


# ─── render_model_info_card ─────────────────────────────────────────────


def test_info_card_empty_profile_returns_empty():
    assert render_model_info_card({}) == ""


def test_info_card_renders_title_and_provider():
    card = render_model_info_card({"title": "Claude Sonnet 4", "provider": "Anthropic"})
    assert "Claude Sonnet 4" in card
    assert "Anthropic" in card
    assert 'class="model-card"' in card


def test_info_card_formats_context_window_as_K():
    card = render_model_info_card({
        "title": "X", "model": {"context_window": 200_000}
    })
    assert "200K" in card


def test_info_card_renders_pricing_row():
    card = render_model_info_card({
        "title": "X",
        "pricing": {
            "input_per_1m": 3.00,
            "output_per_1m": 15.00,
            "currency": "USD",
            "effective": "2026-01-15",
        },
    })
    assert "$3.00" in card
    assert "$15.00" in card
    assert "effective 2026-01-15" in card


def test_info_card_renders_benchmarks_sorted_descending():
    card = render_model_info_card({
        "title": "X",
        "benchmarks": {"gpqa_diamond": 0.725, "mmlu": 0.887, "swe_bench": 0.619},
    })
    # All three benchmark labels appear
    assert "GPQA Diamond" in card
    assert "MMLU" in card
    assert "SWE-bench" in card
    # Highest score (MMLU at 88.7%) should appear before the lowest
    mmlu_pos = card.find("MMLU")
    swe_pos = card.find("SWE-bench")
    assert mmlu_pos < swe_pos, "benchmarks must be sorted descending by score"


def test_info_card_benchmark_bars_width_matches_score():
    card = render_model_info_card({
        "title": "X",
        "benchmarks": {"gpqa_diamond": 0.725},
    })
    assert 'style="width: 72.5%"' in card


def test_info_card_escapes_html_in_title():
    card = render_model_info_card({"title": "<script>x</script>"})
    assert "<script>x</script>" not in card
    assert "&lt;script&gt;" in card


# ─── render_models_index ────────────────────────────────────────────────


def test_models_index_empty_renders_placeholder():
    html_out = render_models_index([])
    assert "No model-entity pages found" in html_out
    assert "wiki/entities/" in html_out


def test_models_index_renders_table_with_rows(tmp_path):
    p1 = tmp_path / "ClaudeSonnet4.md"
    profile_a = {
        "title": "Claude Sonnet 4",
        "provider": "Anthropic",
        "model": {"context_window": 200_000},
        "pricing": {"input_per_1m": 3.0, "output_per_1m": 15.0, "currency": "USD"},
        "benchmarks": {"gpqa_diamond": 0.725, "swe_bench": 0.619},
    }
    p2 = tmp_path / "GPT5.md"
    profile_b = {
        "title": "GPT-5",
        "provider": "OpenAI",
        "model": {"context_window": 128_000},
        "pricing": {"input_per_1m": 5.0, "output_per_1m": 20.0, "currency": "USD"},
        "benchmarks": {"gpqa_diamond": 0.680, "mmlu": 0.875},
    }
    entries = [
        (p1, profile_a, [], "body a"),
        (p2, profile_b, [], "body b"),
    ]
    out = render_models_index(entries)
    assert "Claude Sonnet 4" in out
    assert "GPT-5" in out
    assert '<a href="ClaudeSonnet4.html">' in out
    assert '<a href="GPT5.html">' in out
    # Context windows formatted
    assert "200K" in out
    assert "128K" in out
    # Prices
    assert "$3.00" in out
    assert "$20.00" in out
    # Benchmark columns present — both shared (gpqa_diamond) and
    # model-specific (swe_bench, mmlu) should appear as columns.
    assert "GPQA Diamond" in out
    assert "SWE-bench" in out
    assert "MMLU" in out
    # Missing-benchmark cells render as em-dash muted
    assert 'class="muted">—</td>' in out


def test_models_index_table_has_sortable_class():
    """A sortable class hint gives the client-side sorter something to
    latch onto; absent a JS sorter, the table still renders statically."""
    p = Path("/tmp/X.md")
    entries = [(p, {"title": "X"}, [], "body")]
    out = render_models_index(entries)
    assert 'class="models-table sortable"' in out
