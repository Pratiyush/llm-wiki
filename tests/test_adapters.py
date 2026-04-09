"""Tests for the adapter registry."""

from __future__ import annotations

from llmwiki.adapters import REGISTRY, discover_adapters
from llmwiki.adapters.base import BaseAdapter
from llmwiki.adapters.claude_code import ClaudeCodeAdapter
from llmwiki.adapters.codex_cli import CodexCliAdapter
from llmwiki.adapters.copilot_chat import CopilotChatAdapter
from llmwiki.adapters.copilot_cli import CopilotCliAdapter
from llmwiki.adapters.cursor import CursorAdapter
from llmwiki.adapters.gemini_cli import GeminiCliAdapter
from llmwiki.adapters.obsidian import ObsidianAdapter
from llmwiki.adapters.pdf import PdfAdapter


def test_registry_discovers_all_adapters():
    discover_adapters()
    assert "claude_code" in REGISTRY
    assert "codex_cli" in REGISTRY
    assert "copilot-chat" in REGISTRY
    assert "copilot-cli" in REGISTRY
    assert "cursor" in REGISTRY
    assert "gemini_cli" in REGISTRY
    assert "obsidian" in REGISTRY
    assert "pdf" in REGISTRY


def test_all_adapters_subclass_base():
    assert issubclass(ClaudeCodeAdapter, BaseAdapter)
    assert issubclass(CodexCliAdapter, BaseAdapter)
    assert issubclass(CopilotChatAdapter, BaseAdapter)
    assert issubclass(CopilotCliAdapter, BaseAdapter)
    assert issubclass(CursorAdapter, BaseAdapter)
    assert issubclass(GeminiCliAdapter, BaseAdapter)
    assert issubclass(ObsidianAdapter, BaseAdapter)
    assert issubclass(PdfAdapter, BaseAdapter)


def test_all_adapters_have_name():
    discover_adapters()
    for name, cls in REGISTRY.items():
        assert cls.name == name, f"adapter {cls.__name__} name mismatch"


def test_all_adapters_have_description():
    discover_adapters()
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
