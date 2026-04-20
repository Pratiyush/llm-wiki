"""Tests for llmwiki/cache.py (v1.1.0 · #50)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from llmwiki.cache import (
    BATCH_STATE_FILENAME,
    CACHE_CONTROL_EPHEMERAL,
    CHARS_PER_TOKEN,
    DEFAULT_MODEL,
    MIN_CACHEABLE_TOKENS,
    MODEL_PRICING,
    BatchJob,
    BatchState,
    CachedPrompt,
    CostEstimate,
    add_pending,
    batch_state_path,
    build_messages,
    estimate_cost,
    estimate_tokens,
    format_estimate,
    load_batch_state,
    make_cached_block,
    make_plain_block,
    mark_completed,
    save_batch_state,
    warn_prefix_too_small,
)


# ─── Constants / defaults ─────────────────────────────────────────────


def test_cache_control_shape_matches_anthropic_spec():
    # Anthropic requires exactly {"type": "ephemeral"}
    assert CACHE_CONTROL_EPHEMERAL == {"type": "ephemeral"}


def test_chars_per_token_heuristic():
    assert CHARS_PER_TOKEN == 4


def test_min_cacheable_matches_anthropic_floor():
    # 1024 tokens = Anthropic's documented minimum for cache_control
    assert MIN_CACHEABLE_TOKENS == 1024


def test_default_model_is_in_pricing_table():
    assert DEFAULT_MODEL in MODEL_PRICING


def test_all_models_have_complete_rates():
    required = {"input", "cached_input", "cache_write", "output"}
    for model, rates in MODEL_PRICING.items():
        assert required.issubset(rates.keys()), f"{model} missing rate fields"
        for key in required:
            assert rates[key] >= 0, f"{model}.{key} should be non-negative"


def test_cached_input_cheaper_than_fresh_input():
    """Invariant: cache hits must cost less than un-cached input, or
    there's no point caching."""
    for model, rates in MODEL_PRICING.items():
        assert rates["cached_input"] < rates["input"], (
            f"{model}: cached_input {rates['cached_input']} "
            f"not cheaper than input {rates['input']}"
        )


# ─── Content block builders ───────────────────────────────────────────


def test_make_cached_block_has_cache_control():
    block = make_cached_block("Hello")
    assert block == {
        "type": "text",
        "text": "Hello",
        "cache_control": {"type": "ephemeral"},
    }


def test_make_cached_block_cache_control_is_copy_not_alias():
    # Mutating one block's cache_control must not leak into others.
    a = make_cached_block("a")
    b = make_cached_block("b")
    a["cache_control"]["type"] = "tampered"
    assert b["cache_control"]["type"] == "ephemeral"


def test_make_plain_block_has_no_cache_control():
    assert make_plain_block("Hi") == {"type": "text", "text": "Hi"}


# ─── CachedPrompt / build_messages ────────────────────────────────────


def test_cached_prompt_content_blocks_order_and_caching():
    p = CachedPrompt(stable_prefix="PREFIX", dynamic_suffix="BODY")
    blocks = p.content_blocks()
    assert len(blocks) == 2
    assert blocks[0]["text"] == "PREFIX"
    assert "cache_control" in blocks[0]
    assert blocks[1]["text"] == "BODY"
    assert "cache_control" not in blocks[1]


def test_cached_prompt_empty_prefix_omits_cached_block():
    p = CachedPrompt(stable_prefix="", dynamic_suffix="only body")
    blocks = p.content_blocks()
    assert len(blocks) == 1
    assert blocks[0]["text"] == "only body"
    assert "cache_control" not in blocks[0]


def test_cached_prompt_empty_suffix_still_sends_prefix():
    p = CachedPrompt(stable_prefix="only prefix", dynamic_suffix="")
    blocks = p.content_blocks()
    assert len(blocks) == 1
    assert blocks[0]["text"] == "only prefix"
    assert "cache_control" in blocks[0]


