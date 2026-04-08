"""Tests for `llmwiki.viz_tokens` — token usage visualizations (v0.8 · #66)."""

from __future__ import annotations

import re

import pytest

from llmwiki.viz_tokens import (
    _hit_ratio_tier,
    cache_hit_ratio,
    compute_site_stats,
    format_tokens,
    parse_token_totals,
    render_project_token_card,
    render_project_token_timeline,
    render_session_token_card,
    render_site_token_stats,
)


# ─── format_tokens: K/M/B suffixes ───────────────────────────────────────


@pytest.mark.parametrize(
    "n,expected",
    [
        (0, "0"),
        (1, "1"),
        (999, "999"),
        (1000, "1.0K"),
        (1234, "1.2K"),
        (12_345, "12.3K"),
        (999_999, "1000.0K"),  # rounds to K
        (1_000_000, "1.0M"),
        (1_234_567, "1.2M"),
        (1_234_567_890, "1.2B"),
    ],
)
def test_format_tokens(n, expected):
    assert format_tokens(n) == expected


# ─── parse_token_totals handles every frontmatter shape ─────────────────


def test_parse_token_totals_from_json_string():
    meta = {"token_totals": '{"input": 100, "cache_read": 500}'}
    assert parse_token_totals(meta) == {"input": 100, "cache_read": 500}


def test_parse_token_totals_from_dict():
    meta = {"token_totals": {"input": 1, "output": 2}}
    assert parse_token_totals(meta) == {"input": 1, "output": 2}


def test_parse_token_totals_empty_returns_empty():
    for v in (None, "", "{}", {}):
        assert parse_token_totals({"token_totals": v}) == {}


def test_parse_token_totals_missing_returns_empty():
    assert parse_token_totals({}) == {}


def test_parse_token_totals_malformed_json_returns_empty():
    assert parse_token_totals({"token_totals": "{bad json"}) == {}


# ─── cache_hit_ratio ─────────────────────────────────────────────────────


def test_cache_hit_ratio_healthy():
    totals = {"input": 100, "cache_creation": 200, "cache_read": 1700}
    r = cache_hit_ratio(totals)
    assert r is not None
    assert abs(r - 0.85) < 0.01


def test_cache_hit_ratio_zero_input_returns_none():
    assert cache_hit_ratio({"input": 0, "cache_creation": 0, "cache_read": 0}) is None


def test_cache_hit_ratio_no_cache_read_is_zero():
    r = cache_hit_ratio({"input": 1000, "cache_creation": 0, "cache_read": 0})
    assert r == 0.0


def test_cache_hit_ratio_ignores_output():
    """Output tokens should NOT be in the denominator — they're generation,
    not context. Including them would artificially deflate the ratio."""
    with_output = {"input": 100, "cache_read": 900, "output": 10_000}
    without_output = {"input": 100, "cache_read": 900}
    assert cache_hit_ratio(with_output) == cache_hit_ratio(without_output)


# ─── _hit_ratio_tier tiers ───────────────────────────────────────────────


@pytest.mark.parametrize(
    "ratio,tier",
    [
        (None, "tier-unknown"),
        (0.0, "tier-red"),
        (0.49, "tier-red"),
        (0.50, "tier-yellow"),
        (0.79, "tier-yellow"),
        (0.80, "tier-green"),
        (0.99, "tier-green"),
        (1.00, "tier-green"),
    ],
)
def test_hit_ratio_tier(ratio, tier):
    assert _hit_ratio_tier(ratio)[0] == tier


# ─── render_session_token_card ───────────────────────────────────────────


def test_session_card_empty_returns_empty():
    assert render_session_token_card({}) == ""
    assert render_session_token_card({"token_totals": "{}"}) == ""


def test_session_card_renders_all_four_rows_when_present():
    meta = {
        "token_totals": '{"input": 10000, "cache_creation": 20000, "cache_read": 1000000, "output": 5000}'
    }
    card = render_session_token_card(meta)
    for label in ("Input", "Cache creation", "Cache read", "Output"):
        assert label in card
    # Formatted numbers
    assert "10.0K" in card
    assert "20.0K" in card
    assert "1.0M" in card
    assert "5.0K" in card


def test_session_card_shows_cache_hit_ratio_with_tier_class():
    meta = {
        "token_totals": '{"input": 100, "cache_creation": 200, "cache_read": 1700, "output": 0}'
    }
    card = render_session_token_card(meta)
    assert "Cache hit ratio" in card
    assert "85%" in card
    assert "tier-green" in card
    assert "healthy" in card


def test_session_card_shows_total_in_header():
    meta = {
        "token_totals": '{"input": 100, "cache_creation": 100, "cache_read": 100, "output": 100}'
    }
    card = render_session_token_card(meta)
    assert "400 total" in card


