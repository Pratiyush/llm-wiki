"""Adapter registry.

Each adapter knows how to find .jsonl session files for one coding agent and
parse them into a stream of records. Adapters register themselves on import.

    from llmwiki.adapters import REGISTRY, discover_adapters
    discover_adapters()
    adapter_cls = REGISTRY["claude_code"]
    adapter = adapter_cls(config)
    for path, meta, records in adapter.iter_sessions():
        ...
"""

from __future__ import annotations

from typing import Any

from llmwiki.adapters.base import BaseAdapter

REGISTRY: dict[str, type[BaseAdapter]] = {}


def register(name: str):
    """Decorator used by adapter modules to register themselves."""
    def decorator(cls):
        REGISTRY[name] = cls
        cls.name = name
        return cls
    return decorator


def discover_adapters() -> None:
    """Import all built-in adapters so they register themselves."""
    # Order matters only for stable listing.
    from llmwiki.adapters import claude_code  # noqa: F401
    from llmwiki.adapters import codex_cli  # noqa: F401
    from llmwiki.adapters import cursor  # noqa: F401
    from llmwiki.adapters import gemini_cli  # noqa: F401
    from llmwiki.adapters import obsidian  # noqa: F401
    from llmwiki.adapters import pdf  # noqa: F401


def get_available() -> dict[str, type[BaseAdapter]]:
    """Return only adapters whose session store exists on this machine."""
    discover_adapters()
    return {name: cls for name, cls in REGISTRY.items() if cls.is_available()}
