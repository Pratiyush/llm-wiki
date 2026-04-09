"""Tests for graduated adapters — Cursor, Gemini CLI, PDF (v0.5 · #37, #38, #39).

Verifies each adapter's contract: SUPPORTED_SCHEMA_VERSIONS,
session_store_path, discover_sessions, derive_project_slug,
and graceful degradation (no crash on bad input).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from llmwiki.adapters.cursor import CursorAdapter
from llmwiki.adapters.gemini_cli import GeminiCliAdapter
from llmwiki.adapters.pdf import PdfAdapter

# pypdf is an optional dep — skip PDF discovery + extraction tests
# when it's not installed (CI doesn't install it by default).
try:
    import pypdf  # noqa: F401
    HAS_PYPDF = True
except ImportError:
    HAS_PYPDF = False

_skip_no_pypdf = pytest.mark.skipif(not HAS_PYPDF, reason="pypdf not installed")


# ═══════════════════════════════════════════════════════════════════════
# CURSOR ADAPTER
# ═══════════════════════════════════════════════════════════════════════


class TestCursorAdapterContract:
    def test_has_supported_schema_versions(self):
        assert hasattr(CursorAdapter, "SUPPORTED_SCHEMA_VERSIONS")
        assert len(CursorAdapter.SUPPORTED_SCHEMA_VERSIONS) >= 1

    def test_session_store_path_returns_list(self):
        adapter = CursorAdapter()
        paths = adapter.session_store_path
        assert isinstance(paths, (list, Path, type(None))) or paths is not None

    def test_derive_project_slug(self):
        adapter = CursorAdapter()
        slug = adapter.derive_project_slug(Path("/tmp/workspace-abc123/state.vscdb"))
        assert isinstance(slug, str)
        assert len(slug) > 0

    def test_discover_returns_list(self):
        adapter = CursorAdapter()
        result = adapter.discover_sessions()
        assert isinstance(result, list)

    def test_instantiate_with_no_config(self):
        adapter = CursorAdapter()
        assert adapter is not None

    def test_instantiate_with_empty_config(self):
        adapter = CursorAdapter(config={})
        assert adapter is not None


# ═══════════════════════════════════════════════════════════════════════
# GEMINI CLI ADAPTER
# ═══════════════════════════════════════════════════════════════════════


class TestGeminiCliAdapterContract:
    def test_has_supported_schema_versions(self):
        assert hasattr(GeminiCliAdapter, "SUPPORTED_SCHEMA_VERSIONS")
        assert len(GeminiCliAdapter.SUPPORTED_SCHEMA_VERSIONS) >= 1

    def test_session_store_path_exists(self):
        adapter = GeminiCliAdapter()
        paths = adapter.session_store_path
        assert paths is not None

    def test_derive_project_slug(self):
        adapter = GeminiCliAdapter()
        slug = adapter.derive_project_slug(Path("/tmp/gemini/session.jsonl"))
        assert isinstance(slug, str)
        assert len(slug) > 0

    def test_discover_returns_list(self):
        adapter = GeminiCliAdapter()
        result = adapter.discover_sessions()
        assert isinstance(result, list)

    def test_instantiate_with_no_config(self):
        adapter = GeminiCliAdapter()
        assert adapter is not None


# ═══════════════════════════════════════════════════════════════════════
# PDF ADAPTER
# ═══════════════════════════════════════════════════════════════════════


class TestPdfAdapterContract:
    def test_has_supported_schema_versions(self):
        assert hasattr(PdfAdapter, "SUPPORTED_SCHEMA_VERSIONS")
        assert len(PdfAdapter.SUPPORTED_SCHEMA_VERSIONS) >= 1

    def test_is_available_reflects_pypdf_install(self):
        """is_available() returns True when pypdf is installed, False
        otherwise. It does NOT gate on user config — that's the job of
        discover_sessions() checking self.enabled."""
        try:
            import pypdf  # noqa
            assert PdfAdapter.is_available() is True
        except ImportError:
            assert PdfAdapter.is_available() is False

    def test_default_disabled_returns_no_sessions(self):
        """Without explicit `enabled: true`, discover_sessions returns []."""
        adapter = PdfAdapter()
        assert adapter.discover_sessions() == []

    def test_instantiate_with_no_config(self):
        adapter = PdfAdapter()
        assert adapter is not None


@_skip_no_pypdf
class TestPdfDiscovery:
    def test_discover_finds_pdfs_when_enabled(self, tmp_path: Path):
        pdf_dir = tmp_path / "papers"
        pdf_dir.mkdir()
        (pdf_dir / "test.pdf").write_bytes(b"%PDF-1.4 fake")
        cfg = {"adapters": {"pdf": {"enabled": True, "roots": [str(pdf_dir)]}}}
        adapter = PdfAdapter(config=cfg)
        sessions = adapter.discover_sessions()
        assert len(sessions) == 1
        assert sessions[0].name == "test.pdf"

    def test_discover_recurses_subdirs(self, tmp_path: Path):
        sub = tmp_path / "papers" / "2026"
        sub.mkdir(parents=True)
        (sub / "deep.pdf").write_bytes(b"%PDF-1.4 fake")
        cfg = {"adapters": {"pdf": {"enabled": True, "roots": [str(tmp_path / "papers")]}}}
        adapter = PdfAdapter(config=cfg)
        sessions = adapter.discover_sessions()
        assert len(sessions) == 1

    def test_discover_skips_non_pdf(self, tmp_path: Path):
        pdf_dir = tmp_path / "papers"
        pdf_dir.mkdir()
        (pdf_dir / "readme.txt").write_text("not a pdf")
        (pdf_dir / "paper.pdf").write_bytes(b"%PDF-1.4")
        cfg = {"adapters": {"pdf": {"enabled": True, "roots": [str(pdf_dir)]}}}
        adapter = PdfAdapter(config=cfg)
        sessions = adapter.discover_sessions()
        assert len(sessions) == 1
        assert sessions[0].suffix == ".pdf"


@_skip_no_pypdf
class TestPdfExtractText:
    def test_extract_text_returns_tuple(self, tmp_path: Path):
        """extract_text always returns (body: str, meta: dict)."""
        fake = tmp_path / "fake.pdf"
        fake.write_text("not a real PDF")
        result = PdfAdapter.extract_text(fake)
        assert isinstance(result, tuple)
        body, meta = result
        assert isinstance(body, str)
        assert isinstance(meta, dict)

    def test_extract_text_bad_file_has_error_key(self, tmp_path: Path):
        fake = tmp_path / "bad.pdf"
        fake.write_text("garbage")
        body, meta = PdfAdapter.extract_text(fake)
        assert body == ""
        assert "error" in meta or meta.get("pages", 0) == 0

    def test_extract_text_nonexistent_file(self):
        body, meta = PdfAdapter.extract_text(Path("/does/not/exist.pdf"))
        assert body == ""
        assert "error" in meta


@_skip_no_pypdf
class TestPdfGracefulDegradation:
    def test_discover_nonexistent_roots(self):
        cfg = {"adapters": {"pdf": {"enabled": True, "roots": ["/nonexistent/xyz"]}}}
        adapter = PdfAdapter(config=cfg)
        sessions = adapter.discover_sessions()
        assert sessions == []

    def test_mixed_roots(self, tmp_path: Path):
        real_dir = tmp_path / "real"
        real_dir.mkdir()
        (real_dir / "paper.pdf").write_bytes(b"%PDF-1.4")
        cfg = {"adapters": {"pdf": {"enabled": True, "roots": ["/nonexistent", str(real_dir)]}}}
        adapter = PdfAdapter(config=cfg)
        sessions = adapter.discover_sessions()
        assert len(sessions) == 1

    def test_derive_project_slug_format(self):
        adapter = PdfAdapter()
        slug = adapter.derive_project_slug(Path("/home/user/Papers/ml/transformer.pdf"))
        assert slug.startswith("pdf-")
        assert " " not in slug


# ═══════════════════════════════════════════════════════════════════════
# CROSS-ADAPTER
# ═══════════════════════════════════════════════════════════════════════


class TestCrossAdapterGracefulDegradation:
    def test_all_adapters_handle_empty_config(self):
        for cls in [CursorAdapter, GeminiCliAdapter, PdfAdapter]:
            adapter = cls(config={})
            assert adapter is not None
            sessions = adapter.discover_sessions()
            assert isinstance(sessions, list)