def test_session_card_bar_widths_scale_to_max():
    """The largest category sets the 100% mark; smaller ones scale down.
    Zero-count categories (cache_creation, output here) render as 0%."""
    meta = {
        "token_totals": '{"input": 100, "cache_read": 1000, "cache_creation": 0, "output": 0}'
    }
    card = render_session_token_card(meta)
    widths = re.findall(r'width: (\d+(?:\.\d+)?)%', card)
    widths_f = sorted(float(w) for w in widths)
    # Four rows: [0, 0, 10, 100]
    assert widths_f[-1] == 100.0  # cache_read
    # Smallest non-zero width must be ~10% (input is 10% of 1000)
    nonzero = [w for w in widths_f if w > 0]
    assert 9 <= min(nonzero) <= 11
    # cache_creation and output are 0 → 0.0%
    assert widths_f.count(0.0) == 2


def test_session_card_uses_category_classes_per_row():
    meta = {
        "token_totals": '{"input": 10, "cache_creation": 20, "cache_read": 30, "output": 40}'
    }
    card = render_session_token_card(meta)
    for cat in ("input", "cache_creation", "cache_read", "output"):
        assert f"token-bar-{cat}" in card


# ─── render_project_token_timeline ──────────────────────────────────────


def test_project_timeline_empty_returns_empty():
    assert render_project_token_timeline([], "foo") == ""


def test_project_timeline_single_session_still_renders():
    metas = [{"date": "2026-04-07", "token_totals": '{"input": 100, "cache_read": 1000}'}]
    svg = render_project_token_timeline(metas, "demo")
    assert svg.startswith("<svg")
    assert "role=\"img\"" in svg
    assert "demo token usage timeline" in svg


def test_project_timeline_has_axis_lines_and_path():
    metas = [
        {"date": "2026-04-01", "token_totals": '{"input": 100, "cache_read": 5000}'},
        {"date": "2026-04-07", "token_totals": '{"input": 200, "cache_read": 50000}'},
    ]
    svg = render_project_token_timeline(metas, "demo")
    assert '<line class="axis"' in svg
    assert '<path class="area"' in svg
    # Y-axis labels should be formatted token numbers
    assert ">5.1K<" in svg or ">5.0K<" in svg
    # X-axis labels should be YYYY-MM
    assert ">2026-04<" in svg


def test_project_timeline_skips_sessions_without_tokens():
    """Sessions missing `token_totals` are silently dropped, not plotted."""
    metas = [
        {"date": "2026-04-01", "token_totals": "{}"},
        {"date": "2026-04-07", "token_totals": '{"input": 100, "cache_read": 200}'},
    ]
    svg = render_project_token_timeline(metas, "demo")
    assert svg != ""


# ─── render_project_token_card ──────────────────────────────────────────


def test_project_card_has_header_with_total_and_ratio():
    metas = [
        {"date": "2026-04-01", "token_totals": '{"input": 100, "cache_creation": 200, "cache_read": 1700, "output": 5000}'}
    ]
    card = render_project_token_card(metas, "demo")
    assert "Token usage · timeline" in card
    assert "7.0K total" in card
    assert "85%" in card
    assert "tier-green" in card


def test_project_card_empty_returns_empty():
    assert render_project_token_card([], "demo") == ""


# ─── compute_site_stats ─────────────────────────────────────────────────


def test_compute_site_stats_zero_input():
    assert compute_site_stats({})["session_count"] == 0


def test_compute_site_stats_finds_best_ratio_and_heaviest():
    by_project = {
        "alpha": [
            {"token_totals": '{"input": 100, "cache_read": 900, "output": 10}'},
            {"token_totals": '{"input": 100, "cache_read": 900, "output": 10}'},
        ],
        "beta": [
            {"token_totals": '{"input": 1000, "cache_read": 10, "output": 10000}'},
        ],
    }
    stats = compute_site_stats(by_project)
    assert stats["session_count"] == 3
    assert stats["total_tokens"] == (1010 + 1010 + 11010)
    # alpha has ~90% hit ratio, beta has ~1%
    assert stats["best_ratio_project"][0] == "alpha"
    assert stats["best_ratio_project"][1] > 0.85
    # beta has the most total tokens (12010 > 2020)
    assert stats["heaviest_project"][0] == "beta"


def test_compute_site_stats_ignores_empty_sessions():
    by_project = {"alpha": [{"token_totals": "{}"}, {"token_totals": None}]}
    stats = compute_site_stats(by_project)
    assert stats["session_count"] == 0
    assert stats["heaviest_project"] is None
    assert stats["best_ratio_project"] is None


# ─── render_site_token_stats ────────────────────────────────────────────


def test_site_stats_block_returns_empty_when_no_data():
    assert render_site_token_stats({}) == ""


def test_site_stats_block_renders_four_cards():
    by_project = {
        "alpha": [{"token_totals": '{"input": 100, "cache_read": 900}'}],
        "beta": [{"token_totals": '{"input": 500, "cache_read": 10, "output": 2000}'}],
    }
    block = render_site_token_stats(by_project)
    assert "Total tokens" in block
    assert "Average per session" in block
    assert "Best cache hit" in block
    assert "Heaviest project" in block
    assert 'href="projects/alpha.html"' in block
    assert 'href="projects/beta.html"' in block


def test_site_stats_block_respects_link_prefix():
    by_project = {
        "alpha": [{"token_totals": '{"input": 100, "cache_read": 900}'}],
    }
    block = render_site_token_stats(by_project, link_prefix="../")
    assert 'href="../projects/alpha.html"' in block
