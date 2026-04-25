"""Tests for the canonical frontmatter parser (#273)."""

from __future__ import annotations

import pytest

from llmwiki._frontmatter import (
    parse_frontmatter,
    parse_frontmatter_dict,
    parse_frontmatter_or_none,
    _parse_scalar,
)


# ─── parse_frontmatter: happy paths ──────────────────────────────────


def test_parses_basic_frontmatter():
    text = '---\ntitle: "Example"\ntype: entity\n---\n\nBody.\n'
    meta, body = parse_frontmatter(text)
    assert meta["title"] == "Example"
    assert meta["type"] == "entity"
    assert body.startswith("\nBody.")


def test_handles_missing_frontmatter():
    text = "# Just body\n\nContent\n"
    meta, body = parse_frontmatter(text)
    assert meta == {}
    assert body == text


def test_empty_frontmatter_block():
    text = "---\n---\nbody\n"
    meta, body = parse_frontmatter(text)
    assert meta == {}
    assert body == "body\n"


def test_ignores_malformed_lines():
    text = "---\ntitle: X\nnot a key line\nvalid: 1\n---\n"
    meta, _ = parse_frontmatter(text)
    assert meta["title"] == "X"
    assert meta["valid"] == 1
    assert "not a key line" not in meta


# ─── _parse_scalar edge cases ────────────────────────────────────────


@pytest.mark.parametrize("raw,expected", [
    ("123", 123),
    ("-17", -17),
    ("0", 0),
    ("3.14", 3.14),
    ("true", True),
    ("True", True),
    ("yes", True),
    ("false", False),
    ("no", False),
    ("", ""),
    ('"quoted"', "quoted"),
    ("'single'", "single"),
    ("plain string", "plain string"),
    ("[]", []),
    ("[a, b, c]", ["a", "b", "c"]),
    ('["x", "y"]', ["x", "y"]),
    ("[1, 2, 3]", [1, 2, 3]),
])
def test_parse_scalar_variants(raw, expected):
    assert _parse_scalar(raw) == expected


def test_parse_scalar_whitespace_agnostic():
    assert _parse_scalar("  123  ") == 123


# ─── legacy signature wrappers ───────────────────────────────────────


def test_parse_frontmatter_dict_returns_meta_only():
    text = '---\ntitle: X\n---\nbody\n'
    assert parse_frontmatter_dict(text) == {"title": "X"}


def test_parse_frontmatter_or_none_returns_raw_text():
    text = '---\ntitle: "Ex"\ntags: [a, b]\n---\nbody\n'
    fm, body = parse_frontmatter_or_none(text)
    assert fm is not None
    assert 'title: "Ex"' in fm
    assert 'tags: [a, b]' in fm
    assert body == "body\n"


def test_parse_frontmatter_or_none_missing():
    fm, body = parse_frontmatter_or_none("no frontmatter\n")
    assert fm is None
    assert body == "no frontmatter\n"


# ─── Inline list is properly parsed ──────────────────────────────────


def test_inline_list_returns_python_list():
    text = '---\ntags: [claude-code, session-transcript]\n---\n'
    meta, _ = parse_frontmatter(text)
    assert meta["tags"] == ["claude-code", "session-transcript"]


def test_quoted_list_elements_stripped():
    text = '---\ntags: ["a b", "c d"]\n---\n'
    meta, _ = parse_frontmatter(text)
    assert meta["tags"] == ["a b", "c d"]


def test_int_and_bool_scalars_typed():
    text = '---\ncount: 42\nenabled: true\ntitle: X\n---\n'
    meta, _ = parse_frontmatter(text)
    assert meta["count"] == 42
    assert meta["enabled"] is True
    assert meta["title"] == "X"


def test_round_trip_simple_case():
    """Write a page, read it back, frontmatter round-trips."""
    text = '---\ntitle: "Round trip"\ntype: source\n---\n\n# Body\n'
    meta, body = parse_frontmatter(text)
    assert meta == {"title": "Round trip", "type": "source"}
    assert body.strip() == "# Body"


# ─── #409 / #423: line-ending + BOM handling ─────────────────────────


def test_crlf_line_endings_parsed_identically_to_lf():
    """Windows-authored files (CRLF) must parse like LF input (#409)."""
    text = '---\r\ntitle: "Win"\r\ntype: source\r\n---\r\nbody\r\n'
    meta, body = parse_frontmatter(text)
    assert meta == {"title": "Win", "type": "source"}
    assert body == "body\r\n"


def test_cr_only_line_endings_parsed():
    """Old-Mac CR-only line endings (#409 edge case)."""
    text = '---\rtitle: "OldMac"\r---\rbody\r'
    meta, body = parse_frontmatter(text)
    assert meta == {"title": "OldMac"}
    assert body == "body\r"


def test_mixed_crlf_and_lf_in_same_file():
    """Mixed line endings (e.g. file copied across platforms) (#409)."""
    text = '---\r\ntitle: A\nkey: B\r\n---\nbody\n'
    meta, _ = parse_frontmatter(text)
    assert meta == {"title": "A", "key": "B"}


