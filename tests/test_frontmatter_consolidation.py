"""Tests for #495 — frontmatter parsers consolidated onto _frontmatter.py.

The bug: lint/__init__.py, models_page.py, and tags.py each had their
own LF-only regex parser. After #409 (BOM strip) and #423 (CRLF
support) landed in the canonical _frontmatter.py, the three local
copies diverged — every Windows-authored or BOM-prefixed wiki page
silently parsed as zero frontmatter.

The fix: all three import the canonical parser as a thin wrapper.
"""

from __future__ import annotations

import pytest

from llmwiki._frontmatter import parse_frontmatter as canonical
from llmwiki.lint import parse_frontmatter as lint_parse
from llmwiki.models_page import _parse_frontmatter as models_parse
from llmwiki.tags import _parse_frontmatter as tags_parse


def _make(content_body: str, line_ending: str = "\n", bom: bool = False) -> str:
    raw = (
        f'---{line_ending}'
        f'title: "Foo"{line_ending}'
        f'type: entity{line_ending}'
        f'---{line_ending}'
        f'{content_body}'
    )
    return ("\ufeff" if bom else "") + raw


def test_lint_parser_sees_crlf_frontmatter():
    """The original bug: lint silently skipped CRLF files."""
    text = _make("body content", line_ending="\r\n")
    meta = lint_parse(text)
    assert meta.get("title") == "Foo"
    assert meta.get("type") == "entity"


def test_lint_parser_sees_bom_prefixed_frontmatter():
    text = _make("body content", line_ending="\n", bom=True)
    meta = lint_parse(text)
    assert meta.get("title") == "Foo"


def test_models_parser_returns_canonical_shape():
    """models_page._parse_frontmatter must return (meta, body)."""
    text = _make("the body", line_ending="\r\n", bom=True)
    meta, body = models_parse(text)
    assert meta.get("title") == "Foo"
    assert "the body" in body


def test_tags_parser_returns_optional_str_shape():
    """tags._parse_frontmatter is the parse_frontmatter_or_none variant."""
    text = _make("body", line_ending="\r\n", bom=True)
    fm, body = tags_parse(text)
    assert fm is not None
    assert "title:" in fm
    assert body == "body"


def test_all_three_entry_points_agree_with_canonical():
    """Identical input through every entry point must produce
    identical metadata."""
    for line_ending in ("\n", "\r\n"):
        for bom in (False, True):
            text = _make("body", line_ending=line_ending, bom=bom)
            canon_meta, _ = canonical(text)
            lint_meta = lint_parse(text)
            models_meta, _ = models_parse(text)
            assert canon_meta.get("title") == lint_meta.get("title") == models_meta.get("title"), (
                f"divergence at line_ending={line_ending!r} bom={bom}: "
                f"canonical={canon_meta} lint={lint_meta} models={models_meta}"
            )
            assert canon_meta.get("type") == lint_meta.get("type") == models_meta.get("type")
