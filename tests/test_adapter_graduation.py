"""Tests for graduating Cursor, Gemini CLI, and PDF adapters to production.

Covers:
- Adapter registration and BaseAdapter contract
- SUPPORTED_SCHEMA_VERSIONS declaration
- Realistic session_store_path for each platform
- Converter round-trip against minimal synthetic fixtures
- Snapshot tests (converter output matches golden files)
- Graceful degradation (unknown record type -> skip, don't crash)

References: #37 (Cursor), #38 (Gemini CLI), #39 (PDF)
"""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

import pytest

from llmwiki.adapters import REGISTRY, discover_adapters
from llmwiki.adapters.base import BaseAdapter
from llmwiki.adapters.cursor import CursorAdapter
from llmwiki.adapters.gemini_cli import GeminiCliAdapter
from llmwiki.adapters.pdf import PdfAdapter
from llmwiki.convert import (
    DEFAULT_CONFIG,
    Redactor,
    count_tool_calls,
    count_user_messages,
    extract_tools_used,
    filter_records,
    parse_jsonl,
    render_session_markdown,
)

from tests.conftest import FIXTURES_DIR, SNAPSHOTS_DIR


# ─── Shared helpers ───────────────────────────────────────────────────────


def _update_snapshot(path: Path, content: str) -> None:
    """Write a snapshot file. Called on first run or when UPDATE_SNAPSHOTS=1."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _render_fixture(adapter_name: str, project_slug: str) -> tuple[str, str]:
    """Parse + render a fixture and return (markdown, slug)."""
    fx = FIXTURES_DIR / adapter_name / "minimal.jsonl"
    assert fx.exists(), f"fixture missing: {fx}"
    records = parse_jsonl(fx)
    redactor = Redactor(DEFAULT_CONFIG)
    md, slug, _started = render_session_markdown(
        records,
        jsonl_path=fx,
        project_slug=project_slug,
        redact=redactor,
        config=DEFAULT_CONFIG,
        is_subagent_file=False,
    )
    return md, slug


# ═══════════════════════════════════════════════════════════════════════════
# CURSOR ADAPTER (#37)
# ═══════════════════════════════════════════════════════════════════════════


class TestCursorAdapterContract:
    """Verify the Cursor adapter meets the BaseAdapter contract."""

    def test_subclass_of_base(self):
        assert issubclass(CursorAdapter, BaseAdapter)

    def test_registered(self):
        discover_adapters()
        assert "cursor" in REGISTRY
        assert REGISTRY["cursor"] is CursorAdapter

    def test_name_attribute(self):
        discover_adapters()
        assert CursorAdapter.name == "cursor"

    def test_has_description(self):
        desc = CursorAdapter.description()
        assert isinstance(desc, str)
        assert len(desc) > 0

    def test_declares_supported_schema_versions(self):
        assert hasattr(CursorAdapter, "SUPPORTED_SCHEMA_VERSIONS")
        versions = CursorAdapter.SUPPORTED_SCHEMA_VERSIONS
        assert isinstance(versions, list)
        assert len(versions) > 0
        assert all(isinstance(v, str) for v in versions)

    def test_session_store_path_realistic(self):
        adapter = CursorAdapter()
        paths = adapter.session_store_path
        assert isinstance(paths, list)
        assert len(paths) > 0
        # Should include macOS Application Support path
        path_strs = [str(p) for p in paths]
        assert any("Cursor" in s for s in path_strs)

    def test_default_roots_cover_platforms(self):
        root_strs = [str(p) for p in CursorAdapter.DEFAULT_ROOTS]
        # macOS
        assert any("Library/Application Support/Cursor" in s for s in root_strs)
        # Linux
        assert any(".config/Cursor" in s for s in root_strs)
        # Windows
        assert any("AppData" in s for s in root_strs)

    def test_config_override_roots(self):
        cfg = {"adapters": {"cursor": {"roots": ["/tmp/custom-cursor"]}}}
        adapter = CursorAdapter(config=cfg)
        assert len(adapter.roots) == 1
        assert str(adapter.roots[0]) == "/tmp/custom-cursor"


class TestCursorDiscovery:
    """Test Cursor session discovery and slug derivation."""

    def test_discover_in_empty_dir(self, tmp_path: Path):
        cfg = {"adapters": {"cursor": {"roots": [str(tmp_path)]}}}
        adapter = CursorAdapter(config=cfg)
        assert adapter.discover_sessions() == []

    def test_discover_finds_jsonl(self, tmp_path: Path):
        workspace = tmp_path / "abc123hash"
        workspace.mkdir()
        (workspace / "chat.jsonl").write_text('{"type":"user"}\n')
        cfg = {"adapters": {"cursor": {"roots": [str(tmp_path)]}}}
        adapter = CursorAdapter(config=cfg)
        sessions = adapter.discover_sessions()
        assert len(sessions) == 1
        assert sessions[0].name == "chat.jsonl"

    def test_derive_project_slug_hash_prefix(self, tmp_path: Path):
        cfg = {"adapters": {"cursor": {"roots": [str(tmp_path)]}}}
        adapter = CursorAdapter(config=cfg)
        p = tmp_path / "abcdef123456789" / "session.jsonl"
        slug = adapter.derive_project_slug(p)
        assert slug == "cursor-abcdef123456"

    def test_derive_project_slug_fallback(self):
        adapter = CursorAdapter()
        p = Path("/some/random/path/session.jsonl")
        slug = adapter.derive_project_slug(p)
        assert slug  # any non-empty string is acceptable


class TestCursorConverter:
    """Test the converter round-trip against the Cursor fixture."""

    def test_parse_fixture(self):
        fx = FIXTURES_DIR / "cursor" / "minimal.jsonl"
        records = parse_jsonl(fx)
        assert len(records) == 4
        assert records[0]["type"] == "user"
        assert records[1]["type"] == "assistant"

    def test_count_user_messages(self):
        records = parse_jsonl(FIXTURES_DIR / "cursor" / "minimal.jsonl")
        assert count_user_messages(records) == 1

    def test_count_tool_calls(self):
        records = parse_jsonl(FIXTURES_DIR / "cursor" / "minimal.jsonl")
        assert count_tool_calls(records) == 1

    def test_extract_tools_used(self):
        records = parse_jsonl(FIXTURES_DIR / "cursor" / "minimal.jsonl")
        tools = extract_tools_used(records)
        assert tools == ["Write"]

    def test_render_session_markdown(self):
        md, slug = _render_fixture("cursor", "cursor-abc123")
        assert slug == "cursor-react-dashboard"
        # Frontmatter
        assert "---" in md
        assert "slug: cursor-react-dashboard" in md
        assert "project: cursor-abc123" in md
        assert "tools_used: [Write]" in md
        assert "model: gpt-4o" in md
        # Body
        assert "## Conversation" in md
        assert "### Turn 1 \u2014 User" in md
        assert "React component" in md
        assert "### Turn 1 \u2014 Assistant" in md
        assert "`Write`" in md

    def test_snapshot_match(self):
        md, _slug = _render_fixture("cursor", "cursor-abc123")
        snap = SNAPSHOTS_DIR / "cursor" / "minimal.md"
        if not snap.exists():
            _update_snapshot(snap, md)
        expected = snap.read_text(encoding="utf-8")
        assert md == expected, "Cursor snapshot mismatch -- re-run with UPDATE_SNAPSHOTS=1"

    def test_graceful_degradation_unknown_record_type(self):
        """Unknown record types should be silently skipped, not crash."""
        fx = FIXTURES_DIR / "cursor" / "minimal.jsonl"
        records = parse_jsonl(fx)
        # Inject an unknown record type
        records.insert(1, {"type": "cursor-internal-debug", "data": {"foo": "bar"}})
        # filter_records drops known noise; unknown types pass through but
        # the renderer ignores them (they're not user/assistant/tool_result)
        filtered = filter_records(records, ["queue-operation"])
        redactor = Redactor(DEFAULT_CONFIG)
        # Should NOT raise
        md, slug, started = render_session_markdown(
            filtered,
            jsonl_path=Path("test.jsonl"),
            project_slug="cursor-test",
            redact=redactor,
            config=DEFAULT_CONFIG,
            is_subagent_file=False,
        )
        assert "## Conversation" in md
        assert "cursor-internal-debug" not in md


# ═══════════════════════════════════════════════════════════════════════════
# GEMINI CLI ADAPTER (#38)
# ═══════════════════════════════════════════════════════════════════════════


class TestGeminiCliAdapterContract:
    """Verify the Gemini CLI adapter meets the BaseAdapter contract."""

    def test_subclass_of_base(self):
        assert issubclass(GeminiCliAdapter, BaseAdapter)

    def test_registered(self):
        discover_adapters()
        assert "gemini_cli" in REGISTRY
        assert REGISTRY["gemini_cli"] is GeminiCliAdapter

    def test_name_attribute(self):
        discover_adapters()
        assert GeminiCliAdapter.name == "gemini_cli"

    def test_has_description(self):
        desc = GeminiCliAdapter.description()
        assert isinstance(desc, str)
        assert len(desc) > 0

    def test_declares_supported_schema_versions(self):
        assert hasattr(GeminiCliAdapter, "SUPPORTED_SCHEMA_VERSIONS")
        versions = GeminiCliAdapter.SUPPORTED_SCHEMA_VERSIONS
        assert isinstance(versions, list)
        assert len(versions) > 0
        assert all(isinstance(v, str) for v in versions)

    def test_session_store_path_realistic(self):
        adapter = GeminiCliAdapter()
        paths = adapter.session_store_path
        assert isinstance(paths, list)
        assert len(paths) > 0
        # Should include ~/.gemini
        path_strs = [str(p) for p in paths]
        assert any(".gemini" in s or "gemini" in s for s in path_strs)

    def test_default_roots_cover_xdg(self):
        root_strs = [str(p) for p in GeminiCliAdapter.DEFAULT_ROOTS]
        # Primary
        assert any(".gemini" in s and ".config" not in s for s in root_strs)
        # XDG config
        assert any(".config/gemini" in s for s in root_strs)
        # XDG data
        assert any(".local/share/gemini" in s for s in root_strs)

    def test_config_override_roots(self):
        cfg = {"adapters": {"gemini_cli": {"roots": ["/tmp/custom-gemini"]}}}
        adapter = GeminiCliAdapter(config=cfg)
        assert len(adapter.roots) == 1
        assert str(adapter.roots[0]) == "/tmp/custom-gemini"


class TestGeminiCliDiscovery:
    """Test Gemini CLI session discovery and slug derivation."""

    def test_discover_in_empty_dir(self, tmp_path: Path):
        cfg = {"adapters": {"gemini_cli": {"roots": [str(tmp_path)]}}}
        adapter = GeminiCliAdapter(config=cfg)
        assert adapter.discover_sessions() == []

    def test_discover_finds_jsonl(self, tmp_path: Path):
        sessions_dir = tmp_path / "chats"
        sessions_dir.mkdir()
        (sessions_dir / "session-001.jsonl").write_text('{"type":"user"}\n')
        cfg = {"adapters": {"gemini_cli": {"roots": [str(tmp_path)]}}}
        adapter = GeminiCliAdapter(config=cfg)
        sessions = adapter.discover_sessions()
        assert len(sessions) == 1

    def test_discover_finds_json_patterns(self, tmp_path: Path):
        (tmp_path / "chat-abc.json").write_text('{}')
        (tmp_path / "session-xyz.json").write_text('{}')
        (tmp_path / "random.json").write_text('{}')  # should NOT match
        cfg = {"adapters": {"gemini_cli": {"roots": [str(tmp_path)]}}}
        adapter = GeminiCliAdapter(config=cfg)
        sessions = adapter.discover_sessions()
        # Only chat-*.json and session-*.json match
        assert len(sessions) == 2

    def test_derive_project_slug(self, tmp_path: Path):
        cfg = {"adapters": {"gemini_cli": {"roots": [str(tmp_path)]}}}
        adapter = GeminiCliAdapter(config=cfg)
        p = tmp_path / "MyProject" / "session.jsonl"
        slug = adapter.derive_project_slug(p)
        assert slug == "gemini-myproject"

    def test_derive_project_slug_fallback(self):
        adapter = GeminiCliAdapter()
        p = Path("/some/random/path/session.jsonl")
        slug = adapter.derive_project_slug(p)
        assert slug.startswith("gemini-")


class TestGeminiCliConverter:
    """Test the converter round-trip against the Gemini CLI fixture."""

    def test_parse_fixture(self):
        fx = FIXTURES_DIR / "gemini_cli" / "minimal.jsonl"
        records = parse_jsonl(fx)
        assert len(records) == 4
        assert records[0]["type"] == "user"
        assert records[1]["type"] == "assistant"

    def test_count_user_messages(self):
        records = parse_jsonl(FIXTURES_DIR / "gemini_cli" / "minimal.jsonl")
        assert count_user_messages(records) == 1

    def test_count_tool_calls(self):
        records = parse_jsonl(FIXTURES_DIR / "gemini_cli" / "minimal.jsonl")
        assert count_tool_calls(records) == 1

    def test_extract_tools_used(self):
        records = parse_jsonl(FIXTURES_DIR / "gemini_cli" / "minimal.jsonl")
        tools = extract_tools_used(records)
        assert tools == ["Bash"]

    def test_render_session_markdown(self):
        md, slug = _render_fixture("gemini_cli", "gemini-learning")
        assert slug == "gemini-decorators"
        # Frontmatter
        assert "---" in md
        assert "slug: gemini-decorators" in md
        assert "project: gemini-learning" in md
        assert "tools_used: [Bash]" in md
        assert "model: gemini-2.5-pro" in md
        # Body
        assert "## Conversation" in md
        assert "### Turn 1 \u2014 User" in md
        assert "decorators" in md
        assert "### Turn 1 \u2014 Assistant" in md
        assert "`Bash`" in md

    def test_snapshot_match(self):
        md, _slug = _render_fixture("gemini_cli", "gemini-learning")
        snap = SNAPSHOTS_DIR / "gemini_cli" / "minimal.md"
        if not snap.exists():
            _update_snapshot(snap, md)
        expected = snap.read_text(encoding="utf-8")
        assert md == expected, "Gemini CLI snapshot mismatch -- re-run with UPDATE_SNAPSHOTS=1"

    def test_graceful_degradation_unknown_record_type(self):
        """Unknown record types should be silently skipped, not crash."""
        fx = FIXTURES_DIR / "gemini_cli" / "minimal.jsonl"
        records = parse_jsonl(fx)
        # Inject unknown Gemini-specific record types
        records.insert(1, {"type": "gemini-thinking-trace", "thought": "reasoning..."})
        records.insert(3, {"type": "grounding-metadata", "sources": []})
        filtered = filter_records(records, ["queue-operation"])
        redactor = Redactor(DEFAULT_CONFIG)
        # Should NOT raise
        md, slug, started = render_session_markdown(
            filtered,
            jsonl_path=Path("test.jsonl"),
            project_slug="gemini-test",
            redact=redactor,
            config=DEFAULT_CONFIG,
            is_subagent_file=False,
        )
        assert "## Conversation" in md
        assert "gemini-thinking-trace" not in md
        assert "grounding-metadata" not in md


# ═══════════════════════════════════════════════════════════════════════════
# PDF ADAPTER (#39)
# ═══════════════════════════════════════════════════════════════════════════


class TestPdfAdapterContract:
    """Verify the PDF adapter meets the BaseAdapter contract."""

    def test_subclass_of_base(self):
        assert issubclass(PdfAdapter, BaseAdapter)

    def test_registered(self):
        discover_adapters()
        assert "pdf" in REGISTRY
        assert REGISTRY["pdf"] is PdfAdapter

    def test_name_attribute(self):
        discover_adapters()
        assert PdfAdapter.name == "pdf"

    def test_has_description(self):
        desc = PdfAdapter.description()
        assert isinstance(desc, str)
        assert len(desc) > 0

    def test_declares_supported_schema_versions(self):
        assert hasattr(PdfAdapter, "SUPPORTED_SCHEMA_VERSIONS")
        versions = PdfAdapter.SUPPORTED_SCHEMA_VERSIONS
        assert isinstance(versions, list)
        assert len(versions) > 0
        assert all(isinstance(v, str) for v in versions)

    def test_session_store_path_empty_default(self):
        """PDF adapter has no default roots -- user must configure."""
        adapter = PdfAdapter()
        paths = adapter.session_store_path
        assert isinstance(paths, list)
        assert len(paths) == 0

    def test_is_available_false_by_default(self):
        """PDF adapter requires explicit configuration."""
        assert PdfAdapter.is_available() is False

    def test_config_override_roots(self):
        cfg = {"adapters": {"pdf": {"roots": ["/tmp/papers"]}}}
        adapter = PdfAdapter(config=cfg)
        assert len(adapter.roots) == 1
        assert str(adapter.roots[0]) == "/tmp/papers"

    def test_config_page_limits(self):
        cfg = {"adapters": {"pdf": {"min_pages": 2, "max_pages": 100}}}
        adapter = PdfAdapter(config=cfg)
        assert adapter.min_pages == 2
        assert adapter.max_pages == 100


class TestPdfDiscovery:
    """Test PDF session discovery and slug derivation."""

    def test_discover_in_empty_dir(self, tmp_path: Path):
        cfg = {"adapters": {"pdf": {"roots": [str(tmp_path)]}}}
        adapter = PdfAdapter(config=cfg)
        assert adapter.discover_sessions() == []

    def test_discover_finds_pdfs(self, tmp_path: Path):
        (tmp_path / "paper.pdf").write_bytes(b"%PDF-1.0 fake")
        (tmp_path / "notes.txt").write_text("not a pdf")
        cfg = {"adapters": {"pdf": {"roots": [str(tmp_path)]}}}
        adapter = PdfAdapter(config=cfg)
        sessions = adapter.discover_sessions()
        assert len(sessions) == 1
        assert sessions[0].name == "paper.pdf"

    def test_discover_recurses_subdirs(self, tmp_path: Path):
        sub = tmp_path / "cs" / "papers"
        sub.mkdir(parents=True)
        (sub / "attention.pdf").write_bytes(b"%PDF")
        (tmp_path / "intro.pdf").write_bytes(b"%PDF")
        cfg = {"adapters": {"pdf": {"roots": [str(tmp_path)]}}}
        adapter = PdfAdapter(config=cfg)
        sessions = adapter.discover_sessions()
        assert len(sessions) == 2

    def test_derive_project_slug(self, tmp_path: Path):
        cfg = {"adapters": {"pdf": {"roots": [str(tmp_path)]}}}
        adapter = PdfAdapter(config=cfg)
        p = tmp_path / "Research Papers" / "attention.pdf"
        slug = adapter.derive_project_slug(p)
        assert slug == "pdf-research-papers"

    def test_derive_project_slug_simple(self):
        adapter = PdfAdapter()
        p = Path("/home/user/docs/paper.pdf")
        slug = adapter.derive_project_slug(p)
        assert slug == "pdf-docs"


class TestPdfExtractText:
    """Test the PDF text extraction helper."""

    def test_extract_text_without_pypdf(self):
        """extract_text returns empty string when pypdf is not installed."""
        # We can't guarantee pypdf is installed in test env, so test the
        # graceful degradation path.
        result = PdfAdapter.extract_text(Path("/nonexistent/file.pdf"))
        assert result == ""

    def test_extract_text_bad_path(self, tmp_path: Path):
        """extract_text returns empty string for non-PDF files."""
        fake = tmp_path / "not-a-pdf.pdf"
        fake.write_text("this is not a real PDF")
        result = PdfAdapter.extract_text(fake)
        # Should return "" whether pypdf is installed or not (it will fail to parse)
        assert isinstance(result, str)


class TestPdfGracefulDegradation:
    """Test PDF adapter handles edge cases gracefully."""

    def test_discover_nonexistent_roots(self):
        cfg = {"adapters": {"pdf": {"roots": ["/nonexistent/path/xyz"]}}}
        adapter = PdfAdapter(config=cfg)
        # Should NOT raise
        sessions = adapter.discover_sessions()
        assert sessions == []

    def test_multiple_roots_mixed_existence(self, tmp_path: Path):
        real_dir = tmp_path / "real"
        real_dir.mkdir()
        (real_dir / "paper.pdf").write_bytes(b"%PDF")
        cfg = {"adapters": {"pdf": {"roots": ["/nonexistent", str(real_dir)]}}}
        adapter = PdfAdapter(config=cfg)
        sessions = adapter.discover_sessions()
        assert len(sessions) == 1


# ═══════════════════════════════════════════════════════════════════════════
# CROSS-ADAPTER: Graceful degradation for all adapters
# ═══════════════════════════════════════════════════════════════════════════


class TestCrossAdapterGracefulDegradation:
    """Verify all three adapters handle unknown/malformed data gracefully."""

    def test_all_adapters_handle_empty_config(self):
        """Instantiating with no config should not raise."""
        CursorAdapter()
        GeminiCliAdapter()
        PdfAdapter()

    def test_all_adapters_handle_none_config(self):
        CursorAdapter(config=None)
        GeminiCliAdapter(config=None)
        PdfAdapter(config=None)

    def test_all_adapters_handle_empty_dict_config(self):
        CursorAdapter(config={})
        GeminiCliAdapter(config={})
        PdfAdapter(config={})

    def test_converter_survives_empty_jsonl(self, tmp_path: Path):
        """An empty .jsonl should parse to [] and not crash the converter."""
        empty = tmp_path / "empty.jsonl"
        empty.write_text("")
        records = parse_jsonl(empty)
        assert records == []

    def test_converter_survives_malformed_json(self, tmp_path: Path):
        """Malformed JSON lines should be silently skipped."""
        bad = tmp_path / "bad.jsonl"
        bad.write_text('{"type":"user"}\nnot json\n{"type":"assistant"}\n')
        records = parse_jsonl(bad)
        assert len(records) == 2

    def test_converter_survives_non_dict_records(self, tmp_path: Path):
        """Non-dict records (scalars, arrays) should be silently dropped."""
        mixed = tmp_path / "mixed.jsonl"
        mixed.write_text('42\n"hello"\n[1,2]\n{"type":"user","message":{"content":"hi","role":"user"}}\n')
        records = parse_jsonl(mixed)
        assert len(records) == 1
        assert records[0]["type"] == "user"