def test_utf8_bom_stripped(tmp_path):
    """UTF-8 BOM at start (Notepad default) (#423)."""
    text = '\ufeff---\ntitle: "BOM"\n---\nbody\n'
    meta, body = parse_frontmatter(text)
    assert meta == {"title": "BOM"}
    assert body == "body\n"


def test_bom_plus_crlf_combination():
    """BOM + CRLF (Notepad on Windows is the worst case) (#423)."""
    text = '\ufeff---\r\ntitle: "WinBOM"\r\n---\r\nbody\r\n'
    meta, _ = parse_frontmatter(text)
    assert meta == {"title": "WinBOM"}


def test_bom_inside_file_preserved():
    """A BOM inside the body is content, not metadata (#423)."""
    text = '---\ntitle: X\n---\nbody \ufeff middle\n'
    _, body = parse_frontmatter(text)
    assert "\ufeff" in body


def test_bom_only_no_frontmatter():
    """File starts with BOM but has no frontmatter — body is the rest (#423)."""
    text = '\ufeff# Heading\n\nBody.\n'
    meta, body = parse_frontmatter(text)
    assert meta == {}
    # BOM is stripped at the parser entry, so body comes back without it
    assert body == "# Heading\n\nBody.\n"


def test_legacy_or_none_wrapper_strips_bom():
    """parse_frontmatter_or_none must also strip BOM (#423)."""
    text = '\ufeff---\ntitle: X\n---\nbody\n'
    fm, body = parse_frontmatter_or_none(text)
    assert fm is not None
    assert "title: X" in fm
    assert body == "body\n"


# ─── #409 — build.py must use the same parser ────────────────────────


def test_build_py_parse_frontmatter_is_canonical():
    """`build.py:parse_frontmatter` must be the canonical one — not a
    divergent copy. Regression for #409: divergent regexes silently
    dropped CRLF input on the build-side parser only.
    """
    from llmwiki.build import parse_frontmatter as build_pf
    from llmwiki._frontmatter import parse_frontmatter as canonical_pf
    assert build_pf is canonical_pf


def test_build_py_parses_crlf_now():
    """Regression for #409: build.py used to fail on CRLF and silently
    return ``({}, text)`` for any Windows-authored ``wiki/projects/*.md``.
    """
    from llmwiki.build import parse_frontmatter
    text = '---\r\nproject: my-proj\r\ntopics: [a, b]\r\n---\r\nbody\r\n'
    meta, _ = parse_frontmatter(text)
    assert meta["project"] == "my-proj"
    assert meta["topics"] == ["a", "b"]


def test_build_py_parses_bom_now():
    """Regression for #423: BOM-prefixed files used to silently lose
    frontmatter on the build path, leaving project pages headerless.
    """
    from llmwiki.build import parse_frontmatter
    text = '\ufeff---\ntitle: "BOM Project"\n---\nbody\n'
    meta, _ = parse_frontmatter(text)
    assert meta == {"title": "BOM Project"}


def test_build_py_parses_inline_list_with_quoted_values():
    """Regression for #409: build.py's old list parser didn't unquote
    list elements, so `topics: ["a, b", c]` came back as
    `['"a', 'b"', 'c']` instead of `["a, b", "c"]`. Note: even the new
    canonical parser splits naively on ',' so quoted commas become
    distinct elements — this test pins current behaviour rather than
    aspirational quoted-comma support.
    """
    from llmwiki.build import parse_frontmatter
    text = '---\ntopics: ["foo", "bar"]\n---\n'
    meta, _ = parse_frontmatter(text)
    assert meta["topics"] == ["foo", "bar"]


# ─── #409 / #423: end-to-end via discover_sources ────────────────────


def test_discover_sources_reads_crlf_file(tmp_path, monkeypatch):
    """E2E: a Windows-authored file under raw/ must surface its
    frontmatter through ``discover_sources`` (#409 acceptance)."""
    from llmwiki import build as build_mod

    raw = tmp_path / "raw"
    sessions = raw / "sessions" / "my-proj"
    sessions.mkdir(parents=True)
    text = '---\r\ntitle: "CRLF"\r\nproject: my-proj\r\nslug: crlf-test\r\n---\r\n# CRLF body\r\n'
    (sessions / "2026-04-26T10-00-my-proj-crlf.md").write_bytes(text.encode("utf-8"))

    found = build_mod.discover_sources(sessions)
    assert len(found) == 1
    _, meta, body = found[0]
    assert meta.get("title") == "CRLF"
    assert meta["project"] == "my-proj"
    assert meta["slug"] == "crlf-test"


def test_discover_sources_reads_bom_file(tmp_path):
    """E2E: a Notepad-authored (BOM + CRLF) file surfaces its frontmatter
    instead of falling back to the parent dir name (#423 acceptance).
    """
    from llmwiki import build as build_mod

    sessions = tmp_path / "raw" / "sessions" / "bom-proj"
    sessions.mkdir(parents=True)
    text = '\ufeff---\r\ntitle: "Notepad"\r\nproject: bom-proj\r\n---\r\nbody\r\n'
    (sessions / "2026-04-26T10-00-bom-proj-x.md").write_bytes(text.encode("utf-8"))

    found = build_mod.discover_sources(sessions)
    assert len(found) == 1
    _, meta, _ = found[0]
    assert meta.get("title") == "Notepad"
    assert meta["project"] == "bom-proj"