def test_build_messages_shape():
    p = CachedPrompt(stable_prefix="P", dynamic_suffix="B")
    msgs = build_messages(p)
    assert msgs == [
        {
            "role": "user",
            "content": [
                {
                    "type": "text",
                    "text": "P",
                    "cache_control": {"type": "ephemeral"},
                },
                {"type": "text", "text": "B"},
            ],
        }
    ]


def test_cached_prompt_is_frozen():
    p = CachedPrompt(stable_prefix="a", dynamic_suffix="b")
    with pytest.raises(Exception):  # frozen dataclass → FrozenInstanceError
        p.stable_prefix = "changed"  # type: ignore[misc]


# ─── Token estimator ──────────────────────────────────────────────────


def test_estimate_tokens_empty_is_zero():
    assert estimate_tokens("") == 0


def test_estimate_tokens_one_char_is_one():
    # len // 4 = 0, but we floor at 1 for non-empty text so single
    # characters don't silently disappear in cost estimates.
    assert estimate_tokens("a") == 1


def test_estimate_tokens_matches_char_over_four():
    text = "x" * 400
    assert estimate_tokens(text) == 100


def test_estimate_tokens_unicode():
    # Unicode chars count as characters, not bytes — close enough for
    # a preview estimate.
    assert estimate_tokens("日本語") >= 1


# ─── Cost estimator ───────────────────────────────────────────────────


def test_estimate_cost_cache_hit_cheaper_than_miss():
    hit = estimate_cost(
        cached_tokens=10_000,
        fresh_tokens=500,
        output_tokens=500,
        cache_hit=True,
    )
    miss = estimate_cost(
        cached_tokens=10_000,
        fresh_tokens=500,
        output_tokens=500,
        cache_hit=False,
    )
    assert hit.usd < miss.usd


def test_estimate_cost_breakdown_fields():
    est = estimate_cost(
        cached_tokens=1_000_000,
        fresh_tokens=1_000_000,
        output_tokens=1_000_000,
        model="claude-sonnet-4-6",
        cache_hit=True,
    )
    bd = est.breakdown()
    # 1M cached × $0.30 = $0.30; 1M fresh × $3.00 = $3.00; 1M out × $15.00 = $15.00
    assert bd["prefix_usd"] == pytest.approx(0.30)
    assert bd["fresh_usd"] == pytest.approx(3.00)
    assert bd["output_usd"] == pytest.approx(15.00)
    assert est.usd == pytest.approx(18.30)


def test_estimate_cost_first_write_uses_write_rate():
    est = estimate_cost(
        cached_tokens=1_000_000,
        fresh_tokens=0,
        output_tokens=0,
        model="claude-sonnet-4-6",
        cache_hit=False,
    )
    # 1M × $3.75 = $3.75
    assert est.usd == pytest.approx(3.75)


def test_estimate_cost_rejects_unknown_model():
    with pytest.raises(ValueError, match="unknown model"):
        estimate_cost(
            cached_tokens=10, fresh_tokens=10, output_tokens=10,
            model="gpt-999",
        )


def test_estimate_cost_rejects_negative_tokens():
    with pytest.raises(ValueError, match="non-negative"):
        estimate_cost(cached_tokens=-1, fresh_tokens=0, output_tokens=0)
    with pytest.raises(ValueError, match="non-negative"):
        estimate_cost(cached_tokens=0, fresh_tokens=-1, output_tokens=0)
    with pytest.raises(ValueError, match="non-negative"):
        estimate_cost(cached_tokens=0, fresh_tokens=0, output_tokens=-1)


def test_estimate_cost_all_zeros_is_zero():
    est = estimate_cost(cached_tokens=0, fresh_tokens=0, output_tokens=0)
    assert est.usd == 0.0


def test_format_estimate_renders_all_buckets():
    est = estimate_cost(
        cached_tokens=10_000,
        fresh_tokens=500,
        output_tokens=500,
        cache_hit=True,
    )
    out = format_estimate(est)
    assert "Prefix:" in out
    assert "Fresh:" in out
    assert "Output:" in out
    assert "Total:" in out
    assert est.model in out
    assert "cache hit" in out


def test_format_estimate_flags_first_write():
    est = estimate_cost(
        cached_tokens=10_000, fresh_tokens=0, output_tokens=0, cache_hit=False,
    )
    assert "first write" in format_estimate(est)


