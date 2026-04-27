"""Tests for GitHub Copilot adapters — Chat + CLI (v0.6 · #93).

Verifies each adapter's contract: SUPPORTED_SCHEMA_VERSIONS,
discover_sessions, derive_project_slug, cross-platform DEFAULT_ROOTS,
and graceful degradation (no crash on bad input / nonexistent paths).
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from llmwiki.adapters import REGISTRY, discover_all
from llmwiki.adapters.base import BaseAdapter
from llmwiki.adapters.contrib.copilot_chat import CopilotChatAdapter
from llmwiki.adapters.contrib.copilot_cli import CopilotCliAdapter


# ═══════════════════════════════════════════════════════════════════════
# COPILOT CHAT ADAPTER — Contract
# ═══════════════════════════════════════════════════════════════════════


class TestCopilotChatContract:
    def test_has_supported_schema_versions(self):
        assert hasattr(CopilotChatAdapter, "SUPPORTED_SCHEMA_VERSIONS")
        assert len(CopilotChatAdapter.SUPPORTED_SCHEMA_VERSIONS) >= 1

    def test_subclasses_base_adapter(self):
        assert issubclass(CopilotChatAdapter, BaseAdapter)

    def test_session_store_path_returns_list(self):
        adapter = CopilotChatAdapter()
        paths = adapter.session_store_path
        assert isinstance(paths, list)
        assert len(paths) > 0

    def test_discover_sessions_returns_list(self):
        adapter = CopilotChatAdapter()
        result = adapter.discover_sessions()
        assert isinstance(result, list)

    def test_derive_project_slug_returns_nonempty_string(self):
        adapter = CopilotChatAdapter()
        slug = adapter.derive_project_slug(
            Path("/tmp/workspaceStorage/abc123def456/chatSessions/conv.jsonl")
        )
        assert isinstance(slug, str)
        assert len(slug) > 0

    def test_instantiate_with_no_config(self):
        adapter = CopilotChatAdapter()
        assert adapter is not None

    def test_instantiate_with_empty_config(self):
        adapter = CopilotChatAdapter(config={})
        assert adapter is not None

    def test_description_is_nonempty(self):
        desc = CopilotChatAdapter.description()
        assert isinstance(desc, str)
        assert len(desc) > 0

    def test_registered_as_copilot_chat(self):
        # #v1378-review: REGISTRY is canonical-only; aliases live in
        # REGISTRY_ALIASES and resolve via resolve_adapter_name.
        from llmwiki.adapters import REGISTRY_ALIASES, resolve_adapter_name
        discover_all()
        assert "copilot_chat" in REGISTRY
        assert REGISTRY["copilot_chat"] is CopilotChatAdapter
        assert REGISTRY_ALIASES.get("copilot-chat") == "copilot_chat"
        assert resolve_adapter_name("copilot-chat") == "copilot_chat"


# ═══════════════════════════════════════════════════════════════════════
# COPILOT CHAT ADAPTER — Cross-platform roots
# ═══════════════════════════════════════════════════════════════════════


class TestCopilotChatCrossPlatform:
    def test_default_roots_has_macos_entries(self):
        roots = CopilotChatAdapter.DEFAULT_ROOTS
        macos = [r for r in roots if "Library" in str(r) and "Application Support" in str(r)]
        # Should have entries for Code, Code - Insiders, VSCodium
        assert len(macos) >= 3

    def test_default_roots_has_linux_entries(self):
        roots = CopilotChatAdapter.DEFAULT_ROOTS
        linux = [r for r in roots if ".config" in str(r)]
        assert len(linux) >= 3

    def test_default_roots_has_windows_entries(self):
        roots = CopilotChatAdapter.DEFAULT_ROOTS
        windows = [r for r in roots if "AppData" in str(r)]
        assert len(windows) >= 3

    def test_default_roots_includes_insiders(self):
        roots = CopilotChatAdapter.DEFAULT_ROOTS
        insiders = [r for r in roots if "Code - Insiders" in str(r)]
        assert len(insiders) >= 1

    def test_default_roots_includes_vscodium(self):
        roots = CopilotChatAdapter.DEFAULT_ROOTS
        codium = [r for r in roots if "VSCodium" in str(r)]
        assert len(codium) >= 1


# ═══════════════════════════════════════════════════════════════════════
# COPILOT CHAT ADAPTER — Discovery + Slug
# ═══════════════════════════════════════════════════════════════════════


class TestCopilotChatDiscovery:
    def test_discover_finds_jsonl_in_chatsessions(self, tmp_path: Path):
        ws = tmp_path / "abc123def456" / "chatSessions"
        ws.mkdir(parents=True)
        (ws / "conv1.jsonl").write_text('{"role":"user","content":"hi"}\n')
        cfg = {"adapters": {"copilot-chat": {"roots": [str(tmp_path)]}}}
        adapter = CopilotChatAdapter(config=cfg)
        sessions = adapter.discover_sessions()
        assert len(sessions) == 1
        assert sessions[0].name == "conv1.jsonl"

    def test_discover_finds_json_in_chatsessions(self, tmp_path: Path):
        ws = tmp_path / "abc123def456" / "chatSessions"
        ws.mkdir(parents=True)
        (ws / "conv1.json").write_text('[{"role":"user","content":"hi"}]')
        cfg = {"adapters": {"copilot-chat": {"roots": [str(tmp_path)]}}}
        adapter = CopilotChatAdapter(config=cfg)
        sessions = adapter.discover_sessions()
        assert len(sessions) == 1
        assert sessions[0].name == "conv1.json"

    def test_discover_ignores_files_outside_chatsessions(self, tmp_path: Path):
        ws = tmp_path / "abc123def456"
        ws.mkdir(parents=True)
        # File directly in workspace dir, not in chatSessions/
        (ws / "state.jsonl").write_text("{}\n")
        cfg = {"adapters": {"copilot-chat": {"roots": [str(tmp_path)]}}}
        adapter = CopilotChatAdapter(config=cfg)
        sessions = adapter.discover_sessions()
        assert len(sessions) == 0

    def test_discover_multiple_workspaces(self, tmp_path: Path):
        for wname in ["ws1", "ws2"]:
            ws = tmp_path / wname / "chatSessions"
            ws.mkdir(parents=True)
            (ws / "conv.jsonl").write_text("{}\n")
        cfg = {"adapters": {"copilot-chat": {"roots": [str(tmp_path)]}}}
        adapter = CopilotChatAdapter(config=cfg)
        sessions = adapter.discover_sessions()
        assert len(sessions) == 2

    def test_discover_deduplicates(self, tmp_path: Path):
        ws = tmp_path / "ws1" / "chatSessions"
        ws.mkdir(parents=True)
        (ws / "conv.jsonl").write_text("{}\n")
        # Point both roots to the same directory
        cfg = {"adapters": {"copilot-chat": {"roots": [str(tmp_path), str(tmp_path)]}}}
        adapter = CopilotChatAdapter(config=cfg)
        sessions = adapter.discover_sessions()
        assert len(sessions) == 1

    def test_derive_slug_from_workspace_hash(self, tmp_path: Path):
        ws = tmp_path / "a1b2c3d4e5f6g7h8" / "chatSessions"
        ws.mkdir(parents=True)
        f = ws / "conv.jsonl"
        f.write_text("{}\n")
        cfg = {"adapters": {"copilot-chat": {"roots": [str(tmp_path)]}}}
        adapter = CopilotChatAdapter(config=cfg)
        slug = adapter.derive_project_slug(f)
        assert slug == "copilot-a1b2c3d4e5f6"

    def test_derive_slug_truncates_long_hash(self, tmp_path: Path):
        long_hash = "abcdef123456789012345678"
        ws = tmp_path / long_hash / "chatSessions"
        ws.mkdir(parents=True)
        f = ws / "conv.jsonl"
        f.write_text("{}\n")
        cfg = {"adapters": {"copilot-chat": {"roots": [str(tmp_path)]}}}
        adapter = CopilotChatAdapter(config=cfg)
        slug = adapter.derive_project_slug(f)
        assert slug == "copilot-abcdef123456"
        assert len(slug) == len("copilot-") + 12


# ═══════════════════════════════════════════════════════════════════════
# COPILOT CHAT ADAPTER — Graceful degradation
# ═══════════════════════════════════════════════════════════════════════


class TestCopilotChatGracefulDegradation:
    def test_discover_nonexistent_roots(self):
        cfg = {"adapters": {"copilot-chat": {"roots": ["/nonexistent/copilot/xyz"]}}}
        adapter = CopilotChatAdapter(config=cfg)
        sessions = adapter.discover_sessions()
        assert sessions == []

    def test_mixed_roots(self, tmp_path: Path):
        real_dir = tmp_path / "real" / "chatSessions"
        real_dir.mkdir(parents=True)
        (real_dir / "conv.jsonl").write_text("{}\n")
        cfg = {
            "adapters": {
                "copilot-chat": {
                    "roots": ["/nonexistent", str(tmp_path)]
                }
            }
        }
        adapter = CopilotChatAdapter(config=cfg)
        sessions = adapter.discover_sessions()
        assert len(sessions) == 1

    def test_empty_workspace_dirs(self, tmp_path: Path):
        (tmp_path / "ws1" / "chatSessions").mkdir(parents=True)
        cfg = {"adapters": {"copilot-chat": {"roots": [str(tmp_path)]}}}
        adapter = CopilotChatAdapter(config=cfg)
        sessions = adapter.discover_sessions()
        assert sessions == []

    def test_derive_slug_fallback_for_unknown_path(self):
        adapter = CopilotChatAdapter()
        slug = adapter.derive_project_slug(Path("/random/unknown/chatSessions/conv.jsonl"))
        assert isinstance(slug, str)
        assert len(slug) > 0


# ═══════════════════════════════════════════════════════════════════════
# COPILOT CLI ADAPTER — Contract
# ═══════════════════════════════════════════════════════════════════════


class TestCopilotCliContract:
    def test_has_supported_schema_versions(self):
        assert hasattr(CopilotCliAdapter, "SUPPORTED_SCHEMA_VERSIONS")
        assert len(CopilotCliAdapter.SUPPORTED_SCHEMA_VERSIONS) >= 1

    def test_subclasses_base_adapter(self):
        assert issubclass(CopilotCliAdapter, BaseAdapter)

    def test_session_store_path_returns_list(self):
        adapter = CopilotCliAdapter()
        paths = adapter.session_store_path
        assert isinstance(paths, list)
        assert len(paths) > 0

    def test_discover_sessions_returns_list(self):
        adapter = CopilotCliAdapter()
        result = adapter.discover_sessions()
        assert isinstance(result, list)

    def test_derive_project_slug_returns_nonempty_string(self):
        adapter = CopilotCliAdapter()
        slug = adapter.derive_project_slug(
            Path("/tmp/session-state/abc-123-def/events.jsonl")
        )
        assert isinstance(slug, str)
        assert len(slug) > 0

    def test_instantiate_with_no_config(self):
        adapter = CopilotCliAdapter()
        assert adapter is not None

    def test_instantiate_with_empty_config(self):
        adapter = CopilotCliAdapter(config={})
        assert adapter is not None

    def test_description_is_nonempty(self):
        desc = CopilotCliAdapter.description()
        assert isinstance(desc, str)
        assert len(desc) > 0

    def test_registered_as_copilot_cli(self):
        from llmwiki.adapters import REGISTRY_ALIASES, resolve_adapter_name
        discover_all()
        assert "copilot_cli" in REGISTRY
        assert REGISTRY["copilot_cli"] is CopilotCliAdapter
        assert REGISTRY_ALIASES.get("copilot-cli") == "copilot_cli"
        assert resolve_adapter_name("copilot-cli") == "copilot_cli"


# ═══════════════════════════════════════════════════════════════════════
# COPILOT CLI ADAPTER — Cross-platform roots
# ═══════════════════════════════════════════════════════════════════════


class TestCopilotCliCrossPlatform:
    def test_default_roots_has_home_copilot(self):
        roots = CopilotCliAdapter.DEFAULT_ROOTS
        home_root = [r for r in roots if ".copilot" in str(r)]
        assert len(home_root) >= 1

    def test_default_roots_all_end_with_session_state(self):
        roots = CopilotCliAdapter.DEFAULT_ROOTS
        for r in roots:
            assert r.name == "session-state", f"Root {r} doesn't end with session-state"

    def test_copilot_home_env_var_adds_root(self, tmp_path: Path, monkeypatch):
        custom = tmp_path / "custom-copilot"
        custom.mkdir()
        monkeypatch.setenv("COPILOT_HOME", str(custom))
        # Re-import to pick up env var at build time
        from llmwiki.adapters.contrib.copilot_cli import _build_default_roots
        roots = _build_default_roots()
        custom_roots = [r for r in roots if str(custom) in str(r)]
        assert len(custom_roots) >= 1


# ═══════════════════════════════════════════════════════════════════════
# COPILOT CLI ADAPTER — Discovery + Slug
# ═══════════════════════════════════════════════════════════════════════


class TestCopilotCliDiscovery:
    def test_discover_finds_events_jsonl(self, tmp_path: Path):
        session_dir = tmp_path / "sess-abc-123"
        session_dir.mkdir(parents=True)
        (session_dir / "events.jsonl").write_text('{"type":"init"}\n')
        cfg = {"adapters": {"copilot-cli": {"roots": [str(tmp_path)]}}}
        adapter = CopilotCliAdapter(config=cfg)
        sessions = adapter.discover_sessions()
        assert len(sessions) == 1
        assert sessions[0].name == "events.jsonl"

    def test_discover_ignores_non_events_files(self, tmp_path: Path):
        session_dir = tmp_path / "sess-abc-123"
        session_dir.mkdir(parents=True)
        (session_dir / "state.json").write_text("{}")
        (session_dir / "events.jsonl").write_text('{"type":"init"}\n')
        cfg = {"adapters": {"copilot-cli": {"roots": [str(tmp_path)]}}}
        adapter = CopilotCliAdapter(config=cfg)
        sessions = adapter.discover_sessions()
        assert len(sessions) == 1
        assert sessions[0].name == "events.jsonl"

    def test_discover_multiple_sessions(self, tmp_path: Path):
        for sname in ["sess-1", "sess-2", "sess-3"]:
            d = tmp_path / sname
            d.mkdir()
            (d / "events.jsonl").write_text('{"type":"init"}\n')
        cfg = {"adapters": {"copilot-cli": {"roots": [str(tmp_path)]}}}
        adapter = CopilotCliAdapter(config=cfg)
        sessions = adapter.discover_sessions()
        assert len(sessions) == 3

    def test_discover_deduplicates(self, tmp_path: Path):
        d = tmp_path / "sess-1"
        d.mkdir()
        (d / "events.jsonl").write_text('{"type":"init"}\n')
        cfg = {"adapters": {"copilot-cli": {"roots": [str(tmp_path), str(tmp_path)]}}}
        adapter = CopilotCliAdapter(config=cfg)
        sessions = adapter.discover_sessions()
        assert len(sessions) == 1

    def test_derive_slug_uses_session_id_dir(self, tmp_path: Path):
        session_dir = tmp_path / "my-session-uuid-42"
        session_dir.mkdir()
        f = session_dir / "events.jsonl"
        f.write_text('{"type":"init"}\n')
        cfg = {"adapters": {"copilot-cli": {"roots": [str(tmp_path)]}}}
        adapter = CopilotCliAdapter(config=cfg)
        slug = adapter.derive_project_slug(f)
        assert slug == "my-session-uuid-42"

    def test_derive_slug_fallback(self):
        adapter = CopilotCliAdapter()
        slug = adapter.derive_project_slug(Path("/random/sess-xyz/events.jsonl"))
        assert isinstance(slug, str)
        assert len(slug) > 0


# ═══════════════════════════════════════════════════════════════════════
# COPILOT CLI ADAPTER — Graceful degradation
# ═══════════════════════════════════════════════════════════════════════


class TestCopilotCliGracefulDegradation:
    def test_discover_nonexistent_roots(self):
        cfg = {"adapters": {"copilot-cli": {"roots": ["/nonexistent/copilot/xyz"]}}}
        adapter = CopilotCliAdapter(config=cfg)
        sessions = adapter.discover_sessions()
        assert sessions == []

    def test_mixed_roots(self, tmp_path: Path):
        real_dir = tmp_path / "sess-1"
        real_dir.mkdir()
        (real_dir / "events.jsonl").write_text('{"type":"init"}\n')
        cfg = {
            "adapters": {
                "copilot-cli": {
                    "roots": ["/nonexistent", str(tmp_path)]
                }
            }
        }
        adapter = CopilotCliAdapter(config=cfg)
        sessions = adapter.discover_sessions()
        assert len(sessions) == 1

    def test_empty_session_dirs(self, tmp_path: Path):
        (tmp_path / "sess-1").mkdir()
        cfg = {"adapters": {"copilot-cli": {"roots": [str(tmp_path)]}}}
        adapter = CopilotCliAdapter(config=cfg)
        sessions = adapter.discover_sessions()
        assert sessions == []


# ═══════════════════════════════════════════════════════════════════════
# CROSS-ADAPTER — both Copilot adapters
# ═══════════════════════════════════════════════════════════════════════


class TestCopilotCrossAdapter:
    def test_both_handle_empty_config(self):
        for cls in [CopilotChatAdapter, CopilotCliAdapter]:
            adapter = cls(config={})
            assert adapter is not None
            sessions = adapter.discover_sessions()
            assert isinstance(sessions, list)

    def test_both_in_registry(self):
        # #626: canonical names are snake_case; kebab-case still resolves
        # via the alias mechanism so existing user configs don't break.
        # #v1378-review: aliases moved out of REGISTRY into
        # REGISTRY_ALIASES so a canonical iteration of REGISTRY hits
        # each adapter once. Lookup-by-alias goes through resolve_adapter_name.
        from llmwiki.adapters import REGISTRY_ALIASES, resolve_adapter_name
        discover_all()
        assert "copilot_chat" in REGISTRY
        assert "copilot_cli" in REGISTRY
        # Legacy kebab-case is no longer a REGISTRY key but resolves correctly.
        assert "copilot-chat" not in REGISTRY
        assert "copilot-cli" not in REGISTRY
        assert REGISTRY_ALIASES["copilot-chat"] == "copilot_chat"
        assert REGISTRY_ALIASES["copilot-cli"] == "copilot_cli"
        assert REGISTRY[resolve_adapter_name("copilot-chat")] is REGISTRY["copilot_chat"]
        assert REGISTRY[resolve_adapter_name("copilot-cli")] is REGISTRY["copilot_cli"]

    def test_names_set_by_register(self):
        # #626: cls.name reflects the canonical (snake_case) name only;
        # aliases never overwrite cls.name.
        discover_all()
        assert CopilotChatAdapter.name == "copilot_chat"
        assert CopilotCliAdapter.name == "copilot_cli"

    def test_kebab_case_config_still_recognised(self, tmp_path):
        # #626: existing user `sessions_config.json` files keyed under
        # `copilot-chat` / `copilot-cli` must keep working — the
        # adapter __init__ falls back to the legacy key when the
        # snake_case key is absent.
        discover_all()
        legacy_chat = {"adapters": {"copilot-chat": {"roots": [str(tmp_path)]}}}
        adapter = CopilotChatAdapter(config=legacy_chat)
        assert adapter.roots == [tmp_path]
        legacy_cli = {"adapters": {"copilot-cli": {"roots": [str(tmp_path)]}}}
        adapter = CopilotCliAdapter(config=legacy_cli)
        assert adapter.roots == [tmp_path]

    def test_snake_case_config_takes_precedence(self, tmp_path):
        # When BOTH keys are present, the canonical snake_case wins so
        # users migrating their config can clean up the old key safely.
        discover_all()
        snake_path = tmp_path / "snake"
        kebab_path = tmp_path / "kebab"
        snake_path.mkdir()
        kebab_path.mkdir()
        cfg = {"adapters": {
            "copilot_chat": {"roots": [str(snake_path)]},
            "copilot-chat": {"roots": [str(kebab_path)]},
        }}
        adapter = CopilotChatAdapter(config=cfg)
        assert adapter.roots == [snake_path]
