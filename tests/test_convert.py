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


# ─── #419: tilde-fence handling ──────────────────────────────────────


def test_truncate_chars_closes_open_tilde_fence():
    """~~~python\\ncode...  → must auto-close with ~~~ (#419)."""
    src = "~~~python\n" + "x = 1\n" * 50
    out = truncate_chars(src, 30)
    tildes = [ln for ln in out.splitlines() if ln.lstrip().startswith("~~~")]
    assert len(tildes) % 2 == 0
    assert len(tildes) >= 2  # opener + auto-close
    assert "truncated" in out


def test_truncate_lines_closes_open_tilde_fence():
    src = "~~~\nroot/\n├── a\n├── b\n├── c\n├── d\n"
    out = truncate_lines(src, 3)
    tildes = [ln for ln in out.splitlines() if ln.lstrip().startswith("~~~")]
    assert len(tildes) % 2 == 0
    assert "truncated" in out


def test_truncate_chars_balanced_tilde_unchanged():
    """Already-balanced ~~~ pair: no phantom close added."""
    src = "~~~\nshort\n~~~\nmore text past the budget that's longer"
    out = truncate_chars(src, 25)
    tildes = [ln for ln in out.splitlines() if ln.lstrip().startswith("~~~")]
    assert len(tildes) == 2


def test_truncate_chars_mixed_fences_both_closed():
    """One unclosed ``` + one unclosed ~~~ → both get their own close."""
    src = "```js\nconsole.log()\n~~~python\nprint('x')\n" + "more " * 50
    out = truncate_chars(src, 80)
    backticks = [ln for ln in out.splitlines() if ln.lstrip().startswith("```")]
    tildes = [ln for ln in out.splitlines() if ln.lstrip().startswith("~~~")]
    assert len(backticks) % 2 == 0, f"backtick count odd: {backticks}"
    assert len(tildes) % 2 == 0, f"tilde count odd: {tildes}"


def test_truncate_chars_one_fence_style_doesnt_mask_other():
    """Pre-fix bug: counting both fence types together let one even out
    the other's odd count, so the wrong type was appended."""
    # 1 unclosed ~~~ alone — must close with ~~~, NOT ```
    src = "~~~python\ncode\n" + "x " * 100
    out = truncate_chars(src, 30)
    # Last non-truncation-marker fence-line should be ~~~
    fence_lines = [
        ln for ln in out.splitlines()
        if ln.lstrip().startswith(("```", "~~~"))
    ]
    assert fence_lines, "no fences found in output"
    assert all("~~~" in ln or "```python" in ln for ln in fence_lines), (
        f"unexpected fence type appended: {fence_lines}"
    )
    # The closing fence should be tilde, not backtick.
    last_fence = fence_lines[-1]
    assert last_fence.lstrip() == "~~~", (
        f"closing fence should be ~~~, got: {last_fence!r}"
    )


def test_truncate_chars_indented_fence():
    """Indented fences (e.g. inside list items) still count."""
    src = "- item\n  ```python\n  x = 1\n  y = 2\n  z = 3\n"
    out = truncate_chars(src, 25)
    backticks = [ln for ln in out.splitlines() if ln.lstrip().startswith("```")]
    assert len(backticks) % 2 == 0


def test_close_open_fence_unit_tilde_only():
    """Direct unit test for the helper — odd ~~~ count gets ~~~ close."""
    from llmwiki.convert import _close_open_fence
    text = "~~~python\ncode here\n"
    out = _close_open_fence(text)
    assert out.endswith("~~~")
    assert out.count("~~~") == 2


def test_close_open_fence_unit_balanced_no_change():
    """Even count of either fence type: no change."""
    from llmwiki.convert import _close_open_fence
    text = "```\nfoo\n```\n~~~\nbar\n~~~\n"
    assert _close_open_fence(text) == text


def test_close_open_fence_unit_both_unclosed():
    """One ``` open + one ~~~ open → both get appended."""
    from llmwiki.convert import _close_open_fence
    text = "```js\nconst x = 1\n~~~python\nprint('y')\n"
    out = _close_open_fence(text)
    # Both styles are now even.
    assert out.count("```") == 2
    assert out.count("~~~") == 2


def test_close_open_fence_unit_no_fences():
    """Plain text — no fences added."""
    from llmwiki.convert import _close_open_fence
    text = "just plain text\nwith no fences\n"
    assert _close_open_fence(text) == text


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


# ─── #416: Windows / WSL / token redaction ──────────────────────────


def _user_redactor(username: str = "alice", replacement: str = "USER") -> Redactor:
    return Redactor({
        "redaction": {
            "real_username": username,
            "replacement_username": replacement,
            "extra_patterns": [],
        }
    })


def test_redactor_windows_path_backslash():
    """Windows: `C:\\Users\\alice\\Desktop\\...` → redacted (#416)."""
    r = _user_redactor()
    out = r(r"C:\Users\alice\Desktop\code\file.py")
    assert "alice" not in out
    assert r"C:\Users\USER\Desktop\code\file.py" == out


def test_redactor_windows_path_mixed_separators():
    """Windows: mixed `C:\\Users/alice/...` (copy-paste between shells)."""
    r = _user_redactor()
    out = r(r"C:/Users/alice/Documents/x.txt")
    assert "alice" not in out
    assert "C:/Users/USER/Documents/x.txt" == out


