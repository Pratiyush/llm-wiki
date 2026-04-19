"""Tests for cache-tier frontmatter + lint rule (v1.2.0 · #52)."""

from __future__ import annotations

from pathlib import Path

import pytest

from llmwiki.cache_tiers import (
    CACHE_TIERS,
    DEFAULT_CACHE_TIER,
    PRELOADED_TIERS,
    TIER_METADATA,
    conflicting_tier_reason,
    estimate_tier_tokens,
    is_preloaded,
    parse_cache_tier,
    summary_excerpt,
    tier_badge_class,
    tier_budget_tokens,
)
from llmwiki.lint import REGISTRY
from llmwiki.lint.rules import CacheTierConsistency


# ─── Constants ────────────────────────────────────────────────────────


def test_cache_tiers_tuple():
    assert CACHE_TIERS == ("L1", "L2", "L3", "L4")


def test_default_tier_is_l3():
    # L3 = on-demand = status quo. Default must preserve old behavior.
    assert DEFAULT_CACHE_TIER == "L3"


def test_preloaded_tiers_are_l1_l2():
    assert PRELOADED_TIERS == frozenset({"L1", "L2"})


def test_every_tier_has_metadata():
    for tier in CACHE_TIERS:
        assert tier in TIER_METADATA
        meta = TIER_METADATA[tier]
        assert meta["label"].startswith(tier)
        assert meta["color"].startswith("#")
        assert meta["when"]
        assert meta["token_budget"] >= 0


def test_l1_budget_is_sharpest():
    # L1 is "always loaded, everywhere" — budget must be smaller than L2
    # (summary-only pre-load can sprawl wider).
    assert TIER_METADATA["L1"]["token_budget"] < TIER_METADATA["L2"]["token_budget"]


def test_on_demand_tiers_have_no_preload_budget():
    assert TIER_METADATA["L3"]["token_budget"] == 0
    assert TIER_METADATA["L4"]["token_budget"] == 0


# ─── parse_cache_tier ─────────────────────────────────────────────────


def test_parse_known_tier_is_noop():
    for tier in CACHE_TIERS:
        out, warning = parse_cache_tier(tier)
        assert out == tier
        assert warning is None


def test_parse_lowercase_is_normalized():
    out, warning = parse_cache_tier("l1")
    assert out == "L1"
    assert warning is None


def test_parse_trimmed_and_split():
    # User typed `L2 — Summary preload` — we split on first space.
    out, warning = parse_cache_tier("  L2 — Summary preload  ")
    assert out == "L2"
    assert warning is None


def test_parse_none_returns_default_no_warning():
    out, warning = parse_cache_tier(None)
    assert out == DEFAULT_CACHE_TIER
    assert warning is None


def test_parse_empty_string_returns_default_no_warning():
    out, warning = parse_cache_tier("   ")
    assert out == DEFAULT_CACHE_TIER
    assert warning is None


def test_parse_invalid_string_returns_default_with_warning():
    out, warning = parse_cache_tier("L9")
    assert out == DEFAULT_CACHE_TIER
    assert warning is not None
    assert "L9" in warning


def test_parse_non_string_input_accepted_via_str_coercion():
    out, warning = parse_cache_tier(1)  # type: ignore[arg-type]
    assert out == DEFAULT_CACHE_TIER
    assert warning is not None


# ─── is_preloaded / tier_badge_class / tier_budget_tokens ────────────


def test_is_preloaded_splits_on_l1_l2():
    assert is_preloaded("L1") is True
    assert is_preloaded("L2") is True
    assert is_preloaded("L3") is False
    assert is_preloaded("L4") is False
    assert is_preloaded("not-a-tier") is False


def test_tier_badge_class_deterministic():
    assert tier_badge_class("L1") == "cache-tier-L1"
    assert tier_badge_class("L4") == "cache-tier-L4"


def test_tier_budget_tokens_unknown_returns_zero():
    assert tier_budget_tokens("unknown") == 0


# ─── summary_excerpt ──────────────────────────────────────────────────


def test_summary_excerpt_finds_summary_section():
    body = (
        "Intro text.\n\n## Summary\n\nOne-line summary.\n\n"
        "## Key Claims\n\n- Claim 1"
    )
    assert summary_excerpt(body).startswith("One-line summary")
    assert "Key Claims" not in summary_excerpt(body)


def test_summary_excerpt_case_insensitive_heading():
    body = "## summary\n\nCase-insensitive."
    assert "Case-insensitive" in summary_excerpt(body)


def test_summary_excerpt_falls_back_to_body_prefix():
    body = "Just a plain body without a Summary heading. " * 20
    out = summary_excerpt(body, max_chars=80)
    assert 1 <= len(out) <= 81  # up to max_chars + the ellipsis


def test_summary_excerpt_handles_empty_body():
    assert summary_excerpt("") == ""


def test_summary_excerpt_truncates_long_summary():
    body = "## Summary\n\n" + ("x" * 1000)
    out = summary_excerpt(body, max_chars=100)
    assert len(out) <= 101  # chars + trailing ellipsis
    assert out.endswith("…")


# ─── estimate_tier_tokens ─────────────────────────────────────────────


def test_estimate_tier_tokens_empty_list():
    assert estimate_tier_tokens([], "L1") == 0


