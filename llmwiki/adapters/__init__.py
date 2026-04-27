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

# #v1378-review: aliases tracked separately so REGISTRY stays
# canonical-only. `cmd_adapters` and any other consumer that walks
# every adapter exactly once can iterate REGISTRY directly without
# de-duping. Lookup-by-alias still works via `resolve_adapter_name`.
REGISTRY_ALIASES: dict[str, str] = {}

# Contrib adapters that can be loaded on demand.
CONTRIB_ADAPTERS = {
    "chatgpt", "copilot_chat", "copilot_cli",
    "cursor", "gemini_cli", "obsidian", "opencode",
}


def register(name: str, aliases: list[str] | None = None):
    """Decorator used by adapter modules to register themselves.

    ``aliases`` (#arch-l5 / #626): historical lookup-only names that
    resolve to the same class. Used to keep kebab-case names like
    ``copilot-chat`` working after the canonical name moves to
    snake_case (``copilot_chat``). ``cls.name`` always reflects the
    canonical name.

    #v1378-review: aliases live in a SEPARATE ``REGISTRY_ALIASES`` map
    so iterating ``REGISTRY`` walks each adapter exactly once. The
    previous version inserted aliases into ``REGISTRY`` directly,
    which made ``cmd_adapters`` print duplicate rows (one for the
    canonical name, one for the alias) and made ``adapter_status``
    look up the wrong config key on the alias row.

    A collision guard prevents an alias from shadowing an existing
    canonical adapter — e.g. ``register("copilot_chat",
    aliases=["claude_code"])`` would raise ValueError, not silently
    replace the real ``claude_code`` entry.
    """
    def decorator(cls):
        REGISTRY[name] = cls
        cls.name = name
        for alias in aliases or ():
            if alias in REGISTRY:
                raise ValueError(
                    f"adapter alias {alias!r} would shadow existing "
                    f"canonical adapter {REGISTRY[alias].name!r}"
                )
            existing = REGISTRY_ALIASES.get(alias)
            if existing is not None and existing != name:
                raise ValueError(
                    f"adapter alias {alias!r} already mapped to "
                    f"{existing!r}; cannot remap to {name!r}"
                )
            REGISTRY_ALIASES[alias] = name
        return cls
    return decorator


def resolve_adapter_name(name: str) -> str | None:
    """Return the canonical adapter name for ``name``, or None.

    ``name`` may be the canonical name (returned as-is) or a registered
    alias (returned as the canonical it maps to). Anything else returns
    None, letting callers raise their own user-facing error.
    """
    if name in REGISTRY:
        return name
    canonical = REGISTRY_ALIASES.get(name)
    if canonical and canonical in REGISTRY:
        return canonical
    return None


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
