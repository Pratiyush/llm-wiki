"""Tests for #496 — unified adapter is_available() contract.

The bug: `BaseAdapter.is_available()` read `cls.session_store_path`
directly — worked for ClaudeCodeAdapter (class attribute) but
returned the property descriptor object for the 8 contrib adapters
which override session_store_path as a @property. Every contrib
had to re-implement its own is_available().

The fix: BaseAdapter.is_available() now instantiates a temp
instance and reads self.session_store_path through the same code
path discover_sessions() uses. 7 contrib overrides removed; one
(copilot_cli) kept for COPILOT_HOME env-var handling.
"""

from __future__ import annotations

import importlib

import pytest

from llmwiki.adapters import REGISTRY
from llmwiki.adapters.base import BaseAdapter
from llmwiki.adapters.claude_code import ClaudeCodeAdapter


# Force-load every contrib adapter so the registry is populated.
for mod in (
    "llmwiki.adapters.codex_cli",
    "llmwiki.adapters.contrib.copilot_chat",
    "llmwiki.adapters.contrib.copilot_cli",
    "llmwiki.adapters.contrib.cursor",
    "llmwiki.adapters.contrib.gemini_cli",
    "llmwiki.adapters.contrib.obsidian",
    "llmwiki.adapters.contrib.opencode",
    "llmwiki.adapters.contrib.chatgpt",
):
    importlib.import_module(mod)


def test_claude_code_class_attribute_pattern_still_works():
    """The legacy class-attribute pattern (no @property override) must
    keep working — ClaudeCodeAdapter is the canonical user."""
    result = ClaudeCodeAdapter.is_available()
    assert isinstance(result, bool)


def test_contrib_property_pattern_still_works():
    """Contrib adapters (codex_cli, cursor, etc.) override
    session_store_path as @property. is_available() now flows through
    BaseAdapter via temp-instance and reads it correctly."""
    contrib_names = [
        "codex_cli", "copilot-chat", "cursor", "gemini_cli",
        "obsidian", "opencode", "chatgpt",
    ]
    for name in contrib_names:
        if name not in REGISTRY:
            continue
        cls = REGISTRY[name]
        result = cls.is_available()
        assert isinstance(result, bool), (
            f"{name}.is_available() returned {type(result)}, "
            f"expected bool — temp-instance pattern broke"
        )


def test_six_contrib_adapters_inherit_base_is_available():
    """The 6 adapters whose duplicate is_available() was removed must
    now resolve to BaseAdapter.is_available (no per-class shadow).

    Excluded:
    - copilot_cli — kept its specialised override (COPILOT_HOME)
    - chatgpt — intentionally returns False unconditionally (opt-in
      only, requires explicit config)
    """
    inherited = ("codex_cli", "copilot-chat", "cursor", "gemini_cli",
                 "obsidian", "opencode")
    for name in inherited:
        if name not in REGISTRY:
            continue
        cls = REGISTRY[name]
        assert cls.is_available.__func__ is BaseAdapter.is_available.__func__, (
            f"{name} re-shadows is_available — should inherit from base "
            f"after #496 cleanup"
        )


def test_chatgpt_intentional_disabled_default_preserved():
    """chatgpt.is_available() returns False by default (opt-in only).
    Must not have been swept up in the #496 cleanup."""
    if "chatgpt" not in REGISTRY:
        pytest.skip("chatgpt not registered")
    cls = REGISTRY["chatgpt"]
    # NOT inheriting BaseAdapter.is_available — has its own opt-in default.
    assert cls.is_available.__func__ is not BaseAdapter.is_available.__func__
    assert cls.is_available() is False


def test_copilot_cli_intentional_override_preserved():
    """copilot_cli kept its is_available() override because it has
    special COPILOT_HOME env-var handling."""
    if "copilot-cli" not in REGISTRY:
        pytest.skip("copilot-cli not registered in this environment")
    cls = REGISTRY["copilot-cli"]
    assert cls.is_available.__func__ is not BaseAdapter.is_available.__func__, (
        "copilot_cli should keep its specialised is_available() — "
        "the COPILOT_HOME env-var fallback isn't in BaseAdapter"
    )


def test_broken_init_adapter_returns_false_not_crash():
    """An adapter whose __init__ raises (e.g. missing transitive
    import surfaced eagerly) must report unavailable rather than
    crash the whole `llmwiki adapters` listing."""

    class BrokenAdapter(BaseAdapter):
        name = "broken_test"

        def __init__(self, config=None):
            raise RuntimeError("simulated import / config failure")

    result = BrokenAdapter.is_available()
    assert result is False
