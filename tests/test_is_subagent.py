"""is_subagent classification tests (#406 + #430).

Old heuristic was ``"subagent" in jsonl_path.parts or "subagent" in
jsonl_path.name`` — mis-tagged any user project containing the
substring ``subagent`` as a sub-agent run. New behaviour:

- ``BaseAdapter.is_subagent`` returns False (no adapter has the concept
  by default).
- ``ClaudeCodeAdapter.is_subagent`` returns True only for the canonical
  layout: a directory literally named ``subagents`` containing a
  filename starting with ``agent-``.

This test file is the cross-product matrix from #430.
"""

from __future__ import annotations

from pathlib import Path

import pytest


# ─── BaseAdapter default — never True ────────────────────────────────────


def test_base_adapter_default_returns_false():
    from llmwiki.adapters.base import BaseAdapter

    class _Stub(BaseAdapter):
        name = "stub"
        session_store_path = Path("/nonexistent")

    a = _Stub({})
    # All these used to be True under the old substring heuristic; now all False.
    assert a.is_subagent(Path("/tmp/subagent-runner/main.jsonl")) is False
    assert a.is_subagent(Path("/tmp/foo/subagent.jsonl")) is False
    assert a.is_subagent(Path("/tmp/foo/subagents/agent-1.jsonl")) is False
    assert a.is_subagent(Path("/tmp/foo/bar.jsonl")) is False


# ─── ClaudeCodeAdapter — canonical layout ─────────────────────────────────


def _claude_adapter():
    from llmwiki.adapters.claude_code import ClaudeCodeAdapter
    return ClaudeCodeAdapter({})


@pytest.mark.parametrize("path,expected", [
    # POSITIVE — canonical Claude Code subagent layout
    (Path("/Users/me/.claude/projects/my-proj/sess-abc/subagents/agent-prompt-1.jsonl"), True),
    (Path("/Users/me/.claude/projects/foo/X/subagents/agent-X.jsonl"), True),

    # NEGATIVE — project name contains 'subagent' (the bug from #406)
    (Path("/Users/me/.claude/projects/subagent-runner/main.jsonl"), False),
    (Path("/Users/me/.claude/projects/agent-subagent-helper/main.jsonl"), False),
    (Path("/Users/me/.claude/projects/-Users-me-Desktop-subagent-x/main.jsonl"), False),

    # NEGATIVE — 'subagents' directory but filename doesn't match
    (Path("/Users/me/.claude/projects/p/sess/subagents/main.jsonl"), False),
    (Path("/Users/me/.claude/projects/p/sess/subagents/random.jsonl"), False),

    # NEGATIVE — 'agent-' prefix but not under a 'subagents' directory
    (Path("/Users/me/.claude/projects/p/agent-runner.jsonl"), False),

    # NEGATIVE — similar-but-not-canonical directory names
    (Path("/Users/me/.claude/projects/p/subagent/agent-X.jsonl"), False),  # singular
    (Path("/Users/me/.claude/projects/p/subagents-old/agent-X.jsonl"), False),
    (Path("/Users/me/.claude/projects/p/old-subagents/agent-X.jsonl"), False),

    # NEGATIVE — empty path / minimal path
    (Path("foo.jsonl"), False),
    (Path("/foo.jsonl"), False),
])
def test_claude_code_is_subagent(path, expected):
    a = _claude_adapter()
    assert a.is_subagent(path) is expected, (
        f"is_subagent({path!r}) returned {a.is_subagent(path)}, expected {expected}"
    )


# ─── Cross-product against the other adapters (#430) ─────────────────────


@pytest.mark.parametrize("adapter_cls_name", [
    "codex_cli.CodexCliAdapter",
    "contrib.cursor.CursorAdapter",
    "contrib.gemini_cli.GeminiCliAdapter",
    "contrib.obsidian.ObsidianAdapter",
])
def test_other_adapters_never_classify_as_subagent(adapter_cls_name):
    """Adapters that don't have a sub-agent concept all return False
    for any path — including the false-positive triggers that bit the
    base implementation in #406.

    OpenCode is excluded from this list because the adapter author
    explicitly opts in to a substring check (``"subagent" in
    jsonl_path.name``) — that's a legitimate convention for that store
    layout, even if it has the same false-positive risk."""
    import importlib
    mod_path, cls_name = adapter_cls_name.rsplit(".", 1)
    mod = importlib.import_module(f"llmwiki.adapters.{mod_path}")
    cls = getattr(mod, cls_name)
    a = cls({})
    # Throw every adversarial path at it
    for path in [
        Path("/tmp/subagent/file.jsonl"),
        Path("/tmp/subagents/agent-X.jsonl"),
        Path("/tmp/proj/sess/subagents/agent-X.jsonl"),
        Path("/tmp/subagent-runner/main.jsonl"),
    ]:
        assert a.is_subagent(path) is False, (
            f"{adapter_cls_name}.is_subagent({path!r}) returned True; "
            "this adapter inherits BaseAdapter and should not classify "
            "sub-agents."
        )
