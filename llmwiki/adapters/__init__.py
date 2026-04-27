"""Adapter registry.

Each adapter knows how to find .jsonl session files for one coding agent and
parse them into a stream of records. Adapters register themselves on import.

    from llmwiki.adapters import REGISTRY, discover_adapters
    discover_adapters()
    adapter_cls = REGISTRY["claude_code"]
    adapter = adapter_cls(config)
    for path in adapter.discover_sessions():
        ...

Core adapters (always loaded):
    claude_code, codex_cli

Contrib adapters (loaded on demand via --adapter flag):
    chatgpt, copilot_chat, copilot_cli, cursor, gemini_cli, obsidian, opencode
"""

from __future__ import annotations

from typing import Any

from llmwiki.adapters.base import BaseAdapter

REGISTRY: dict[str, type[BaseAdapter]] = {}

# Contrib adapters that can be loaded on demand.
CONTRIB_ADAPTERS = {
    "chatgpt", "copilot_chat", "copilot_cli",
    "cursor", "gemini_cli", "obsidian", "opencode",
}


def register(name: str, aliases: list[str] | None = None):
    """Decorator used by adapter modules to register themselves.

    ``aliases`` (#arch-l5 / #626): additional REGISTRY keys that resolve
    to the same class. Used to keep historical kebab-case names like
    ``copilot-chat`` working after the canonical name moves to
    snake_case (``copilot_chat``). ``cls.name`` always reflects the
    canonical name; aliases only affect REGISTRY lookups.
    """
    def decorator(cls):
        REGISTRY[name] = cls
        cls.name = name
        for alias in aliases or ():
            REGISTRY[alias] = cls
        return cls
    return decorator


def discover_adapters() -> None:
    """Import core adapters so they register themselves."""
    from llmwiki.adapters import claude_code  # noqa: F401
    from llmwiki.adapters import codex_cli  # noqa: F401


def discover_contrib(names: list[str] | None = None) -> None:
    """Import contrib adapters on demand.

    Parameters
    ----------
    names : list[str] | None
        Specific adapter names to load. If None, loads all contrib adapters.
    """
    targets = names if names else CONTRIB_ADAPTERS
    for name in targets:
        if name not in CONTRIB_ADAPTERS:
            continue
        try:
            __import__(f"llmwiki.adapters.contrib.{name}")
        except ImportError as e:
            import sys
            print(f"  warning: contrib adapter {name!r} failed to load: {e}",
                  file=sys.stderr)


def discover_all() -> None:
    """Import all adapters (core + contrib)."""
    discover_adapters()
    discover_contrib()


def get_available() -> dict[str, type[BaseAdapter]]:
    """Return only adapters whose session store exists on this machine."""
    discover_adapters()
    return {name: cls for name, cls in REGISTRY.items() if cls.is_available()}
