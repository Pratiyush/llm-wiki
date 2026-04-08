"""Unit tests for the converter internals (redaction, parsing, rendering)."""

from __future__ import annotations

import json
from pathlib import Path

from llmwiki.convert import (
    DEFAULT_CONFIG,
    Redactor,
    count_tool_calls,
    count_user_messages,
    extract_tools_used,
    filter_records,
    is_real_user_prompt,
    is_tool_result_delivery,
    parse_jsonl,
    render_session_markdown,
    truncate_chars,
    truncate_lines,
)

from tests.conftest import FIXTURES_DIR


def test_truncate_chars_short():
    assert truncate_chars("abc", 10) == "abc"


def test_truncate_chars_long():
    out = truncate_chars("a" * 100, 10)
    assert out.startswith("aaaaaaaaaa")
    assert "truncated" in out


def test_truncate_lines_short():
    assert truncate_lines("a\nb\nc", 10) == "a\nb\nc"


def test_truncate_lines_long():
    out = truncate_lines("a\nb\nc\nd\ne", 2)
    assert out.startswith("a\nb\n")
    assert "truncated" in out


# ─── #72: code-fence balance preservation ───────────────────────────────
# When truncate_chars / truncate_lines cuts mid-code-block, the opening
# ``` must get a matching close fence so downstream markdown parsers
# don't consume the entire rest of the page.


def test_truncate_chars_closes_open_fence():
    src = "```\nline1\nline2\nline3\nline4\nline5\nline6\nline7\n"
    out = truncate_chars(src, 20)
    # fence count in the returned text should be even (open + auto-close)
    fences = [ln for ln in out.splitlines() if ln.lstrip().startswith("```")]
    assert len(fences) % 2 == 0
    assert len(fences) >= 2  # at least the original open + one close
    assert "truncated" in out


def test_truncate_lines_closes_open_fence():
    src = "```\nroot/\n├── a\n├── b\n├── c\n├── d\n"
    out = truncate_lines(src, 3)
    fences = [ln for ln in out.splitlines() if ln.lstrip().startswith("```")]
    assert len(fences) % 2 == 0
    assert "truncated" in out


def test_truncate_chars_balanced_fence_unchanged():
    # Already balanced ``` open + close — truncation should NOT add extras.
    src = "```\nshort\n```\nmore text that pushes over the char budget"
    out = truncate_chars(src, 20)
    fences = [ln for ln in out.splitlines() if ln.lstrip().startswith("```")]
    # Only the original two fences should be present; no phantom third.
    assert len(fences) == 2


def test_truncate_chars_no_fence_no_change():
    # Plain text without any fence — no injected close.
    src = "a" * 100
    out = truncate_chars(src, 10)
    assert "```" not in out


def test_truncate_chars_fenced_lang_marker():
    # Fence with a language marker (```python) must still be detected.
    src = "```python\n" + "x = 1\n" * 50
    out = truncate_chars(src, 30)
    fences = [ln for ln in out.splitlines() if ln.lstrip().startswith("```")]
    assert len(fences) % 2 == 0


def test_redactor_username_in_path():
    config = {"redaction": {"real_username": "alice", "replacement_username": "USER", "extra_patterns": []}}
    r = Redactor(config)
    assert r("/Users/alice/foo") == "/Users/USER/foo"
    assert r("/Users/alice/") == "/Users/USER/"
    assert r("/home/alice/bar") == "/home/USER/bar"


def test_redactor_api_key():
    r = Redactor(DEFAULT_CONFIG)
    text = "export ANTHROPIC_API_KEY=sk-ant-1234567890abcdefghij"
    out = r(text)
    assert "sk-ant-1234567890abcdefghij" not in out
    assert "<REDACTED>" in out


def test_redactor_email():
    r = Redactor(DEFAULT_CONFIG)
    assert "alice@example.com" not in r("email me at alice@example.com please")


def test_filter_records_drops_noise():
    records = [
        {"type": "user", "message": {"role": "user", "content": "hi"}},
        {"type": "queue-operation"},
        {"type": "file-history-snapshot"},
        {"type": "progress"},
        {"type": "assistant", "message": {"role": "assistant", "content": []}},
    ]
    out = filter_records(records, ["queue-operation", "file-history-snapshot", "progress"])
    assert len(out) == 2
    assert out[0]["type"] == "user"
    assert out[1]["type"] == "assistant"


def test_is_real_user_prompt():
    real = {"type": "user", "message": {"role": "user", "content": "hi"}}
    tool_result = {
        "type": "user",
        "message": {
            "role": "user",
            "content": [{"type": "tool_result", "tool_use_id": "t1", "content": "ok"}],
        },
    }
    assert is_real_user_prompt(real) is True
    assert is_real_user_prompt(tool_result) is False


def test_is_tool_result_delivery():
    real = {"type": "user", "message": {"role": "user", "content": "hi"}}
    tool_result = {
        "type": "user",
        "message": {
            "role": "user",
            "content": [{"type": "tool_result", "tool_use_id": "t1", "content": "ok"}],
        },
    }
    assert is_tool_result_delivery(tool_result) is True
    assert is_tool_result_delivery(real) is False


def test_parse_jsonl_fixture():
    fx = FIXTURES_DIR / "claude_code" / "minimal.jsonl"
    assert fx.exists(), f"fixture missing: {fx}"
    records = parse_jsonl(fx)
    assert len(records) == 4
    assert records[0]["type"] == "user"
    assert records[1]["type"] == "assistant"


def test_count_user_messages_fixture():
    records = parse_jsonl(FIXTURES_DIR / "claude_code" / "minimal.jsonl")
    # 1 real user prompt (the "hello" one). The tool_result delivery doesn't count.
    assert count_user_messages(records) == 1


def test_count_tool_calls_fixture():
    records = parse_jsonl(FIXTURES_DIR / "claude_code" / "minimal.jsonl")
    assert count_tool_calls(records) == 1


def test_extract_tools_used_fixture():
    records = parse_jsonl(FIXTURES_DIR / "claude_code" / "minimal.jsonl")
    tools = extract_tools_used(records)
    assert tools == ["Bash"]


def test_render_session_markdown_fixture():
    records = parse_jsonl(FIXTURES_DIR / "claude_code" / "minimal.jsonl")
    redactor = Redactor(DEFAULT_CONFIG)
    md, slug, started = render_session_markdown(
        records,
        jsonl_path=Path("minimal.jsonl"),
        project_slug="sample-project",
        redact=redactor,
        config=DEFAULT_CONFIG,
        is_subagent_file=False,
    )
    assert slug == "tiny-fixture-alpha"
    assert started.year == 2026
    # Frontmatter
    assert "---" in md
    assert "slug: tiny-fixture-alpha" in md
    assert "project: sample-project" in md
    assert "tools_used: [Bash]" in md
    # Body
    assert "## Conversation" in md
    assert "### Turn 1 — User" in md
    assert "hello, say hi and run pwd" in md
    assert "### Turn 1 — Assistant" in md
    assert "`Bash`" in md
    # Redaction: since the fixture uses USER already, nothing to redact. Just verify structure.
    assert "/Users/USER/sample-project" in md