def test_estimate_tier_tokens_only_counts_matching_tier():
    pages = [
        {"meta": {"cache_tier": "L1"}, "body": "x" * 400},
        {"meta": {"cache_tier": "L3"}, "body": "y" * 400},
        {"meta": {"cache_tier": "L1"}, "body": "z" * 800},
    ]
    # 400/4 + 800/4 = 100 + 200 = 300
    assert estimate_tier_tokens(pages, "L1") == 300


def test_estimate_tier_tokens_l2_uses_summary_excerpt():
    pages = [
        {
            "meta": {"cache_tier": "L2"},
            "body": "## Summary\n\nShort. \n\n## Big\n\n" + "x" * 2000,
        }
    ]
    # L2 counts only the Summary block, not the 2000-char body
    tokens = estimate_tier_tokens(pages, "L2")
    assert tokens < 50  # ≈ 7 chars // 4 = 1, floored at 1


# ─── conflicting_tier_reason ──────────────────────────────────────────


def test_l1_with_zero_inbound_is_flagged():
    msg = conflicting_tier_reason("L1", inbound_links=0)
    assert msg is not None
    assert "wasted" in msg or "no inbound" in msg


def test_l1_with_inbound_is_fine():
    assert conflicting_tier_reason("L1", inbound_links=3) is None


def test_l4_with_many_inbound_is_flagged():
    msg = conflicting_tier_reason("L4", inbound_links=5)
    assert msg is not None
    assert "L4" in msg


def test_l4_with_few_inbound_is_fine():
    assert conflicting_tier_reason("L4", inbound_links=1) is None


def test_archived_status_requires_l4():
    msg = conflicting_tier_reason("L3", inbound_links=0, has_archived_status=True)
    assert msg is not None
    assert "archived" in msg


def test_archived_status_with_l4_is_fine():
    assert conflicting_tier_reason(
        "L4", inbound_links=0, has_archived_status=True
    ) is None


# ─── Lint rule registration + run() ───────────────────────────────────


def test_cache_tier_rule_registered():
    from llmwiki.lint import rules  # noqa: F401 — populate registry
    assert "cache_tier_consistency" in REGISTRY


def test_lint_rule_empty_pages_returns_no_issues():
    rule = CacheTierConsistency()
    assert rule.run({}) == []


def test_lint_rule_detects_invalid_tier(tmp_path: Path):
    pages = {
        "x.md": {
            "path": tmp_path / "x.md",
            "rel": "x.md",
            "meta": {"cache_tier": "L99"},
            "body": "body",
        }
    }
    issues = CacheTierConsistency().run(pages)
    assert any("L99" in i["message"] for i in issues)


def test_lint_rule_detects_l1_with_no_inbound(tmp_path: Path):
    pages = {
        "Foo.md": {
            "path": tmp_path / "Foo.md",
            "rel": "entities/Foo.md",
            "meta": {"cache_tier": "L1"},
            "body": "body, no one links here",
        }
    }
    issues = CacheTierConsistency().run(pages)
    assert any("no inbound" in i["message"] or "wasted" in i["message"]
               for i in issues)


def test_lint_rule_detects_archived_status_mismatch(tmp_path: Path):
    pages = {
        "Old.md": {
            "path": tmp_path / "Old.md",
            "rel": "entities/Old.md",
            "meta": {"cache_tier": "L3", "status": "archived"},
            "body": "deprecated entity",
        }
    }
    issues = CacheTierConsistency().run(pages)
    assert any("archived" in i["message"] for i in issues)


def test_lint_rule_fires_budget_warning(tmp_path: Path):
    # Seed more than 5k tokens worth of L1 content (5k tokens ≈ 20k chars)
    big_body = "x" * 25_000
    pages = {
        f"P{i}.md": {
            "path": tmp_path / f"P{i}.md",
            "rel": f"entities/P{i}.md",
            "meta": {"cache_tier": "L1"},
            "body": big_body,
        }
        for i in range(2)  # 2 × 25k chars ≈ 12.5k tokens — above budget
    }
    # give each page one inbound link so the "wasted preload" rule
    # doesn't fire (we're testing the aggregate-budget warning)
    pages["P0.md"]["body"] += " [[P1]]"
    pages["P1.md"]["body"] += " [[P0]]"

    issues = CacheTierConsistency().run(pages)
    assert any("budget" in i["message"] for i in issues)


def test_lint_rule_silent_on_healthy_wiki(tmp_path: Path):
    pages = {
        "Index.md": {
            "path": tmp_path / "Index.md",
            "rel": "Index.md",
            "meta": {"cache_tier": "L1"},
            "body": "Short index. [[Foo]] [[Bar]]",
        },
        "Foo.md": {
            "path": tmp_path / "Foo.md",
            "rel": "entities/Foo.md",
            "meta": {"cache_tier": "L3"},
            "body": "[[Index]]",
        },
        "Bar.md": {
            "path": tmp_path / "Bar.md",
            "rel": "entities/Bar.md",
            "meta": {},  # no cache_tier = L3 default
            "body": "[[Index]]",
        },
    }
    # No tier conflicts, no invalid tiers — should return []
    issues = CacheTierConsistency().run(pages)
    # Only warnings we'd expect: none
    messages = [i["message"] for i in issues]
    assert all(
        "no inbound" not in m and "budget" not in m and "not valid" not in m
        for m in messages
    ), f"unexpected issues on healthy wiki: {messages}"


# ─── Registry count guard ─────────────────────────────────────────────


def test_lint_registry_grew_to_13():
    """Sanity: we bumped from 12 (after #51) to 13 (after #52)."""
    from llmwiki.lint import rules  # noqa: F401 — force registration
    assert len(REGISTRY) == 13