def test_redactor_wsl_path():
    """WSL: `/mnt/c/Users/alice/...` → redacted."""
    r = _user_redactor()
    out = r("/mnt/c/Users/alice/code/repo/file.py")
    assert "alice" not in out
    assert "/mnt/c/Users/USER/code/repo/file.py" == out


def test_redactor_wsl_path_d_drive():
    """WSL: `/mnt/d/Users/alice/...` (any drive letter) → redacted."""
    r = _user_redactor()
    out = r("/mnt/d/Users/alice/work/file.py")
    assert "/mnt/d/Users/USER/work/file.py" == out


def test_redactor_macos_path_still_works():
    """Regression: macOS path still redacts after the regex rewrite."""
    r = _user_redactor()
    assert r("/Users/alice/Desktop/x") == "/Users/USER/Desktop/x"


def test_redactor_linux_path_still_works():
    """Regression: Linux path still redacts after the regex rewrite."""
    r = _user_redactor()
    assert r("/home/alice/code/x") == "/home/USER/code/x"


def test_redactor_username_substring_safe():
    """Username `alice` must NOT match `aliceandbob` (boundary respected)."""
    r = _user_redactor("alice")
    text = "/Users/aliceandbob/code"
    out = r(text)
    # `aliceandbob` should be left alone since it's not the user.
    assert out == text


def test_redactor_username_with_hyphens():
    """Usernames with hyphens are valid and must be matched."""
    r = _user_redactor("alice-smith")
    out = r("/Users/alice-smith/code")
    assert out == "/Users/USER/code"


def test_redactor_username_with_underscores():
    r = _user_redactor("alice_smith")
    out = r("/home/alice_smith/code")
    assert out == "/home/USER/code"


def test_redactor_username_unicode():
    """Unicode usernames (CJK, emoji-prefix) round-trip."""
    r = _user_redactor("aliceé")
    out = r("/Users/aliceé/code")
    assert "aliceé" not in out


def test_redactor_network_drive_no_false_redaction():
    """`\\\\server\\share\\...` (UNC path) must not be touched."""
    r = _user_redactor("alice")
    text = r"\\server\share\public\file.txt"
    assert r(text) == text  # no `Users\\alice` segment, no change


# Token-shape fixtures are built via string concatenation so the
# literal text never appears in the source — that keeps GitHub's
# secret-scanner from flagging the test file itself as a leaked secret.
# These are obvious test patterns (all-A's, sequential digits) chosen
# to match the regex shape without resembling any real credential.

def _ghp(suffix: str = "A" * 36) -> str:
    return "g" + "h" + "p_" + suffix

def _gho(suffix: str = "A" * 36) -> str:
    return "g" + "h" + "o_" + suffix

def _ghs(suffix: str = "A" * 36) -> str:
    return "g" + "h" + "s_" + suffix

def _ghu(suffix: str = "A" * 36) -> str:
    return "g" + "h" + "u_" + suffix

def _github_pat(suffix: str = "A" * 36) -> str:
    return "g" + "ithub_" + "pat_" + suffix

def _akia(suffix: str = "A" * 16) -> str:
    return "AK" + "IA" + suffix

def _xox(letter: str = "b", suffix: str = "1234567890-abc") -> str:
    return "x" + "ox" + letter + "-" + suffix


def test_redactor_github_pat_classic():
    """GitHub classic PAT (ghp_*) is redacted by default (#416)."""
    r = Redactor({})
    token = _ghp()
    out = r(f"token={token}")
    assert token not in out
    assert "<REDACTED>" in out


def test_redactor_github_oauth_token():
    """GitHub OAuth (gho_*) is redacted."""
    r = Redactor({})
    token = _gho()
    out = r(f"Authorization: token {token}")
    assert token not in out


def test_redactor_github_server_to_server():
    """ghs_* → redacted."""
    r = Redactor({})
    token = _ghs()
    out = r(f"X-API-Key: {token}")
    assert token not in out


def test_redactor_github_user_to_server():
    """ghu_* → redacted."""
    r = Redactor({})
    token = _ghu()
    assert token not in r(token)


def test_redactor_github_fine_grained_pat():
    """github_pat_* → redacted."""
    r = Redactor({})
    token = _github_pat()
    out = r(f"export TOKEN={token}")
    assert token not in out


def test_redactor_aws_access_key_id():
    """AWS access key IDs (AKIA*) → redacted."""
    r = Redactor({})
    token = _akia()
    out = r(f"aws_access_key_id={token}")
    assert token not in out


def test_redactor_slack_bot_token():
    """Slack bot token (xoxb-*) → redacted."""
    r = Redactor({})
    token = _xox("b")
    out = r(f"Bearer {token}")
    assert token not in out


def test_redactor_slack_user_token():
    """Slack user token (xoxp-*) → redacted."""
    r = Redactor({})
    token = _xox("p")
    assert token not in r(token)


def test_redactor_does_not_mistake_short_tokens():
    """Short prefixes that don't meet the length threshold are preserved.
    Avoids false positives on docs / examples."""
    r = Redactor({})
    short = "g" + "h" + "p_short"
    out = r(short)
    assert short in out


def test_redactor_no_extra_patterns_still_redacts_tokens():
    """Token defaults run regardless of user `extra_patterns` config (#416).
    Closes the gap where users without security tooling had no protection."""
    r = Redactor({"redaction": {"real_username": "", "extra_patterns": []}})
    token = _ghp()
    out = r(token)
    assert "<REDACTED>" in out


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
