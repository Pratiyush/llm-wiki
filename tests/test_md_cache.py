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
    assert stats == {"hits": 0, "misses": 0, "size": 0}


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
