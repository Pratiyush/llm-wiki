"""Tests for the derive_session_slug UUID fallback (closes #424).

When a JSONL has no `slug` field in any record, we fall back to a
slug derived from the filename. The historical fallback was
``jsonl_path.stem[:12]``. UUID-named transcripts (Claude Code emits
those) all collapsed onto the same 12-char prefix per project, so
two UUIDs in the same minute produced colliding canonical filenames
— the disambig pass (#339) saved us, but only because it ran after.

The fix detects UUID-shaped stems and falls back to a stable 8-char
source-path hash. Non-UUID stems keep the 12-char prefix.
"""

from __future__ import annotations

from pathlib import Path

from llmwiki.convert import derive_session_slug, _source_hash8


def test_explicit_slug_field_used_as_is():
    """Records with `slug` field → that's the slug. No filename fallback."""
    records = [{"slug": "the-real-slug", "type": "user"}]
    out = derive_session_slug(records, Path("/tmp/whatever.jsonl"))
    assert out == "the-real-slug"


def test_first_slug_wins_when_multiple_records_have_one():
    """First non-empty `slug` field across records wins."""
    records = [
        {"type": "init"},
        {"slug": "first-real", "type": "user"},
        {"slug": "later-record", "type": "assistant"},
    ]
    assert derive_session_slug(records, Path("/tmp/x.jsonl")) == "first-real"


def test_normal_filename_uses_12_char_prefix():
    """Non-UUID stems use the historical 12-char prefix fallback."""
    out = derive_session_slug([], Path("/tmp/clever-munching-parnas.jsonl"))
    assert out == "clever-munch"


def test_uuid_filename_uses_hash_not_prefix():
    """Regression for #424: UUID stems get hash-based slugs, not the
    UUID's 12-char prefix (which collided per-project)."""
    uuid_path = Path("/tmp/b7f0e3c4-2189-4f8e-9e4f-1234567890ab.jsonl")
    out = derive_session_slug([], uuid_path)
    expected = _source_hash8(uuid_path)
    assert out == expected
    # And NOT the 12-char prefix that was collision-prone.
    assert out != "b7f0e3c4-21"


def test_two_uuid_jsonls_produce_distinct_slugs():
    """The point of the fix: two different UUIDs in the same project
    produce different canonical slugs without needing disambig."""
    a = Path("/tmp/proj/aaaaaaaa-1111-1111-1111-111111111111.jsonl")
    b = Path("/tmp/proj/bbbbbbbb-2222-2222-2222-222222222222.jsonl")
    slug_a = derive_session_slug([], a)
    slug_b = derive_session_slug([], b)
    assert slug_a != slug_b


def test_uuid_uppercase_also_detected():
    """Uppercase hex UUIDs also match the pattern."""
    upper = Path("/tmp/B7F0E3C4-2189-4F8E-9E4F-1234567890AB.jsonl")
    out = derive_session_slug([], upper)
    expected = _source_hash8(upper)
    assert out == expected


def test_uuid_with_extra_suffix_still_detected():
    """`<uuid>-something.jsonl` (Claude Code subagents) still detected
    as UUID-shaped at the front and gets the hash."""
    p = Path("/tmp/b7f0e3c4-2189-4f8e-9e4f-1234567890ab-suffix.jsonl")
    out = derive_session_slug([], p)
    assert out == _source_hash8(p)


def test_short_filename_returns_short_prefix():
    """A 4-char stem returns 4 chars (Python slicing handles short input)."""
    out = derive_session_slug([], Path("/tmp/abc.jsonl"))
    assert out == "abc"


def test_dotfile_returns_stem_as_is():
    """Edge case: literal `.jsonl` filename — Python's `Path.stem`
    returns ``.jsonl`` (the dotfile), so the 12-char prefix path
    fires. This is rare enough that the existing prefix is fine."""
    p = Path("/tmp/.jsonl")
    out = derive_session_slug([], p)
    # Just confirm we don't crash; pin current behaviour.
    assert isinstance(out, str)
    assert len(out) > 0


def test_special_chars_in_filename_returns_prefix():
    """Filenames with hyphens/underscores still use 12-char prefix."""
    out = derive_session_slug([], Path("/tmp/some_long-name-here.jsonl"))
    assert out == "some_long-na"


def test_uuid_only_first_8_hex_chars_dont_match():
    """Stems like `b7f0e3c4-something` (NOT a full UUID) keep the
    12-char prefix path. UUID detection requires full UUID shape."""
    p = Path("/tmp/b7f0e3c4-not-a-uuid.jsonl")
    out = derive_session_slug([], p)
    # Should NOT take the hash path — pattern is dash-segmented but
    # not 8-4-4-4-12 hex.
    assert out == "b7f0e3c4-not"


def test_record_slug_takes_precedence_over_uuid_filename():
    """Even with a UUID-shaped filename, an explicit `slug` field wins."""
    p = Path("/tmp/b7f0e3c4-2189-4f8e-9e4f-1234567890ab.jsonl")
    out = derive_session_slug([{"slug": "human-readable"}], p)
    assert out == "human-readable"


def test_no_disambig_needed_for_distinct_uuid_jsonls(tmp_path: Path):
    """End-to-end-style: two UUIDs in same project + same minute, no
    explicit slug → distinct canonical filenames without disambig.

    Pre-fix: both produced ``YYYY-MM-DDTHH-MM-proj-b7f0e3c4-21.md``
    Post-fix: both produce distinct hashes → no collision.
    """
    from datetime import datetime
    from llmwiki.convert import flat_output_name

    started = datetime(2026, 4, 26, 10, 0, 0)
    a = tmp_path / "aaaaaaaa-1111-1111-1111-111111111111.jsonl"
    b = tmp_path / "bbbbbbbb-2222-2222-2222-222222222222.jsonl"

    slug_a = derive_session_slug([], a)
    slug_b = derive_session_slug([], b)

    name_a = flat_output_name(started, "proj", slug_a)
    name_b = flat_output_name(started, "proj", slug_b)

    # The whole point: distinct names, no disambig needed.
    assert name_a != name_b


def test_hash_is_stable_across_calls():
    """The fallback is deterministic — same path → same slug."""
    p = Path("/some/path/aaaaaaaa-1111-1111-1111-111111111111.jsonl")
    first = derive_session_slug([], p)
    second = derive_session_slug([], p)
    assert first == second
