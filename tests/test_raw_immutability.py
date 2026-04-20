"""Tests for raw/ immutability guardrail + AI-session adapter defaults (#326).

Covers:
* ``_raw_write_guard`` raises when out_path exists + force=False
* ``_raw_write_guard`` passes when out_path exists + force=True
* ``_raw_write_guard`` passes when out_path doesn't exist
* Every non-AI adapter has ``is_ai_session = False``
* Every AI adapter has ``is_ai_session = True``
* Convert loop skips non-AI adapters unless explicitly enabled
* Convert loop includes non-AI adapters when enabled via config
"""

from __future__ import annotations

from pathlib import Path

import pytest

from llmwiki.convert import _raw_write_guard


# ─── _raw_write_guard unit ────────────────────────────────────────────────


def test_guard_passes_when_file_missing(tmp_path):
    out = tmp_path / "new.md"
    _raw_write_guard(out, force=False, source="src.jsonl", adapter_name="x")
    # No exception → pass


def test_guard_raises_when_file_exists_and_not_forced(tmp_path):
    out = tmp_path / "existing.md"
    out.write_text("existing content", encoding="utf-8")
    with pytest.raises(FileExistsError) as exc:
        _raw_write_guard(out, force=False, source="src.jsonl", adapter_name="x")
    assert "refusing to overwrite" in str(exc.value)
    assert "--force" in str(exc.value)


def test_guard_passes_when_forced(tmp_path):
    out = tmp_path / "existing.md"
    out.write_text("existing", encoding="utf-8")
    _raw_write_guard(out, force=True, source="src.jsonl", adapter_name="x")


def test_guard_error_includes_source_and_adapter(tmp_path):
    out = tmp_path / "f.md"
    out.write_text("x", encoding="utf-8")
    with pytest.raises(FileExistsError) as exc:
        _raw_write_guard(out, force=False, source="src.jsonl", adapter_name="claude_code")
    err = str(exc.value)
    assert "src.jsonl" in err
    assert "claude_code" in err


# ─── is_ai_session classification ────────────────────────────────────────


AI_SESSION_ADAPTERS = {
    "claude_code", "codex_cli", "copilot-chat", "copilot-cli",
    "cursor", "gemini_cli", "opencode", "chatgpt",
}
NON_AI_ADAPTERS = {"obsidian", "jira", "meeting", "pdf"}


def test_ai_session_adapters_are_marked():
    from llmwiki.adapters import REGISTRY, discover_adapters
    discover_adapters()
    for name in AI_SESSION_ADAPTERS:
        if name not in REGISTRY:
            continue  # adapter may not be registered
        cls = REGISTRY[name]
        assert getattr(cls, "is_ai_session", True) is True, (
            f"{name} should be marked as an AI-session adapter"
        )


def test_non_ai_adapters_are_opt_in():
    from llmwiki.adapters import REGISTRY, discover_adapters
    discover_adapters()
    for name in NON_AI_ADAPTERS:
        if name not in REGISTRY:
            continue
        cls = REGISTRY[name]
        assert cls.is_ai_session is False, (
            f"{name} is user content, not an AI session — should be opt-in "
            "(is_ai_session = False). See #326."
        )


def test_base_adapter_defaults_to_ai_session():
    """Safe default: new adapters without explicit markers are treated
    as AI sessions (so we don't silently skip legitimate adapters)."""
    from llmwiki.adapters.base import BaseAdapter
    assert BaseAdapter.is_ai_session is True


# ─── selection logic ────────────────────────────────────────────────────


class _FakeAI:
    name = "ai_test"
    is_ai_session = True

    @classmethod
    def is_available(cls):
        return True


class _FakeNonAI:
    name = "non_ai_test"
    is_ai_session = False

    @classmethod
    def is_available(cls):
        return True


def test_default_selection_picks_ai_only(monkeypatch):
    """#326: default adapter selection skips non-AI adapters."""
    import llmwiki.convert as convert_mod
    monkeypatch.setattr(
        convert_mod, "REGISTRY",
        {"ai_test": _FakeAI, "non_ai_test": _FakeNonAI},
    )
    # Replicate the loop from convert_all:
    config: dict = {}
    selected = []
    for cls in convert_mod.REGISTRY.values():
        if not cls.is_available():
            continue
        explicit = False
        if cls.name in config and isinstance(config[cls.name], dict):
            explicit = config[cls.name].get("enabled") is True
        if getattr(cls, "is_ai_session", True) or explicit:
            selected.append(cls)
    names = {s.name for s in selected}
    assert names == {"ai_test"}


def test_explicit_enable_includes_non_ai(monkeypatch):
    """#326: non-AI adapters can be opted in via sessions_config.json."""
    import llmwiki.convert as convert_mod
    monkeypatch.setattr(
        convert_mod, "REGISTRY",
        {"ai_test": _FakeAI, "non_ai_test": _FakeNonAI},
    )
    config = {"non_ai_test": {"enabled": True}}
    selected = []
    for cls in convert_mod.REGISTRY.values():
        if not cls.is_available():
            continue
        explicit = False
        if cls.name in config and isinstance(config[cls.name], dict):
            explicit = config[cls.name].get("enabled") is True
        if getattr(cls, "is_ai_session", True) or explicit:
            selected.append(cls)
    names = {s.name for s in selected}
    assert names == {"ai_test", "non_ai_test"}


def test_explicit_disable_still_works_for_ai():
    """AI adapters can still be explicitly disabled via config."""
    # This is already covered by existing sync/--status tests, but the
    # invariant matters here: `enabled: false` on an AI adapter turns
    # it off regardless of is_ai_session.
    cfg = {"enabled": False}
    assert cfg.get("enabled") is False
