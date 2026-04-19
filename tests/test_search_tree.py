"""Tests for tree-aware search routing (v1.2.0 · #53)."""

from __future__ import annotations

from pathlib import Path

import pytest

from llmwiki.search_tree import (
    DEFAULT_SEARCH_MODE,
    SEARCH_MODES,
    TREE_ELIGIBLE_DEPTH,
    TREE_MODE_THRESHOLD,
    annotate_entry_headings,
    decide_search_mode,
    heading_depths,
    search_index_footer_badge,
)


# ─── Constants ────────────────────────────────────────────────────────


def test_tree_eligible_depth_is_three():
    # Matches the TreeSearch paper — h3+ counts as "deep"
    assert TREE_ELIGIBLE_DEPTH == 3


def test_threshold_matches_paper():
    # 30% is the heuristic flip point from the issue
    assert TREE_MODE_THRESHOLD == 0.30


def test_valid_modes():
    assert SEARCH_MODES == ("flat", "tree", "auto")


def test_default_is_auto():
    assert DEFAULT_SEARCH_MODE == "auto"


# ─── heading_depths ───────────────────────────────────────────────────


def test_heading_depths_empty_body():
    stats = heading_depths("")
    assert stats["heading_max_depth"] == 0
    assert stats["heading_count_by_depth"] == {}


def test_heading_depths_no_headings():
    stats = heading_depths("Just paragraphs and [[links]], no headings.\n\nMore text.")
    assert stats["heading_max_depth"] == 0


def test_heading_depths_shallow():
    body = "# Title\n\n## Summary\n\nBody."
    stats = heading_depths(body)
    assert stats["heading_max_depth"] == 2
    assert stats["heading_count_by_depth"] == {1: 1, 2: 1}


def test_heading_depths_deep():
    body = (
        "# Top\n## A\n### A1\n#### A1a\n### A2\n## B\n"
        "#### deep under nothing\n"
    )
    stats = heading_depths(body)
    assert stats["heading_max_depth"] == 4
    assert stats["heading_count_by_depth"][1] == 1
    assert stats["heading_count_by_depth"][2] == 2
    assert stats["heading_count_by_depth"][3] == 2
    assert stats["heading_count_by_depth"][4] == 2


def test_heading_depths_ignores_non_heading_hashes():
    # `#hashtag` mid-line, `#` without a space, and lines starting with
    # `#` followed by nothing shouldn't count.
    body = (
        "Mention a #hashtag mid-sentence.\n"
        "#nospace\n"
        "#\n"
        "\n"
        "## Real heading\n"
    )
    stats = heading_depths(body)
    assert stats["heading_max_depth"] == 2
    assert stats["heading_count_by_depth"] == {2: 1}


def test_heading_depths_caps_at_max_bucket():
    # ######## should bucket at 6 (h6 is the floor)
    body = "# a\n######## deep"
    stats = heading_depths(body)
    # 8 hashes bucket to 6
    assert 6 in stats["heading_count_by_depth"]


# ─── annotate_entry_headings ──────────────────────────────────────────


def test_annotate_entry_writes_two_keys():
    entry: dict = {"id": "x", "title": "x"}
    body = "# T\n## S\n### Deep"
    annotate_entry_headings(entry, body)
    assert entry["heading_max_depth"] == 3
    # JSON-safe: keys must be strings
    assert all(isinstance(k, str) for k in entry["heading_count_by_depth"])


def test_annotate_entry_empty_body():
    entry: dict = {"id": "x"}
    annotate_entry_headings(entry, "")
    assert entry["heading_max_depth"] == 0
    assert entry["heading_count_by_depth"] == {}


def test_annotate_preserves_other_keys():
    entry: dict = {"id": "x", "title": "X", "body": "content"}
    annotate_entry_headings(entry, "# T")
    assert entry["title"] == "X"
    assert entry["body"] == "content"


def test_annotate_is_json_safe():
    import json as _json
    entry: dict = {"id": "x"}
    annotate_entry_headings(entry, "# T\n## S")
    # Round-trip must work without a custom encoder
    assert _json.loads(_json.dumps(entry))["heading_max_depth"] == 2


# ─── decide_search_mode ───────────────────────────────────────────────


def _entries(depths: list[int]) -> list[dict]:
    return [{"heading_max_depth": d} for d in depths]


def test_decide_empty_corpus_is_flat():
    mode, ratio = decide_search_mode([])
    assert mode == "flat"
    assert ratio == 0.0


def test_decide_all_shallow_is_flat():
    mode, ratio = decide_search_mode(_entries([1, 1, 2, 2, 2]))
    assert mode == "flat"
    assert ratio == 0.0


def test_decide_below_threshold_is_flat():
    # 1 out of 10 = 10% < 30%
    mode, ratio = decide_search_mode(_entries([1, 1, 1, 1, 1, 1, 1, 1, 1, 3]))
    assert mode == "flat"
    assert ratio == pytest.approx(0.1)


def test_decide_at_threshold_is_tree():
    # Exactly 30% deep — threshold is >= so tree wins
    mode, ratio = decide_search_mode(
        _entries([1, 1, 1, 1, 1, 1, 1, 3, 3, 3])
    )
    assert mode == "tree"
    assert ratio == pytest.approx(0.3)


