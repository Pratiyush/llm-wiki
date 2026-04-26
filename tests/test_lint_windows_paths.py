"""Tests for #490 — lint helpers must handle both POSIX and Windows
path separators.

The bug: `rel.rsplit('/', 1)[-1]` returns the WHOLE string when the
path uses backslashes (i.e. on Windows where `Path.parts` yields
native separators). Every navigation file fell out of the
exemption set; every Windows install spammed spurious lint errors.

The fix: a `_basename(rel)` helper that normalises both separators
before splitting. All callsites route through it.
"""

from __future__ import annotations

import pytest

from llmwiki.lint.rules import _basename, _page_slug, FrontmatterCompleteness


@pytest.mark.parametrize("rel,expected", [
    ("wiki/index.md", "index.md"),
    ("wiki\\index.md", "index.md"),
    ("entities/Foo.md", "Foo.md"),
    ("entities\\Foo.md", "Foo.md"),
    ("a/b/c/deep.md", "deep.md"),
    ("a\\b\\c\\deep.md", "deep.md"),
    ("a/b\\c/mixed.md", "mixed.md"),
    ("noslash.md", "noslash.md"),
])
def test_basename_handles_both_separators(rel: str, expected: str):
    assert _basename(rel) == expected


@pytest.mark.parametrize("rel,expected_slug", [
    ("entities/Foo.md", "Foo"),
    ("entities\\Foo.md", "Foo"),
    ("Bar.md", "Bar"),
])
def test_page_slug_strips_extension_after_basename(rel: str, expected_slug: str):
    assert _page_slug(rel) == expected_slug


def test_frontmatter_completeness_exempts_windows_index_path():
    """Regression for the original bug: a Windows page key like
    `wiki\\index.md` must hit the EXEMPT_FILES set instead of being
    linted as missing-frontmatter."""
    rule = FrontmatterCompleteness()
    pages = {
        "wiki\\index.md": {"meta": {}, "body": "# Index"},
        "wiki\\overview.md": {"meta": {}, "body": "# Overview"},
    }
    issues = rule.run(pages)
    assert issues == [], (
        f"Windows nav paths still leaking lint errors: {issues}"
    )


def test_frontmatter_completeness_still_lints_windows_real_pages():
    """Sanity: the helper doesn't accidentally exempt non-nav pages
    just because the path uses backslashes."""
    rule = FrontmatterCompleteness()
    pages = {
        "wiki\\entities\\NewEntity.md": {
            "meta": {},
            "body": "Some body",
        },
    }
    issues = rule.run(pages)
    assert any(
        issue.get("page", "").endswith("NewEntity.md")
        for issue in issues
    ), f"expected lint error on NewEntity.md (Windows path), got {issues}"
