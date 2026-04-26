"""Tests for #492 — renderer must read `is_subagent` frontmatter, not
re-implement the old broken substring rule.

The bug: PR #406 fixed `is_subagent` at the adapter layer (strict
canonical-path check, writes correct `is_subagent: true|false` into
frontmatter). But `build.py` never read the frontmatter field; it
re-implemented the old `'subagent' in p.name` substring check in 5
separate places. Any session in any project with "subagent" in its
filename was misclassified in the rendered UI.

The fix: new `_is_subagent(meta, path)` helper that prefers the
frontmatter field, falls back to the substring check only when the
field is missing (back-compat for pre-#406 raw files).
"""

from __future__ import annotations

from pathlib import Path

from llmwiki.build import _is_subagent


def test_explicit_true_returns_true():
    assert _is_subagent({"is_subagent": True}, Path("anything.md")) is True


def test_explicit_false_returns_false_even_when_path_says_otherwise():
    """Critical regression: a session in a project named `subagent-runner`
    whose filename contains 'subagent' must NOT be classified as a
    sub-agent if the adapter wrote `is_subagent: false` (PR #406)."""
    assert _is_subagent(
        {"is_subagent": False},
        Path("2026-04-25-subagent-runner-rewrite.md"),
    ) is False


def test_string_true_variants_coerce_to_true():
    for s in ("true", "True", "TRUE", "yes", "1"):
        assert _is_subagent({"is_subagent": s}, Path("x.md")) is True, s


def test_string_false_variants_coerce_to_false():
    for s in ("false", "False", "FALSE", "no", "0"):
        assert _is_subagent({"is_subagent": s}, Path("x.md")) is False, s


def test_missing_field_falls_back_to_substring():
    """Pre-#406 raw files won't have the field — keep the substring
    fallback for back-compat. Re-syncing those files restores the
    correct classification."""
    assert _is_subagent({}, Path("session-subagent-abc.md")) is True
    assert _is_subagent({}, Path("session-foo.md")) is False


def test_unrecognised_string_falls_back_to_substring():
    assert _is_subagent({"is_subagent": "maybe"}, Path("x.md")) is False
    assert _is_subagent({"is_subagent": "maybe"}, Path("subagent-x.md")) is True


def test_none_value_falls_back_to_substring():
    assert _is_subagent({"is_subagent": None}, Path("subagent-x.md")) is True
    assert _is_subagent({"is_subagent": None}, Path("foo.md")) is False


def test_int_value_falls_back_to_substring():
    """`is_subagent: 5` is nonsense — falls through to substring rule."""
    assert _is_subagent({"is_subagent": 5}, Path("foo.md")) is False
    assert _is_subagent({"is_subagent": 5}, Path("subagent-x.md")) is True