# ─── Prefix-too-small warning ─────────────────────────────────────────


def test_warn_prefix_too_small_returns_message():
    msg = warn_prefix_too_small(100)
    assert msg is not None
    assert "100" in msg
    assert str(MIN_CACHEABLE_TOKENS) in msg


def test_warn_prefix_too_small_returns_none_at_threshold():
    assert warn_prefix_too_small(MIN_CACHEABLE_TOKENS) is None


def test_warn_prefix_too_small_returns_none_above_threshold():
    assert warn_prefix_too_small(MIN_CACHEABLE_TOKENS + 1) is None


# ─── BatchJob / BatchState round-trip ────────────────────────────────


def test_batch_job_defaults():
    job = BatchJob(batch_id="batch_abc")
    assert job.source_slugs == []
    assert job.submitted_at == ""
    assert job.status == "pending"


def test_batch_state_empty_roundtrip():
    state = BatchState()
    assert state.pending == []
    assert state.completed == []
    assert BatchState.from_json(state.to_json()) == state


def test_batch_state_with_jobs_roundtrip():
    state = BatchState(
        pending=[BatchJob(batch_id="b1", source_slugs=["a", "b"])],
        completed=[BatchJob(batch_id="b0", status="completed")],
    )
    data = state.to_json()
    assert data["pending"][0]["batch_id"] == "b1"
    assert data["pending"][0]["source_slugs"] == ["a", "b"]
    assert data["completed"][0]["status"] == "completed"

    restored = BatchState.from_json(data)
    assert len(restored.pending) == 1
    assert restored.pending[0].batch_id == "b1"


def test_add_pending_deduplicates_by_batch_id():
    state = BatchState()
    add_pending(state, BatchJob(batch_id="b1"))
    add_pending(state, BatchJob(batch_id="b1"))  # duplicate
    add_pending(state, BatchJob(batch_id="b2"))
    assert [b.batch_id for b in state.pending] == ["b1", "b2"]


def test_mark_completed_moves_job_and_updates_status():
    state = BatchState()
    add_pending(state, BatchJob(batch_id="b1"))
    moved = mark_completed(state, "b1", status="completed")
    assert moved is True
    assert state.pending == []
    assert len(state.completed) == 1
    assert state.completed[0].status == "completed"


def test_mark_completed_false_when_missing():
    state = BatchState()
    add_pending(state, BatchJob(batch_id="b1"))
    assert mark_completed(state, "b_nope") is False
    assert len(state.pending) == 1


def test_mark_completed_allows_custom_status():
    state = BatchState()
    add_pending(state, BatchJob(batch_id="b1"))
    mark_completed(state, "b1", status="expired")
    assert state.completed[0].status == "expired"


# ─── Batch state file I/O ─────────────────────────────────────────────


def test_batch_state_path_uses_canonical_filename(tmp_path: Path):
    assert batch_state_path(tmp_path).name == BATCH_STATE_FILENAME
    assert batch_state_path(tmp_path).parent == tmp_path


def test_load_missing_returns_empty_state(tmp_path: Path):
    state = load_batch_state(tmp_path)
    assert state.pending == []
    assert state.completed == []


def test_load_corrupt_returns_empty_state(tmp_path: Path):
    (tmp_path / BATCH_STATE_FILENAME).write_text("not json", encoding="utf-8")
    state = load_batch_state(tmp_path)
    assert state.pending == []
    assert state.completed == []


def test_save_then_load_roundtrip(tmp_path: Path):
    state = BatchState(
        pending=[BatchJob(batch_id="b1", source_slugs=["src/a"])]
    )
    path = save_batch_state(tmp_path, state)
    assert path.is_file()

    restored = load_batch_state(tmp_path)
    assert len(restored.pending) == 1
    assert restored.pending[0].batch_id == "b1"
    assert restored.pending[0].source_slugs == ["src/a"]


