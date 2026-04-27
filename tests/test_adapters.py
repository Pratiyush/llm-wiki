"""Tests for the adapter registry."""

from __future__ import annotations

from llmwiki.adapters import REGISTRY, discover_all
from llmwiki.adapters.base import BaseAdapter
from llmwiki.adapters.claude_code import ClaudeCodeAdapter
from llmwiki.adapters.codex_cli import CodexCliAdapter
from llmwiki.adapters.contrib.copilot_chat import CopilotChatAdapter
from llmwiki.adapters.contrib.copilot_cli import CopilotCliAdapter
from llmwiki.adapters.contrib.cursor import CursorAdapter
from llmwiki.adapters.contrib.gemini_cli import GeminiCliAdapter
from llmwiki.adapters.contrib.obsidian import ObsidianAdapter


def test_registry_discovers_all_adapters():
    discover_all()
    assert "claude_code" in REGISTRY
    assert "codex_cli" in REGISTRY
    # #626: copilot adapters now register under snake_case (canonical)
    # plus a kebab-case alias (back-compat for existing user configs).
    assert "copilot_chat" in REGISTRY
    assert "copilot_cli" in REGISTRY
    assert "copilot-chat" in REGISTRY  # alias
    assert "copilot-cli" in REGISTRY  # alias
    assert "cursor" in REGISTRY
    assert "gemini_cli" in REGISTRY
    assert "obsidian" in REGISTRY


def test_all_adapters_subclass_base():
    assert issubclass(ClaudeCodeAdapter, BaseAdapter)
    assert issubclass(CodexCliAdapter, BaseAdapter)
    assert issubclass(CopilotChatAdapter, BaseAdapter)
    assert issubclass(CopilotCliAdapter, BaseAdapter)
    assert issubclass(CursorAdapter, BaseAdapter)
    assert issubclass(GeminiCliAdapter, BaseAdapter)
    assert issubclass(ObsidianAdapter, BaseAdapter)


def test_all_adapters_have_name():
    # #626: REGISTRY may carry alias keys that legitimately differ from
    # ``cls.name`` (e.g. ``copilot-chat`` aliases the canonical
    # ``copilot_chat``). Walk the unique classes once instead of asserting
    # every key matches ``cls.name``.
    discover_all()
    seen: set[type] = set()
    for cls in REGISTRY.values():
        if cls in seen:
            continue
        seen.add(cls)
        assert isinstance(cls.name, str) and cls.name, (
            f"adapter {cls.__name__} has no name"
        )
        assert REGISTRY.get(cls.name) is cls, (
            f"adapter {cls.__name__} canonical name {cls.name!r} not in REGISTRY"
        )


def test_all_adapters_have_description():
    discover_all()
    for cls in REGISTRY.values():
        desc = cls.description()
        assert isinstance(desc, str)
        assert len(desc) > 0


def test_claude_code_project_slug_stripping():
    """derive_project_slug should strip the common '-Users-...-draft-' prefix."""
    from pathlib import Path

    adapter = ClaudeCodeAdapter()
    # Fake a path that looks like what Claude Code writes
    p = (
        adapter.session_store_path
        / "-Users-alice-Desktop-2026-production-draft-ai-newsletter"
        / "abc-def.jsonl"
    )
    slug = adapter.derive_project_slug(p)
    assert slug == "ai-newsletter"


def test_claude_code_project_slug_fallback():
    from pathlib import Path

    adapter = ClaudeCodeAdapter()
    # Path that doesn't match the expected pattern
    p = adapter.session_store_path / "random-project" / "s.jsonl"
    slug = adapter.derive_project_slug(p)
    assert slug  # any non-empty string is acceptable