def test_decide_above_threshold_is_tree():
    mode, ratio = decide_search_mode(_entries([3, 3, 4, 4, 4, 5]))
    assert mode == "tree"
    assert ratio == 1.0


def test_decide_override_tree_forces_tree():
    mode, _ = decide_search_mode(_entries([1, 1, 1]), override="tree")
    assert mode == "tree"


def test_decide_override_flat_forces_flat():
    mode, _ = decide_search_mode(_entries([4, 4, 4]), override="flat")
    assert mode == "flat"


def test_decide_override_auto_uses_heuristic():
    mode, _ = decide_search_mode(_entries([1, 1, 1]), override="auto")
    assert mode == "flat"


def test_decide_override_none_uses_default():
    mode, _ = decide_search_mode(_entries([1, 1, 1]), override=None)
    assert mode == "flat"


def test_decide_invalid_override_falls_back_to_auto():
    # Typo in config — don't explode, just default.
    mode, _ = decide_search_mode(_entries([1, 1, 1]), override="magic")
    assert mode == "flat"


def test_decide_override_case_insensitive():
    mode, _ = decide_search_mode(_entries([1]), override="TREE")
    assert mode == "tree"


def test_decide_entries_missing_depth_key_count_as_zero():
    mode, ratio = decide_search_mode([{}, {}, {"heading_max_depth": 3}])
    # 1 deep / 3 total = 33% → tree
    assert mode == "tree"
    assert ratio == pytest.approx(1 / 3)


# ─── footer badge ─────────────────────────────────────────────────────


def test_footer_badge_tree_mode():
    assert "tree mode" in search_index_footer_badge("tree", 0.42).lower()
    assert "42%" in search_index_footer_badge("tree", 0.42)


def test_footer_badge_flat_mode():
    assert "flat mode" in search_index_footer_badge("flat", 0.1).lower()
    assert "10%" in search_index_footer_badge("flat", 0.1)


def test_footer_badge_rounds_to_integer():
    assert "33%" in search_index_footer_badge("flat", 0.3333)


# ─── Build integration ────────────────────────────────────────────────


def test_build_site_accepts_search_mode_kwarg():
    """`build_site(..., search_mode=...)` must be a real kwarg."""
    import inspect
    from llmwiki.build import build_site
    sig = inspect.signature(build_site)
    assert "search_mode" in sig.parameters
    assert sig.parameters["search_mode"].default == "auto"


def test_build_search_index_accepts_search_mode_kwarg():
    import inspect
    from llmwiki.build import build_search_index
    sig = inspect.signature(build_search_index)
    assert "search_mode" in sig.parameters


def test_cli_build_has_search_mode_flag():
    from llmwiki.cli import build_parser
    parser = build_parser()
    # Parse a minimal build invocation
    args = parser.parse_args(["build", "--search-mode", "tree"])
    assert args.search_mode == "tree"


def test_cli_build_search_mode_rejects_unknown():
    from llmwiki.cli import build_parser
    parser = build_parser()
    with pytest.raises(SystemExit):
        parser.parse_args(["build", "--search-mode", "magic"])


def test_cli_build_search_mode_default_is_auto():
    from llmwiki.cli import build_parser
    parser = build_parser()
    args = parser.parse_args(["build"])
    assert args.search_mode == "auto"


def test_build_search_index_stamps_mode_on_output(tmp_path: Path):
    """build_search_index must write `_mode` / `_tree_eligible_ratio` /
    `_mode_badge` into the top-level search-index.json."""
    import json as _json
    from llmwiki.build import build_search_index

    out = tmp_path / "site"
    out.mkdir()
    # Minimal inputs: one source with heavy heading depth + one group
    src_path = tmp_path / "sessions" / "demo" / "one.md"
    src_path.parent.mkdir(parents=True)
    src_path.write_text("# T\n## S\n### Deep\n#### Very\n", encoding="utf-8")

    sources = [(
        src_path,
        {"project": "demo", "slug": "one", "date": "2026-04-19"},
        "# T\n## S\n### Deep\n#### Very\n",
    )]
    groups = {"demo": sources}

    build_search_index(sources, groups, out, search_mode="tree")
    data = _json.loads((out / "search-index.json").read_text(encoding="utf-8"))
    assert data["_mode"] == "tree"
    assert "_tree_eligible_ratio" in data
    assert "_mode_badge" in data
    assert "tree mode" in data["_mode_badge"].lower()


def test_build_search_index_annotates_chunks(tmp_path: Path):
    """Session entries in the per-project chunk must carry the heading
    stats the client consumes for tree walks."""
    import json as _json
    from llmwiki.build import build_search_index

    out = tmp_path / "site"
    out.mkdir()
    src_path = tmp_path / "sessions" / "demo" / "x.md"
    src_path.parent.mkdir(parents=True)
    body = "## A\n### A1\n#### A1a"
    src_path.write_text(body, encoding="utf-8")

    sources = [(src_path, {"project": "demo", "slug": "x"}, body)]
    build_search_index(sources, {"demo": sources}, out)

    chunk = _json.loads((out / "search-chunks" / "demo.json").read_text(encoding="utf-8"))
    assert chunk[0]["heading_max_depth"] == 4
    assert "2" in chunk[0]["heading_count_by_depth"]
    assert "4" in chunk[0]["heading_count_by_depth"]