def test_save_writes_sorted_and_indented_json(tmp_path: Path):
    state = BatchState(pending=[BatchJob(batch_id="b1")])
    path = save_batch_state(tmp_path, state)
    text = path.read_text(encoding="utf-8")
    data = json.loads(text)
    assert data["pending"][0]["batch_id"] == "b1"
    # indent=2 makes the file diff-friendly in git
    assert "  " in text


# ─── Edge cases ───────────────────────────────────────────────────────


def test_cached_prompt_both_empty_returns_no_blocks():
    p = CachedPrompt(stable_prefix="", dynamic_suffix="")
    assert p.content_blocks() == []


def test_build_messages_preserves_role():
    msgs = build_messages(CachedPrompt(stable_prefix="p", dynamic_suffix="s"))
    assert msgs[0]["role"] == "user"


def test_format_estimate_thousand_separator():
    est = estimate_cost(
        cached_tokens=1_234_567, fresh_tokens=500, output_tokens=500,
    )
    # Ensure the comma formatter runs — key for large-wiki previews
    assert "1,234,567" in format_estimate(est)


def test_cost_estimate_breakdown_sums_to_total():
    est = estimate_cost(
        cached_tokens=1_000,
        fresh_tokens=2_000,
        output_tokens=3_000,
        cache_hit=True,
    )
    bd = est.breakdown()
    total = bd["prefix_usd"] + bd["fresh_usd"] + bd["output_usd"]
    assert total == pytest.approx(est.usd)


# ─── CLI wiring ───────────────────────────────────────────────────────


def test_synthesize_parser_accepts_estimate_flag():
    from llmwiki.cli import build_parser

    parser = build_parser()
    args = parser.parse_args(["synthesize", "--estimate"])
    assert args.estimate is True


def test_synthesize_parser_estimate_defaults_false():
    from llmwiki.cli import build_parser

    parser = build_parser()
    args = parser.parse_args(["synthesize"])
    assert args.estimate is False


def test_estimate_command_emits_total(tmp_path, monkeypatch, capsys):
    # _synthesize_estimate() reads REPO_ROOT for the prefix and calls
    # _discover_raw_sessions() / _load_state() for the per-session bodies.
    # Swap the discovery hook so the test runs in tmp_path with a known
    # body and no dependency on the real raw/ tree.
    from llmwiki import cli as cli_mod

    class _FakePath:
        def __init__(self, name: str, text: str | None = None):
            self.name = name
            self._text = text

        def is_file(self):
            return self._text is not None

        def read_text(self, encoding="utf-8"):
            return self._text or ""

    monkeypatch.setattr(cli_mod, "REPO_ROOT", tmp_path)
    # Seed a prefix so the token estimator has something to chew on.
    (tmp_path / "CLAUDE.md").write_text("x" * 4000, encoding="utf-8")

    import llmwiki.synth.pipeline as pipe

    def _fake_discover(raw_dir=None):
        return [
            (tmp_path / "a.md", {"slug": "a"}, "a body"),
            (tmp_path / "b.md", {"slug": "b"}, "b body"),
        ]

    monkeypatch.setattr(pipe, "_discover_raw_sessions", _fake_discover)
    monkeypatch.setattr(pipe, "_load_state", lambda: {})

    rc = cli_mod._synthesize_estimate()
    out = capsys.readouterr().out
    assert rc == 0
    # G-07 (#293): output now has three-bucket breakdown.  Model name
    # still appears; total collapses into the incremental + full-force
    # rows.
    assert "claude-sonnet-4-6" in out
    assert "Incremental sync:" in out
    assert "Full re-synth:" in out


def test_estimate_command_no_new_sessions(tmp_path, monkeypatch, capsys):
    from llmwiki import cli as cli_mod
    import llmwiki.synth.pipeline as pipe

    monkeypatch.setattr(cli_mod, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(pipe, "_discover_raw_sessions", lambda raw_dir=None: [])
    monkeypatch.setattr(pipe, "_load_state", lambda: {})

    rc = cli_mod._synthesize_estimate()
    out = capsys.readouterr().out
    assert rc == 0
    # G-07: empty corpus now prints "$0.0000 (nothing new — this is a no-op)".
    assert "nothing new" in out
    assert "0.0000" in out
