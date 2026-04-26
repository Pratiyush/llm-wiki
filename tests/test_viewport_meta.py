"""Tests for #481 — viewport meta tag must include `viewport-fit=cover`.

Without `viewport-fit=cover`, iOS Safari does NOT expose safe-area inset
values to CSS (`env(safe-area-inset-bottom)` returns 0). The mobile
bottom nav at `render/css.py:673` relies on that inset to clear the
iPhone home indicator. Missing it = bottom nav buttons sit under the
swipe-up gesture region and become un-tappable.

Both viewport meta tags emitted by `build.py` (the regular page head
and the article-style page head) must carry the directive.
"""

from __future__ import annotations

import re

from llmwiki.build import page_head, page_head_article


_VIEWPORT_RE = re.compile(r'<meta name="viewport" content="([^"]+)">')


def test_page_head_viewport_meta_has_viewport_fit_cover():
    head = page_head("Test", "")
    m = _VIEWPORT_RE.search(head)
    assert m, f"no viewport meta tag in page_head output:\n{head[:500]}"
    content = m.group(1)
    assert "viewport-fit=cover" in content, (
        f"page_head viewport missing viewport-fit=cover: {content!r}"
    )


def test_page_head_article_viewport_meta_has_viewport_fit_cover():
    head = page_head_article("Test", description="x")
    m = _VIEWPORT_RE.search(head)
    assert m, f"no viewport meta tag in page_head_article output:\n{head[:500]}"
    content = m.group(1)
    assert "viewport-fit=cover" in content, (
        f"page_head_article viewport missing viewport-fit=cover: {content!r}"
    )


def test_viewport_meta_keeps_legacy_directives():
    """Don't regress the existing width + initial-scale parts."""
    for head in (page_head("T", ""), page_head_article("T", description="x")):
        m = _VIEWPORT_RE.search(head)
        assert m
        content = m.group(1)
        assert "width=device-width" in content
        assert "initial-scale=1" in content
