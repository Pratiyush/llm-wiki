"""Tests for the content-hash cache for ``md_to_html`` (#283).

Covers:
* Cache is correct: identical input → identical output.
* Cache hit doesn't change the output.
* Cache miss increments misses; cache hit increments hits.
* Cache respects size cap (FIFO eviction).
* ``md_to_html_cache_clear()`` resets state.
* Semantics unchanged — output matches the uncached path.
"""

from __future__ import annotations

import pytest

from llmwiki.build import (
    _md_to_html_uncached,
    md_to_html,
    md_to_html_cache_clear,
    md_to_html_cache_stats,
)


@pytest.fixture(autouse=True)
def _clear_cache_before_each_test():
    md_to_html_cache_clear()
    yield
    md_to_html_cache_clear()


def test_cache_returns_identical_output_on_hit():
    body = "# Hello\n\nA paragraph with `code`.\n"
    first = md_to_html(body)
    second = md_to_html(body)
    assert first == second


def test_cache_hits_counted():
    body = "# Hi"
    md_to_html(body)
    md_to_html(body)
    md_to_html(body)
    stats = md_to_html_cache_stats()
    assert stats["hits"] == 2
    assert stats["misses"] == 1


def test_distinct_inputs_count_as_distinct_misses():
    md_to_html("# A")
    md_to_html("# B")
    md_to_html("# A")  # hit
    stats = md_to_html_cache_stats()
    assert stats["misses"] == 2
    assert stats["hits"] == 1


def test_cache_size_reflects_stored_entries():
    md_to_html("# A")
    md_to_html("# B")
    md_to_html("# C")
    assert md_to_html_cache_stats()["size"] == 3


def test_cache_clear_resets_state():
    md_to_html("# A")
    md_to_html("# A")
    md_to_html_cache_clear()
    stats = md_to_html_cache_stats()
    # #417: stats now also expose plain_* fields for the
    # md_to_plain_text cache. All hit/miss/size counters reset.
    assert stats["hits"] == 0
    assert stats["misses"] == 0
    assert stats["size"] == 0
    assert stats["plain_hits"] == 0
    assert stats["plain_misses"] == 0
    assert stats["plain_size"] == 0


def test_cached_output_matches_uncached_semantics():
    body = """# Title

A paragraph.

## Section

- bullet
- bullet

```python
print("code")
```
"""
    cached = md_to_html(body)
    uncached = _md_to_html_uncached(body)
    assert cached == uncached


def test_cache_evicts_when_full():
    # Temporarily lower the cap for this test.
    import llmwiki.build as b
    orig = b._MD_CACHE_MAX
    b._MD_CACHE_MAX = 3
    try:
        md_to_html("# A")
        md_to_html("# B")
        md_to_html("# C")
        md_to_html("# D")  # should evict "# A"
        assert md_to_html_cache_stats()["size"] == 3
        md_to_html("# A")  # was evicted → miss again
        stats = md_to_html_cache_stats()
        assert stats["misses"] == 5
    finally:
        b._MD_CACHE_MAX = orig


def test_cache_handles_empty_body():
    empty_out = md_to_html("")
    assert md_to_html("") == empty_out  # still cacheable


def test_cache_handles_unicode():
    body = "# 日本語\n\nBody in Japanese.\n"
    out = md_to_html(body)
    assert "日本語" in out
    # Hit on second call.
    md_to_html(body)
    assert md_to_html_cache_stats()["hits"] == 1


def test_cache_is_content_keyed_not_object_keyed():
    """Two independently-built strings with the same content should
    both hit the cache (SHA-256 keyed)."""
    body1 = "# H\n\nP"
    body2 = "# H" + "\n\n" + "P"
    md_to_html(body1)
    md_to_html(body2)
    assert md_to_html_cache_stats()["hits"] == 1


def test_normalize_markdown_runs_inside_uncached():
    """Smoke: the normalisation step still fires — output contains
    the expected <p> wrapper."""
    out = _md_to_html_uncached("Plain text.\n")
    assert "<p>Plain text.</p>" in out


# ─── #417 — md_to_plain_text caching + perf ──────────────────────────


def test_plain_cache_returns_identical_output():
    from llmwiki.build import md_to_plain_text
    body = "# Title\n\nA paragraph with [a link](url) and **bold**.\n"
    first = md_to_plain_text(body)
    second = md_to_plain_text(body)
    assert first == second


def test_plain_cache_hits_counted():
    from llmwiki.build import md_to_plain_text
    body = "# Hi"
    md_to_plain_text(body)
    md_to_plain_text(body)
    md_to_plain_text(body)
    stats = md_to_html_cache_stats()
    assert stats["plain_hits"] == 2
    assert stats["plain_misses"] == 1


def test_plain_cache_independent_from_html_cache():
    """Calling md_to_html doesn't populate plain cache (different output)."""
    from llmwiki.build import md_to_plain_text
    md_to_html("# A")
    stats = md_to_html_cache_stats()
    assert stats["plain_size"] == 0
    md_to_plain_text("# A")
    stats = md_to_html_cache_stats()
    assert stats["plain_size"] == 1


def test_plain_cache_is_content_keyed():
    """Identical bodies → same cache key (per #417 unified _content_key)."""
    from llmwiki.build import md_to_plain_text
    md_to_plain_text("# A\n\nbody")
    md_to_plain_text("# A" + "\n\n" + "body")
    stats = md_to_html_cache_stats()
    assert stats["plain_hits"] == 1


def test_plain_cache_handles_empty_body():
    from llmwiki.build import md_to_plain_text
    out = md_to_plain_text("")
    # Empty body is cacheable too — just produces empty string after strip.
    assert md_to_plain_text("") == out
    assert md_to_html_cache_stats()["plain_hits"] == 1


def test_blake2b_cache_keys_distinct_for_one_byte_diff():
    """Regression for #417: 8-byte blake2b digest still distinguishes
    bodies that differ by a single byte. (Birthday-collision bound at
    ~4×10^9 entries; the 4096-entry cap keeps us safe.)"""
    from llmwiki.build import _content_key
    assert _content_key("hello") != _content_key("hellp")
    assert _content_key("# A") != _content_key("# B")
    assert _content_key("") != _content_key(" ")


def test_blake2b_key_is_8_bytes():
    """Pin the digest size — anything larger wastes memory, anything
    smaller is collision-prone at scale."""
    from llmwiki.build import _content_key
    assert len(_content_key("any body")) == 8


def test_plain_cache_eviction_at_max():
    """FIFO eviction works for the plain cache too (#417)."""
    from llmwiki.build import md_to_plain_text, _MD_CACHE_MAX
    # Fill the cache one over the cap.
    for i in range(_MD_CACHE_MAX + 5):
        md_to_plain_text(f"body {i}")
    # Size should be capped, not unbounded.
    stats = md_to_html_cache_stats()
    assert stats["plain_size"] <= _MD_CACHE_MAX


def test_md_html_and_plain_share_lifecycle():
    """Clearing the cache resets both html + plain counters (#417)."""
    from llmwiki.build import md_to_plain_text
    md_to_html("# A")
    md_to_plain_text("# A")
    md_to_html_cache_clear()
    stats = md_to_html_cache_stats()
    assert stats["size"] == 0
    assert stats["plain_size"] == 0
