"""#471: derive_description extracts a 120-char human-readable summary
from the first non-trivial user turn in a session.

Edge cases covered:

  - Empty / no-user-turn sessions return "".
  - Trivial openers ("hi", "thanks", "continue") get skipped — pick
    the next non-trivial line instead.
  - Path-noise prefixes (`/Users/x/...`) get stripped before truncation.
  - Code-fence opens (```) get skipped.
  - Long lines truncate at a word boundary with "...".
  - Output is always passed through the Redactor.
  - The frontmatter field gets emitted by render_session_markdown.
"""
from __future__ import annotations

from llmwiki.convert import Redactor, derive_description, render_session_markdown
from pathlib import Path


# ─── helpers ──────────────────────────────────────────────────────────


def _u(text: str) -> dict:
    """Build a minimal user-turn record."""
    return {"type": "user", "message": {"role": "user", "content": text}}


def _u_blocks(blocks: list[dict]) -> dict:
    return {"type": "user", "message": {"role": "user", "content": blocks}}


def _redactor() -> Redactor:
    return Redactor({"redaction": {"real_username": "", "extra_patterns": []}})


# ─── derive_description ───────────────────────────────────────────────


def test_returns_first_user_line() -> None:
    records = [_u("Refactor the auth middleware to use JWT cookies.")]
    assert derive_description(records, _redactor()) == \
        "Refactor the auth middleware to use JWT cookies."


def test_empty_records_returns_empty_string() -> None:
    assert derive_description([], _redactor()) == ""


def test_no_user_turn_returns_empty_string() -> None:
    records = [{"type": "assistant", "message": {"content": "ack"}}]
    assert derive_description(records, _redactor()) == ""


def test_skips_trivial_opener_picks_next_line() -> None:
    records = [_u("hi\nactually, let's debug the failing migration test")]
    out = derive_description(records, _redactor())
    assert "debug the failing migration" in out
    assert out.lower() != "hi"


def test_skips_code_fence_opener() -> None:
    records = [_u("```python\ndef foo():\n    pass\n```\nReview this code.")]
    # First non-fence non-empty line is `def foo():`. We accept either
    # that (line-by-line walk pre-fence-open) or "Review this code."
    out = derive_description(records, _redactor())
    assert out, "should derive something"
    assert "```" not in out


def test_strips_path_prefix_noise() -> None:
    records = [_u("/Users/alice/work/proj/src/auth.py needs a JWT cookie path")]
    out = derive_description(records, _redactor())
    assert out.startswith("auth.py needs a JWT cookie path") or "JWT cookie" in out
    assert "/Users/alice" not in out


def test_truncates_at_word_boundary_around_120_chars() -> None:
    long = (
        "We need to refactor the authentication middleware so that the "
        "JWT cookie path is configurable per-tenant and survives the "
        "session-revocation pass without breaking the existing token "
        "rotation policy that mobile clients depend on."
    )
    records = [_u(long)]
    out = derive_description(records, _redactor())
    assert len(out) <= 124  # 120 + "..." headroom
    assert out.endswith("...")
    # No mid-word truncation (last word should be whole).
    assert " " in out


def test_handles_content_as_block_list() -> None:
    """Records sometimes carry content as a [{type:text, text:...}] list."""
    records = [_u_blocks([{"type": "text", "text": "Block-form prompt content"}])]
    assert derive_description(records, _redactor()) == "Block-form prompt content"


def test_passes_output_through_redactor() -> None:
    """Real_username in the prompt must be redacted in the description."""
    red = Redactor({"redaction": {"real_username": "alice", "extra_patterns": []}})
    records = [_u("Run the test suite under /Users/alice/proj")]
    out = derive_description(records, red)
    assert "alice" not in out


# ─── render_session_markdown emits the field ──────────────────────────


def test_render_session_markdown_emits_description_field() -> None:
    records = [
        _u("Refactor the auth middleware to use JWT cookies."),
        {"type": "assistant", "message": {"content": "ok"}},
    ]
    md, slug, started = render_session_markdown(
        records=records,
        jsonl_path=Path("/tmp/dummy.jsonl"),
        project_slug="demo",
        redact=_redactor(),
        config={},
        is_subagent_file=False,
        adapter_name="claude_code",
    )
    assert 'description: "' in md
    assert "Refactor the auth middleware" in md


def test_render_session_markdown_emits_empty_description_for_no_user_turn() -> None:
    records = [{"type": "assistant", "message": {"content": "ack"}}]
    md, _slug, _started = render_session_markdown(
        records=records,
        jsonl_path=Path("/tmp/dummy.jsonl"),
        project_slug="demo",
        redact=_redactor(),
        config={},
        is_subagent_file=False,
        adapter_name="claude_code",
    )
    assert 'description: ""' in md
